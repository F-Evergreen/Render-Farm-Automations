#! /usr/bin/python
"""

Deadline Toolbox:

Contains functions to modify jobs, workers, create logs and send emails.
For use in deadline scripting

"""

from scripts.General import u_environment_utils
u_environment_utils.setup_environment()
u_environment_utils.setup_python_site_packages()
from Deadline.Scripting import *
import os
import time
import random
from datetime import datetime
import csv
from System.Collections.Specialized import *
from python.utilities import emailutils
import pytz


def modify_job(job,
               set_priority=0,
               set_timeout_to_0=False,
               set_group="",
               set_failure_detection=0,
               override_job_failure_detection=False,
               override_task_failure_detection=False,
               append_job_comment="",
               set_concurrent_tasks=None,
               set_frames_per_task=None,
               set_machine_limit=None,
               nuke_continue_on_error=None
               ):
    """
    This function waits a random amount of time, then suspends the job before doing other actions defined below:

    :param job: The Deadline Job class to modify
    :param int set_priority: Option to modify the priority of the job and define what to set it to.
    :param bool set_timeout_to_0: Option to set the timeout to infinity (0) if True
    :param string set_group: Option to set the group of machines a job is being rendered on. I.e. "251gb"
    :param bool override_job_failure_detection: Option to change job failure detection to infinity.
    :param bool override_task_failure_detection: Option to change task failure detection to infinity,
    :param int set_failure_detection: Option to change the amount of errors a job can have before failing
    :param string append_job_comment: Option to append the comment of the job.
    :param int set_concurrent_tasks: Option to set the concurrent tasks of the job.
    :param int set_frames_per_task: Option to set the frames per each task of the job.
    :param int set_machine_limit: Option to set the machine limit of a job.
    """

    # wait for a random amount of seconds to avoid doing multiple rounds of suspending and resuming.
    random_number = random.uniform(2, 5)
    time.sleep(random_number)
    print("# waiting {} seconds before suspending the job, to avoid multiple rounds of "
          "suspending and resuming".format(random_number))

    # Suspend the job
    RepositoryUtils.SuspendJob(job)

    if set_priority:
        print("# the set_priority arg was found, so the priority will be set to '{}'".format(set_priority))
        # Lower the priority
        job.JobPriority = set_priority

    if set_timeout_to_0:
        print("# the set_timeout_to_0 arg was found, so the timeout will be set to infinity")
        # Set the timeout to infinity
        job.JobTaskTimeoutSeconds = 0

    if set_group:
        print("# the set_group arg was found, so the job group will be set to '{}'".format(set_group))
        # Change the group of machines a job is being rendered on
        job.JobGroup = set_group

    if override_job_failure_detection:
        print("# Override job failure detection arg was found. Setting to 'True'. This will remove the upper "
              "error limit on the job")
        # Remove the error limit on the job
        job.JobOverrideJobFailureDetection = True

    if override_task_failure_detection:
        print("# Override task failure detection arg was found. Setting to 'True'. This will remove the upper "
              "error limit on the task")
        job.JobOverrideTaskFailureDetection = True

    if set_failure_detection:
        print("# the set_failure_detection arg was found. the new amount of errors that will occur before failing "
              "is '{}'".format(set_failure_detection))
        # Change the amount of errors a job can have before failing
        job.JobOverrideJobFailureDetection = True
        job.JobFailureDetectionJobErrors = set_failure_detection

    if append_job_comment:
        print("# The set_job_comment arg was found. Appending the job comment to include other things")
        # Get the existing job comment and add out comment before it
        existing_job_comment = job.JobComment
        new_job_comment = "{} -- {}".format(existing_job_comment, append_job_comment)
        job.JobComment = new_job_comment

    if set_concurrent_tasks is not None:
        print("# Setting concurrent tasks to: {}".format(set_concurrent_tasks))
        job.JobConcurrentTasks = set_concurrent_tasks

    if set_frames_per_task is not None:
        print("# Setting frames per task to: {}".format(set_frames_per_task))
        RepositoryUtils.SetJobFrameRange(job, job.JobFrames, set_frames_per_task)

    if nuke_continue_on_error:
        print("# This job continued on error: ", job)
        job.SetJobPluginInfoKeyValue("ContinueOnError", "True")

    # Save the job
    RepositoryUtils.SaveJob(job)

    # This is after the save job as with the changes above we are using a cached version of the job to make changes
    # to, then saving it. Doing it after the save updates the machine limit in the monitor live, as it doesnt need
    # to be saved.

    if set_machine_limit is not None:
        print("# Setting machine limit to: {}".format(set_machine_limit))
        RepositoryUtils.SetMachineLimitMaximum(job.JobId, set_machine_limit)

    # Resuming the job
    RepositoryUtils.ResumeJob(job)


