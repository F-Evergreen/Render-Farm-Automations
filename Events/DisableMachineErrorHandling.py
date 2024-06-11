#! /usr/bin/python
"""

When an error occurs which means we need to disable a machine we handle it in this script.
For some errors we can fix the machine automatically and re-enable it, if not we wend an email notifying the wrangler.

"""

from Deadline.Events import *
from Deadline.Scripting import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox
import re
from System.Collections.Specialized import *


def GetDeadlineEventListener():
    return OnError()


def CleanupDeadlineEventListener(deadlinePlugin):
    deadlinePlugin.Cleanup()


class OnError(DeadlineEventListener):

    def __init__(self):

        self.OnJobErrorCallback += self.disable_machine_error_handling

    def Cleanup(self):
        del self.OnJobErrorCallback

    def disable_machine_error_handling(self, job, task, errorReport):
        """
        This function handles the disabling of machines if needed when certain errors occur.

        NB: Though this function doesn't use the "task" object, it needs the "task" positional arg as it gets
        it from the OnJobErrorCallback. Without it, the function errors with a Type error.

        Args:
            job: The Deadline job object.
            task: The Deadline task object.
            errorReport: The error report from the erroring task.


        """
        # List of regular expression patterns to look for in a Deadline Error report
        disable_machine_error_patterns = ["No space left on device",
                                          "The user '.*' does not exist",
                                          ".*Permission denied: '/localCache/.*'"
                                          ]

        # Get worker name
        worker_name = errorReport.ReportSlaveName

        setup_and_send_email = True
        disable_machine_reason = ""

        for regex_error_pattern in disable_machine_error_patterns:
            # example of error message from Deadline 
            # "The user 'vili' does not exist"
            # use regular expression matching to match the regex error patterns listed above
            # with the errorReport.ReportMessage string
            match_result = re.match(regex_error_pattern, errorReport.ReportMessage)
            if match_result:
                # Always disable the worker as we don't want to run any other jobs on it until fixed.
                u_DeadlineToolbox.modify_worker(worker_name, set_worker_state=False)
                # This error is usually caused if the sssd service on the machine stops running. A restart will
                # usually solve this, but we can also restart the sssd with a commandline command.
                if regex_error_pattern == "The user '.*' does not exist":
                    # This script is located at "/Volumes/resources/bin/u_restart_sssd_service.sh"
                    sssd_command_result = SlaveUtils.SendRemoteCommandWithResults(worker_name, "Execute u_restart_sssd_service.sh -X")
                    # Create / append a log for this error
                    u_DeadlineToolbox.log_creator(errorReport, job, log_dir="sssd_logs")
                    # if the command runs and the sssd is still disabled, leave the worker disabled
                    exception_list = ["SSSD is active, the worker is erroring for another reason.",
                                      "the SSSD service failed to start."]
                    disable_machine_reason = "SSSD service failed to restart or is already running. Re-enable the" \
                                             "machine and see if the error persists."
                    # If an exception is found in the command result, try to remedy but leave the worker disabled
                    # The wrangler should re-enable the machine to see if the error persists.
                    if any(exception_string in sssd_command_result for exception_string in exception_list):
                        # for workstations, try to relaunch the worker.
                        if "union" in worker_name:
                            SlaveUtils.SendRemoteCommand(worker_name, "RelaunchSlave")
                        # for render machines, restart the machine.
                        elif "render" in worker_name:
                            SlaveUtils.SendRemoteCommand(worker_name, "RestartMachine")
                    # Re-enable the worker if the sssd was restarted without issue.
                    else:
                        u_DeadlineToolbox.modify_worker(worker_name, set_worker_state=True)
                        # We don't need to set up the email as it has been fixed automatically
                        setup_and_send_email = False

                # If it is a cache error, tell the wrangler what to do next.
                if regex_error_pattern == ".*Permission denied: '/localCache/.*'":
                    disable_machine_reason = "Local Cache drive needs re-mounting. Ask systems to do this for you."

                if regex_error_pattern == "No space left on device":
                    disable_machine_reason = "The system has run out of storage, contact systems."

                # If we have to disable a machine, set up an email and send it to the wrangler
                if setup_and_send_email:
                    # setup email info
                    subject = "The worker '{}' has been disabled on the farm.".format(worker_name)
                    message = "The worker '{}' has been automatically disabled because of this error:" \
                              "\n{}" \
                              "\n{}".format(worker_name,
                                            errorReport.ReportMessage,
                                            disable_machine_reason
                                            )
                    # send the email to the wrangler
                    u_DeadlineToolbox.send_email(subject=subject,
                                                 message=message,
                                                 addressee_list=["wrangler@unionvfx.com"]
                                                 )
