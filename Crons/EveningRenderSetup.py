#! /usr/bin/python

"""
"""
from scripts.General.Crons import u_CronLibrary
import socket


def __main__(*args):
	# Here we determine if the file is being run on the MTL pulse, or pulse1/2 (which are located in london)...
	# ...then run the associated location's cron.
	machine_name = socket.gethostname()
	eu_w_pulses = ["pulse1", "pulse2"]
	na_ne_pulse = "pulse-mtl-001"
	if machine_name in eu_w_pulses:
		eu_w_1900_cron()
	elif machine_name == na_ne_pulse:
		ne_ne_1800_cron()
	else:
		print("You are attempting to run cron this locally. This is designed to be run on a localised pulse server"
			  "due to the nature of the functions being run."
			  "Please ask systems to do this for you if you need to test on a pulse server.")


def eu_w_1900_cron():
	"""
	This is a cron that will run at 19:00pm Mon-Fri in LDN.
	- Adds loud workstations back into render pool.
	- Force starts all workstations, allowing the farm to use them even if the user doesn't log out.
	- Restart the site's workstations to prevent long term errors.
	- Remove the group from CG renders.
	- Set remaining Nuke jobs to 95 priority. This allows them to go through before prioritised CG.
	- Remove any machine limits on jobs.
	- Reset "u_ForceMachineLimit" values.
	- Reset "u_TimeoutErrorHandling" values.
	- Disable workers in the "u_OvernightDisableMachine" group. (Usually for people working late)
	- Enable workers in the "u_DisableMachineDuringDay" group. Allows lead / HOD machines to be used on the farm.
	"""

	# Instantiate the cron library with the site location.
	cron_lib_instance = u_CronLibrary.CronLibrary(site="eu_w")

	# Run the needed functions.
	cron_lib_instance.add_loud_workstations_to_render_pool()
	cron_lib_instance.force_start_workers()
	cron_lib_instance.restart_render_nodes()
	cron_lib_instance.set_cg_to_group(group="none")
	cron_lib_instance.set_job_plugin_priority(plugin="Nuke", priority=95)
	cron_lib_instance.remove_machine_limits_on_all_jobs()
	cron_lib_instance.reset_force_machine_limit_values()
	cron_lib_instance.reset_timeout_error_handling_values()
	cron_lib_instance.modify_worker_state_for_user_group(user_group="u_OvernightDisableMachine",
													 worker_state=False
													 )
	cron_lib_instance.modify_worker_state_for_user_group(user_group="u_DisableMachineDuringDay",
													 worker_state=True
													 )


def ne_ne_1800_cron():
	"""
	This is a cron that will run at 18:00pm Mon-Fri in MTL.
	- Force starts all workstations, allowing the farm to use them even if the user doesn't log out.
	- Restart the site's workstations to prevent long term errors.
	"""

	# Instantiate the cron library with the site location.
	cron_lib_instance = u_CronLibrary.CronLibrary(site="na_ne")

	# Run the needed functions.
	cron_lib_instance.force_start_workers()
	cron_lib_instance.restart_render_nodes()