def modify_worker(slave,
                  time_delay_mins=0,
                  set_worker_state=None
                  ):
    """
    This function contains tools to make changes to a given worker.

    :param str slave: The deadline machine or "slave" to modify.
    :param int time_delay_mins: Option to set a time delay in minutes.
    :param bool set_worker_state: Option to set worker to be enabled: True, or disabled: False.
    """

    if time_delay_mins:
        time_delay_secs = time_delay_mins * 60
        time.sleep(time_delay_secs)

    if set_worker_state is not None:
        state_string = ""
        if set_worker_state:
            state_string = "enable"
        elif not set_worker_state:
            state_string = "disable"
        # Setup the command to set the worker state
        cmd_args = ["SetSlaveSetting", slave, 'SlaveEnabled', set_worker_state]
        # run the command to disable the worker
        ClientUtils.ExecuteCommand(cmd_args)
        print("'# executed the command to {} the machine '{}'.".format(state_string, slave))


def log_creator(error_report,
                job,
                log_dir
                ):
    """
    This function creates a monthly log for a given error

    Args:
        error_report,
        job,
        log_dir

    :param str log_dir: The folder name for the error type, e.g. "sssd_logs"
    """
    # Get London time as we set all of our automation using that at the moment
    london_time = LondonDatetime()
    # Get the current month
    current_month = london_time.localised_london_datetime.strftime("%Y-%B")
    # Define the file path for the log to go in
    filepath = "/Volumes/resources/pipeline/logs/deadline/{}".format(log_dir)
    # If the file path doesn't exist, create it.
    if not os.path.isdir(filepath):
        os.makedirs(filepath)
    # Write the log.
    file_name = os.path.join(filepath, "{}_log.csv".format(current_month))
    already_exists = False
    if os.path.isfile(file_name):
        already_exists = True

    with open(file_name, 'a+') as csv_file:
        column_names = ['Worker Name', 'User', 'DateTime', 'Error Message', 'Job ID', 'Task ID',
                        'Job Plugin'
                        ]
        writer = csv.DictWriter(csv_file, column_names, delimiter='|')
        if already_exists is False:
            writer.writeheader()
        writer.writerow({'Worker Name': error_report.ReportSlaveName,
                         'User': error_report.ReportJobUserName,
                         'DateTime': error_report.ReportDateTimeOf,
                         'Error Message': error_report.ReportMessage,
                         'Job ID': job.JobId,
                         'Task ID': error_report.ReportTaskID,
                         'Job Plugin': job.JobPlugin
                         })


def send_email(subject, message, addressee_list):
    """
    Sends an email from the wrangler.
    """
    emailutils.send_email(msg_from_addr="wrangler@unionvfx.com",
                          msg_to_addrs=addressee_list,
                          msg_subject=subject,
                          msg_body=[message],
                          )


def get_slave_names_in_group(group_name=""):

    """
    This function gets the slave names of all the workers in a group (set up in deadline monitor)
    Then puts them into a list to iterate over.

    Args:
        group_name
    returns: worker_list

    :param str group_name: the name of the group to get the list of workers for

    """

    cmd_list = ["-GetSlaveNamesInGroup", group_name]
    cmd_result = ClientUtils.ExecuteCommandAndGetOutput(cmd_list)
    worker_names = str(cmd_result)
    worker_list = worker_names.splitlines()

    return worker_list


