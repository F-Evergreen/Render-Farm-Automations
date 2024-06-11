#! /usr/bin/python

"""
This is a library of all the functions we run on our farm automation crons.
"""

from scripts.General import u_environment_utils
u_environment_utils.setup_environment()
u_environment_utils.setup_python_site_packages()
from Deadline.Scripting import *
from System.Collections.Specialized import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox
from scripts.General.u_RestartHolidayUsers import restart_holiday_users
from workalendar.europe import UnitedKingdom
from datetime import datetime


class CronLibrary:

	def __init__(self, site):
		"""
		Initialise all the reused, site dependent and static variables.
		"""
		# Get list of all the workstations at the site (e.g. "na_ne_workstations").
		self.site_artist_machines = u_DeadlineToolbox.get_slave_names_in_group(site + "_workstations")
		# Get list of all the render nodes at the site (e.g. "na_ne_render_nodes").
		self.site_render_nodes = u_DeadlineToolbox.get_slave_names_in_group(site + "_render_nodes")
		# Get list of London machines currently assigned to Montreal artists from Shotgrid.
		self.mtl_artist_london_machines_list = u_DeadlineToolbox.get_ldn_machines_assigned_to_mtl_artists()
		# Get list of the loud machines (this is a temp group in LDN until they are removed from the floor).
		self.loud_worker_list = u_DeadlineToolbox.get_slave_names_in_group("pizza_boxes_on_floor")
		# Get the active and pending jobs on the farm.
		self.active_pending_jobs = RepositoryUtils.GetJobsInState(["Active", "Pending"])
		# Get failed jobs for resetting group to 251
		self.failed_jobs = RepositoryUtils.GetJobsInState(["Failed"])
		# Get an updated list of all pools.
		self.all_pools = RepositoryUtils.GetPoolNames()
		# List of current CG render plugins we use.
		self.cg_renderers = ["Arnold", "Mantra"]
		# List of names of pools that we don't want added to the workstations
		self.excluded_workstation_pools = ["windows", "none", "hermes"]
		# List of limit names for "ForceMachineLimit" event.
		self.force_machine_limit_keys = ["Limit_Nuke",
										 "Limit_Mantra",
										 "Limit_Houdini",
										 "Limit_Arnold",
										 "Limit_MayaCmd"
										 ]
		# Dictionary of default values for the "TimeoutErrorHandling" script.
		self.timeout_default_dict = {"Nuke Timeout": 15,
									 "Maya and Houdini Timeout": 10,
									 "Arnold and Mantra Timeout": 180,
									 "Nuke Concurrent Tasks": 1,
									 "Nuke Frames Per Task": 2,
									 "Nuke Machine Limit": 0,
									 "Maya and Houdini Concurrent Tasks": 1,
									 "Maya and Houdini Priority": 40,
									 "Maya and Houdini Machine Limit": 0
									 }

		# As we have artists in MTL using LDN machines; we want to treat those LDN machines as if they were in MTL,
		# so they are available when needed by the artist during their working hours.
		# We also want to exclude these machines from the "eu_w" pool of machines for the same reason.
		if site == "na_ne":
			for worker in self.mtl_artist_london_machines_list:
				# The way we report machine names in Shotgrid is a mismatch of lower and upper cases, deadline is always
				# lower, so make sure we append/remove the lower case string.
				# Else we get x not present in list Value Errors.
				self.site_artist_machines.append(worker.lower())
		if site == "eu_w":
			for worker in self.mtl_artist_london_machines_list:
				# First check if the machine is in the list. Groups can be removed from machines on Deadline if they
				# have been reinstalled or recently added to the farm. Regardless, if it's location on Shotgrid is
				# London, it should be in the eu_w_workstations group.
				if worker.lower() not in self.site_artist_machines:
					RepositoryUtils.AddGroupToSlave(worker.lower(), "eu_w_workstations")
					print("Added {} to the {}_workstations group in Deadline.".format(worker.lower(), site))
				# If a worker is not in the list already due to it not being in the group, we don't need to worry about
				# removing it, hence elif. It will be in the list next time around and hit this elif then too.
				# If the worker does exist in the list, remove it.
				elif worker.lower() in self.site_artist_machines:
					self.site_artist_machines.remove(worker.lower())

	def clear_workstation_pools(self):
		"""
		Remove all the pools from each workstation at a given site.
		"""
		for worker in self.site_artist_machines:
			RepositoryUtils.SetPoolsForSlave(worker, [""])

	def set_cg_to_group(self, group):
		"""
		Put all the leftover Arnold, Mantra and u_render jobs into "251gb" group to stop them rendering on
		comp machines during the day. We also do this for failed jobs as if artists resume them in the morning,
		they would render on all machines, which isn't wanted.
		"""
		for jobs_list in [self.active_pending_jobs, self.failed_jobs]:
			for job in jobs_list:
				if job.JobPlugin in self.cg_renderers or "arnold license limit" in job.JobLimitGroups:
					job.JobGroup = group
					RepositoryUtils.SaveJob(job)

	def reset_houdini_engine_licence_limit(self, no_of_licenses):
		"""
		Reset Houdini Limit every morning to a specified number (engine license value). This is necessary because
		overnight and over the weekend the wranglers can up the value to use more licenses(core and fx) but in the
		morning the artists will need the core and fx license to work.
		"""
		RepositoryUtils.SetLimitGroupMaximum("houdini", no_of_licenses)

	def reset_user_groups(self, groups):
		"""
		Remove the users from the given user group.
		"""
		for group in groups:
			user_group_users = RepositoryUtils.GetUserGroup(group)
			RepositoryUtils.RemoveUsersFromUserGroups(user_group_users, [group])

	def restart_holiday_onset_users(self):
		"""
		Restart users who are on holiday or on set if they forget to log out.
		"""
		# Make sure we only run the restart on Work Days
		cal = UnitedKingdom()
		today = datetime.today().date()
		if cal.is_working_day(today):
			# run the script to check and restart any machines needed.
			restart_holiday_users()

	def requeue_tasks_on_workstations(self):
		"""
		Check for and requeue any jobs still rendering on workstations. This allows users to log on without their
		CPU at 100%.
		"""
		self.requeue_tasks_on_list_of_machines(list_of_machines=self.site_artist_machines)

	def requeue_tasks_on_non_251_machines(self):
		"""
		If any CG jobs are still rendering on non 251gb machines, we want to requeue them as the frame times would be
		at least 1hr by this point, and we can't get through those in the day, instead we need to free up the farm for
		2D jobs.
		"""
		group_251 = u_DeadlineToolbox.get_slave_names_in_group(group_name="251gb")
		non_251_machines = []
		for machine in self.site_render_nodes:
			if machine not in group_251:
				non_251_machines.append(machine)
		self.requeue_tasks_on_list_of_machines(list_of_machines=non_251_machines)

	def requeue_tasks_on_list_of_machines(self, list_of_machines):
		"""
		This function re-queues any rendering tasks on a given list of machines.
		"""
		for job in self.active_pending_jobs:
			# Add an exception for if we need a test job on a workstation, and we don't want it to be affected by
			# the requeue script. (Put these types of jobs in the render_testing pool)
			if "render_testing" not in job.JobPool:
				# use the u_render check tool to determine if the job is u_render (CommandLine arnold) If the
				u_render_job_check = u_DeadlineToolbox.is_job_u_render(job)
				if u_render_job_check or job.JobPlugin in self.cg_renderers:
					# get the TaskCollection on that job
					job_task_collection = RepositoryUtils.GetJobTasks(job, True)
					# set up a list to add tasks to be re-queued into
					task_that_need_to_be_requeued = []
					# If the worker on a task is in the list of site workstations and is rendering,
					# add it to the list of tasks to be re-queued
					for task in job_task_collection.TaskCollectionTasks:
						if any(worker in task.TaskSlaveName for worker in list_of_machines):
							if task.TaskStatus == "Rendering":
								task_that_need_to_be_requeued.append(task)
					# Requeue the tasks
					RepositoryUtils.RequeueTasks(job, task_that_need_to_be_requeued)

	def add_render_pools_to_workstations(self):
		"""
		Adds render pools to each workstation
		"""
		# Temp remove mm pool from mtl workstations only. As mm submission is borked till config2.
		if any("mtl" in worker for worker in self.site_artist_machines):
			self.excluded_workstation_pools.append("mm")
		for worker in self.site_artist_machines:
			# leave loud workers out of the render pool during the day
			if worker not in self.loud_worker_list:
				for pool in self.all_pools:
					if pool not in self.excluded_workstation_pools:
						RepositoryUtils.AddPoolToSlave(worker, pool)

	def modify_worker_state_for_user_group(self, user_group, worker_state):
		"""
		People working late need their machine to not be enabled by the farm overnight.
		Some leads who are always in meetings need their machine disabled, so it doesn't get used on the farm when
		it goes idle for an hour
		"""
		# Get the user group users
		user_group_users = RepositoryUtils.GetUserGroup(user_group)
		for user_name in user_group_users:
			# Get the user's machine by comparing it with the comment on the machine (where we put the last
			# logged-in user)
			all_worker_settings = RepositoryUtils.GetSlaveSettingsList(True)
			for worker in all_worker_settings:
				if worker.SlaveComment == user_name:
					u_DeadlineToolbox.modify_worker(worker.SlaveName, set_worker_state=worker_state)

	def add_loud_workstations_to_render_pool(self):
		"""
		Adds all pools except excluded pools i.e. windows, pdg etc...
		"""
		for worker in self.loud_worker_list:
			for pool in self.all_pools:
				if "mtl" not in pool and pool not in self.excluded_workstation_pools:
					RepositoryUtils.AddPoolToSlave(worker, pool)

	def force_start_workers(self):
		"""
		Force-start the worker instance on each workstation, this ensures we can use the worker even if the user hasn't
		logged out. This won't impact the user if they're still using it as the worker will go offline when it detects
		input.
		"""
		for worker in self.site_artist_machines:
			SlaveUtils.SendRemoteCommand(worker, "LaunchSlave")

	def restart_render_nodes(self):
		"""
		Restart all the site's render nodes, after it finishes with the job rendering on it. This helps lessen random
		machine errors.
		"""
		# Restart each render node after the last task has completed on it.
		for worker in self.site_render_nodes:
			SlaveUtils.SendRemoteCommand(worker, "OnLastTaskComplete RestartMachine")

	def set_job_plugin_priority(self, plugin, priority):
		"""
		Set all the jobs of a certain plugin to a given priority.
		"""
		for job in self.active_pending_jobs:
			if job.JobPlugin == plugin:
				job.JobPriority = priority
				# if the priority is above 50 we need to note it in the job extra info, as this is referenced in the
				# Farm Notification System.
				if priority > 50:
					job.JobExtraInfo9 = "Automatic raised priority job"
				RepositoryUtils.SaveJob(job)

	def remove_machine_limits_on_all_jobs(self):
		"""
		Remove all machine limits for active and pending jobs.
		"""
		for job in self.active_pending_jobs:
			RepositoryUtils.SetMachineLimitMaximum(job.JobId, 0)

	def reset_force_machine_limit_values(self):
		"""
		Reset the values of the u_ForceMachineLimit event to 0 (infinity).
		"""
		for limit_key in self.force_machine_limit_keys:
			RepositoryUtils.AddOrUpdateEventPluginConfigSetting("u_ForceMachineLimit", limit_key, str(0))

	def reset_timeout_error_handling_values(self):
		"""
		Reset the u_TimeoutErrorHandling event plugin to its default values.
		"""
		for key in self.timeout_default_dict.keys():
			RepositoryUtils.AddOrUpdateEventPluginConfigSetting("u_TimeoutErrorHandling",
																key,
																str(self.timeout_default_dict[key])
																)
