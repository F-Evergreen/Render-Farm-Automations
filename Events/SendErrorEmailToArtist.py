"""
On Error Event- Send custom message to the artist for specific errors"

Copyright Union VFX 2020

"""

import os
import os.path
from Deadline.Events import *
from Deadline.Scripting import *
from System.Collections.Specialized import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox


def GetDeadlineEventListener():
    return OnError()


def CleanupDeadlineEventListener(deadlinePlugin):
    deadlinePlugin.Cleanup()


class OnError(DeadlineEventListener):

    def __init__(self):

        self.OnJobErrorCallback += self.OnJobError

    def Cleanup(self):
        del self.OnJobErrorCallback

    def OnJobError(self, job, task, errorReport):

        # Get username and other info needed
        user = job.JobUserName
        user_info = RepositoryUtils.GetUserInfo(user, True)
        email = user_info.UserEmailAddress
        job_name = job.JobName
        # Get the task id and then the Task object from that task id, so we use it later.
        task_id = str(errorReport.ReportTaskID)
        job_task_collection = RepositoryUtils.GetJobTasks(job, True)
        task_list = []
        for task in job_task_collection.TaskCollectionTasks:
            if task.TaskId == task_id:
                task_list.append(task)

        # temp file info. Use these files to verify if an email has already been sent.
        temp_file_path = u_DeadlineToolbox.create_temp_txt_file_path(job, "farm_emails")

        # Email setup
        signature = "\nThank You \n\n" \
                    "This is an automated message, if you still need help please contact wrangler@unionvfx.com"
        message_template = "Hi {} , \n \n Can you check your scene? Your job {} is erroring because: " \
                           "\n\n {} \n \n solution \n {}".format(user.capitalize(),
                                                                 job_name,
                                                                 errorReport.ReportMessage,
                                                                 signature
                                                                 )
        subject = "Check your job {} on the farm ".format(job.BatchName)

        # Set up re-used "action" functions.
        def suspend_task():
            RepositoryUtils.SuspendTasks(job, task_list)

        def suspend_job():
            RepositoryUtils.SuspendJob(job)

        # The error dict, containing the error string, custom message to send to the artist and the action performed
        # on the job.
        error_action_dict = {
            "CameraError": {  # Houdini error
                "error": "Error:       Unable to initialize rendering module with given camera",
                "message": "Can you check your camera selection? make sure to select the deepest "
                           "level of the camera node.",
                "action": suspend_job
            },
            "GeoError": {  # Houdini error
                "error": "Error:       Unable to save geometry for",
                "message": "Suggestion: check your frame range or your sources, and retry the task",
                "action": suspend_task
            },
            "IFDError": {  # Houdini error
                "error": "mantra: Unable to open IFD file",
                "message": "Suggestion: check your outputs paths or $JOB settings",
                "action": suspend_job
            },
            "TextureError": {  # htoa error
                "error": " [htoa.texture] Error converting texture",
                "message": " Can you disable the option Auto Generate TX Textures under the Arnold Node--->"
                           "Properties--->Textures Tab?",
                "action": suspend_task
            },
            "CookError": {  # Houdini error
                "error": "Error:       Cook error in input:",
                "message": "Suggestion: check your sources and caches for the failing frame, and retry the task",
                "action": suspend_task
            },
            "HipError": {  # Houdini error
                "error": "Error:       Unexpected end of .hip file",
                "message": "Try to resubmit your scene",
                "action": suspend_task
            },
            "3HourTimeout": {  # Timeout error
                "error": "The Worker did not complete the task before the Regular Task Timeout limit of 00d 03h 00m 00s",
                "message": "The priority has been lowered to 10, putting it at the bottom of the render queue."
                           "\n\nIf this is unexpected, please investigate what may be causing your scene to have such"
                           "high frame times."
                           "\nIf it is expected, please let your producer know before submitting a job with frame "
                           "times this high, so the wrangler can adjust settings to not let it timeout. "
                           "\n\nEvery 3hr timeout could waste as much as 20% of the farm's daily capacity!",
                "action": None  # actions are taken in the u_TimeoutErrorHandling.py script.
            },
            "MaxRAMUsed": { # houdini error
                "error": "Error: FailRenderException : Process returned non-zero exit code '9'",
                "message": "Your job has maxed out the RAM on our machines! This is usually caused by a particularly "
                           "heavy scene."
                           "\n\nSome settings have been automatically adjusted to help it get through, but it may "
                           "still have issues, so please look int making your scene lighter, Thank you.",
                "action": None  # actions are taken in the u_OnJobErrors.py script.
            }
        }

        # Send custom messages and actions for the job to the artist.
        for type_error in error_action_dict:
            # Check if the error message is in the error report
            if error_action_dict[type_error]["error"] in errorReport.ReportMessage:
                # Check that we haven't already emailed this person about this job.
                if not os.path.exists(temp_file_path) and email != "":
                    #  Find and execute the action associated with that error e.g. suspend job / task.
                    error_action = error_action_dict[type_error]["action"]
                    # if there is an action needed for this task, do it.
                    if error_action:
                        error_action()
                    # put the custom message into the message template from above.
                    message = message_template.replace("solution", error_action_dict[type_error]["message"])
                    # Send the email and create a temp file, so we don't send another.
                    u_DeadlineToolbox.send_email(subject=subject,
                                                 message=message,
                                                 addressee_list=[email]
                                                 )
                    with open(temp_file_path, 'w'):  # create the temp file
                        pass