def requeue_tasks_on_workers(re_queue_worker_list):
    """
    This function re-queues all the rendering tasks on a list of workers
    """
    # Get a list of all the active jobs
    all_active_jobs = RepositoryUtils.GetJobsInState("Active")
    # Loop through those active jobs to get a list of their tasks
    for job in all_active_jobs:
        job_task_collection = RepositoryUtils.GetJobTasks(job, True)
        # set up a list to add tasks to be re-queued into
        task_that_need_to_be_requeued = []
        for task in job_task_collection.TaskCollectionTasks:
            if task.TaskSlaveName in re_queue_worker_list:
                # Make sure that we only re-queue rendering tasks, not completed tasks.
                if task.TaskStatus == "Rendering":
                    # add the task to the list of tasks to be re-queued
                    task_that_need_to_be_requeued.append(task)
        # Requeue the tasks for that job
        RepositoryUtils.RequeueTasks(job, task_that_need_to_be_requeued)
    print("# I've requeued the tasks on: {}.".format(re_queue_worker_list))


def set_worker_state_of_user_group(group="", worker_state=None):
    """
    Allows you to enable or disable a group of machines quickly.
    """
    user_machines = RepositoryUtils.GetUserGroup(group)
    for user in user_machines:
        all_workers = RepositoryUtils.GetSlaveSettingsList(True)
        for worker in all_workers:
            if worker.SlaveComment == user:
                modify_worker(worker.SlaveName, set_worker_state=worker_state)


def get_job_frame_count(job):
    """
    Does a simple calculation to get the job's frame count as the Deadline API doesn't have this.
    """
    job_frame_count = job.JobTaskCount * job.JobFramesPerTask
    return job_frame_count


def restart_after_task_completion(worker):
    """
    A simpler command to restart the machine after task completion instead of having to remember the string every time.
    """
    SlaveUtils.SendRemoteCommand(worker, "OnLastTaskComplete RestartMachine")


def cleanup_files(path):
    """
    This deletes files in a given directory path.
    """
    for file in os.listdir(path):
        file = os.path.join(path, file)
        if os.stat(file).st_mtime < time.time() - 1 * 86400 and os.path.isfile(
                file):  # time of last modification, days,  86400 seconds in a day
            os.remove(file)
        else:
            pass


class LondonDatetime:
    """
    Allows us to use a London timezone aware datetime object. This is important for automation. At time of writing
    there is one wrangler across two timezones. Having everything use London time for automation works at the moment.

    When MTL have a larger farm, so they can render their own CG during the day, it would be fine to use regular
    "local" datetime.

    N.B. Using "Europe/London" allows us to take into account BST. It uses whatever time it is in London right now.
    Whereas just using UTC would mean LDN would be an hour out of sync for half the year!
    """

    @property
    def localised_london_datetime(self):
        # Get London time using pytz
        london_timezone = pytz.timezone("Europe/London")
        return datetime.now(london_timezone)

    def get_day_of_week(self):
        return self.localised_london_datetime.today().weekday()

    def get_hour_of_day(self):
        return self.localised_london_datetime.hour


def get_job_limits_as_list(job):
    """
    Unpack the job limits so we can iterate through them or use the list to update the limits.
    """
    job_limit_list = []
    for limit in job.JobLimitGroups:
        job_limit_list.append(limit)

    return job_limit_list


def set_prio(job, prio=0):
    """
    Set the priority of a given job. This also adds a flag needed for the Farm Notification System to avoid spamming
    producers emails.
    """
    if prio:
        job.JobPriority = prio
        if prio > 50:
            job.JobExtraInfo9 = "Automatic raised priority job"
        RepositoryUtils.SaveJob(job)


