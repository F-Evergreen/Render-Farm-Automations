#! /usr/bin/python3
"""
This file contains functions that will check for errors in the error report, and perform actions on the job.
"""

from Deadline.Events import *
from Deadline.Scripting import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox
from scripts.General.u_FarmNotificationSystem import u_FarmNotificationSystem
import logging
import os
import re
from System.Collections.Specialized import *


def GetDeadlineEventListener():
    return OnError()


def CleanupDeadlineEventListener(deadlinePlugin):
    deadlinePlugin.Cleanup()


class OnError(DeadlineEventListener):

    def __init__(self):

        self.OnJobErrorCallback += self.OnJobError
        self.worker = ""

    def Cleanup(self):
        del self.OnJobErrorCallback

    def OnJobError(self, job, task, errorReport):
        self.worker = errorReport.ReportSlaveName

        # Run the functions to look for the error to handle
        self.clear_nuke_caches(errorReport)
        self.override_failure_detection(errorReport, job)
        self.plugin_crash_handling(errorReport, job)

    def clear_nuke_caches(self, errorReport):
        """
        Clear Nuke Caches /var/tmp/nuke when the related error occurs
        """
        if "Error: ERROR: Unable to create cache directory" in errorReport.ReportMessage:
            # Send Remote Command to Clear Cache
            # The path for this script is: /Volumes/resources/bin/clearnukecache.sh
            SlaveUtils.SendRemoteCommandWithResults(self.worker, "Execute clearNukeCache.sh -X")
            print("Nuke Temp Cache cleared")
            logging.info('Nuke Caches on {} have been cleared after Job Error Event'.format(self.worker))

    def override_failure_detection(self, errorReport, job):
        """
        If we know an error doesn't affect a render we can ignore its errors here.
        """

        failure_detection_errors = [".* Stale file handle",
                                    "Error: FailRenderException : IOError: [Errno .*] No such file or directory:.*",
                                    "Error: IOError: [Errno .*] File exists: ",
                                    ".* errors generated",
                                    ".*Maximum user counted exceeded..*",
                                    ".*signal caught: SIGSEGV -- Invalid memory reference.*",
                                    ".*No licenses could be found to run this application..*",
                                    ".*moov atom not found.*"
                                    ]
        # This creates a filepath using the function name as the folder and the job info as the file name.
        # We use temp files to check and stop actions being performed multiple times.
        job_failure_detection_file_path = u_DeadlineToolbox.create_temp_txt_file_path(job,
                                                                                      function_name="failure_detection"
                                                                                      )
        # for each error string in the list above use regular expression matching to match the regex error patterns
        # with the errorReport.ReportMessage string
        for regex_error_pattern in failure_detection_errors:
            match_result = re.match(regex_error_pattern, errorReport.ReportMessage)
            if match_result:
                # If the failure detection file doesn't exist yet, set no. of errors allowed to infinity and append
                # the job comment to reflect the change
                if not os.path.isfile(job_failure_detection_file_path):
                    # For moov atom not found we want to just resume the failed job as QTs fail after 1 error
                    if regex_error_pattern == ".*moov atom not found.*":
                        RepositoryUtils.ResumeFailedJob(job)
                        break
                    else:
                        u_DeadlineToolbox.modify_job(job,
                                                     override_job_failure_detection=True,
                                                     override_task_failure_detection=True,
                                                     append_job_comment="Job and Task failure detection set to 0"
                                                     )

                        # Now write out the temp failure detection file for this job. This stops the us repeating the
                        # same action.
                        with open(job_failure_detection_file_path, "w") as failure_detection_file:
                            failure_detection_file.write(regex_error_pattern)
                        # If we've found and remedied the error, break out of the loop.
                        break
                # if a file is found do nothing
                else:
                    pass

    def plugin_crash_handling(self, errorReport, job):
        """
        When a specific error occurs which is to do with the heaviness of a job, this function will alter parameters
        of the job to try and get it to run more efficiently.
        """
        plugin_crash_handling_errors = [
            # This error happens when a Nuke job is too heavy and causes the session to crash. We should catch this
            # and lower the number of concurrent tasks to lighten the load on the machine.
            "The Plugin's Sandbox process is alive but unresponsive.",
            # exit code 9 relates to a overload of system resources (we saw this with the ghost processes causing
            # machines to max out RAM). It would be good to also set concurrent tasks to 1 for these heavy jobs
            "unionLauncher: returning exit code 9",
            "failed to create thread, out of resources."
        ]
        # Store the job info before we make any changes.
        prev_job_info = {
            "concurrent": job.JobConcurrentTasks,
            "machine limit": job.JobMachineLimit,
            "frames per task": job.JobFramesPerTask,
            "priority": job.JobPriority
        }
        # Set up a path for the timeout error log to be put
        timeout_error_path = u_DeadlineToolbox.create_temp_txt_file_path(job,
                                                                         function_name="job_adjustment_error_handling")
        # Set up FNS messages
        job_params_changed_reason = "The job had an error on it which caused the program to " \
                                    "crash. These settings have been changed to help the " \
                                    "job get through without crashing further."
        job_params_changed_artist_suggestion = "Try to optimise your script, or check for " \
                                               "things that may be causing the crash."
        job_params_changed_prod_suggestion = "This is usually down to poor optimisation or" \
                                             "a buggy script. Please ask your artist to further" \
                                             " optimise their script."
        if any(error in errorReport.ReportMessage for error in plugin_crash_handling_errors):
            # We dont want to change sims tasks as they need to run as one job.
            if not job.JobGroup == "sims":
                job_frame_count = u_DeadlineToolbox.get_job_frame_count(job)
                # for larger jobs, we dont want to adjust the whole job just because one frame bugged.
                if job_frame_count < 1000:
                    # if the file doesn't already exist, modify the job
                    if not os.path.isfile(timeout_error_path):
                        u_DeadlineToolbox.modify_job(job,
                                                     set_concurrent_tasks=1,
                                                     set_frames_per_task=1,
                                                     override_task_failure_detection=True,
                                                     override_job_failure_detection=True,
                                                     )
                        parameters_changed = "Concurrent Tasks {} > 1" \
                                             "\nFrames Per Task {} > 1".format(prev_job_info["concurrent"],
                                                                               prev_job_info["frames per task"]
                                                                               )
                        # Inform the producers and artist of the change if it is a high prio shot.
                        fns_needed = u_DeadlineToolbox.farm_notification_system_check(job)
                        if fns_needed:
                            fns = u_FarmNotificationSystem.FarmNotificationSystem(job)
                            fns.on_parameters_changed(job,
                                                      parameters_changed,
                                                      job_params_changed_reason,
                                                      job_params_changed_artist_suggestion,
                                                      job_params_changed_prod_suggestion
                                                      )
                        with open(timeout_error_path, "w") as timeout_error_file:
                            timeout_error_file.write(errorReport.ReportMessage)