def create_temp_txt_file_path(job, function_name):
    """
    Return a file path that's unique to the job ID and Name that we use to determine if the function needs to run.
    We often use temp files to stop actions being performed multiple times on jobs.
    Args:
        job: The Deadline Job object: Used to draw the job ID and name for use in the temp file name.
        function_name: string: The name of the function calling this function. Used to determine what folder to put the
        temp file into.
    Returns:
        temp_file_path: string: the full file path for use in other functions.
    """
    temp_file_dir = os.path.join(os.sep,
                                 'Volumes',
                                 'resources',
                                 'pipeline',
                                 'logs',
                                 'deadline',
                                 '{}').format(function_name)
    # if the directory doesn't exist i.e. it's a new function, create the dir.
    if not os.path.exists(temp_file_dir):
        os.mkdir(temp_file_dir)

    temp_file_path = os.path.join(os.sep,
                                  temp_file_dir,
                                  '{}_{}_.txt'.format(job.JobId,
                                                      job.JobName.replace("/", "_").replace(" ", "_").replace(".", "_")
                                                      )
                                  )

    return temp_file_path


def farm_notification_system_check(job):
    """
    When running the Farm Notification System we want to do a few checks to make sure we don't spam the producers with
    emails.
    This function checks that the job in question is:
    - Above 80 priority
    - Not an "Automatic raised priority job". e.g. qt / client jobs.
    - Not from a pipeline user. We often want our jobs to fail fast when we prioritise them high.
    - Not a VCR, PDG or Hermes Job.

    If all of those conditions are met, the function returns True.
    """
    pipe_group = RepositoryUtils.GetUserGroup("pipeline")
    exclusions = ["VCR",
                  "Asset Publisher",
                  "Hermes"
                  ]
    if job.JobPriority >= 80:
        # We now set job extra info 9 to "Automatic raised priority job". This means we will only send emails for
        # jobs which have had their priorities changed manually by the wrangler.
        if not job.JobExtraInfo9 == "Automatic raised priority job":
            if job.JobUserName not in pipe_group:
                if not any(exclusion in job.JobName for exclusion in exclusions):
                    return True
    else:
        return False


def office_hours():
    """
    A simple check to see if we are in working hours. It returns True if we are.
    Working hours are Monday-Friday, 0900-1900
    This covers both sites as the datetime it uses is local to the submission machine.
    """
    day_of_week = datetime.now().today().weekday()
    hour_of_day = datetime.now().hour

    if day_of_week < 5 and 19 > hour_of_day > 8:
        return True
    else:
        return False


def set_job_timeout(job, timeout_in_minutes=0):
    """
    A function for setting the timeout on a job in minutes.

    Args:
        job: job
        timeout_in_minutes: int
    """

    job.JobTaskTimeoutSeconds = timeout_in_minutes * 60
    job.JobOnTaskTimeout = "Error"
    RepositoryUtils.SaveJob(job)


def get_ldn_machines_assigned_to_mtl_artists():
    """
    When run, this function returns a list of London machines assigned to Montreal artists.
    This is useful for setting up their machines to be available to work on when they need them, and also have them
    available to render with when not being worked on.

    Returns:
          mtl_artist_london_machines_list: List: List of London based machines assigned to Montreal artists.

    """
    # Set up Shotgrid connection. We want to do this only when the function is called as this file is used everywhere.
    from upy.udbWrapper import udb_connection
    sg = udb_connection.db

    # Get all the artists who are active, have a computer assigned and are in Montreal.
    fields = ["login", "name", "sg_computers_1"]
    filters = [["sg_status_list", "is", "act"],
               ["sg_computers_1", "is_not", None],
               ["department", "name_contains", "Montreal"]
               ]
    found_users = sg.find("HumanUser", filters, fields)

    # set up a list to put these machines into
    mtl_artist_london_machines_list = []
    for user in found_users:
        for computer in user["sg_computers_1"]:
            # we are only interested in mtl artist's london machines
            excluded_machine_types = ["win", "kvm", "mtl"]
            if not any(machine_type in computer["name"] for machine_type in excluded_machine_types):
                mtl_artist_london_machines_list.append(computer["name"])

    return mtl_artist_london_machines_list


def is_job_u_render(job):
    """
    This function returns True if the job passed to it is a u_render job (CommandLine, Arnold job)
    """
    # As we need to check for u_arnold jobs a lot, and it's a bit more involved than just checking for plugin, I've
    # added it as a function here
    if job.JobPlugin == "CommandLine":
        limits = get_job_limits_as_list(job)
        if "arnold license limit" in limits:
            return True
