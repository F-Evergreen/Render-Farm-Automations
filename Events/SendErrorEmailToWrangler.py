"""

On Error Event- Send custom message to wranglers when job is erroring

Copyright Union VFX 2020

"""

import os
from Deadline.Events import *
from System.Collections.Specialized import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox


def GetDeadlineEventListener():
    return OnError()


def CleanupDeadlineEventListener(deadlinePlugin):
    deadlinePlugin.cleanup()


class OnError(DeadlineEventListener):

    def __init__(self):

        self.OnJobErrorCallback += self.OnJobError

    def cleanup(self):

        del self.OnJobErrorCallback

    def OnJobError(self, job, task, errorReport):

        user = job.JobUserName
        job_name = job.JobName
        error = errorReport.ReportMessage
        farm_email_path = "/Volumes/resources/pipeline/logs/deadline/farm_emails"
        # temp file info. Use these files to verify if an email has already been sent.
        temp_file_path = u_DeadlineToolbox.create_temp_txt_file_path(job, "farm_emails")

        # setup body of the email
        message = "The job {} \n from {} is erroring:\n \n {} \n Check the farm " \
                  "\n \n This is an automated message, if you need help please contact wrangler@unionvfx.com".format(
            job_name, user.capitalize(), error)

        # Check if there is a temp file already for this job. If not send the email and create the file.
        if not os.path.exists(temp_file_path):
            u_DeadlineToolbox.send_email(subject="Check the farm",
                                         message=message,
                                         addressee_list=["wrangler@unionvfx.com"]
                                         )
            with open(temp_file_path, 'w'):
                pass
        # If there is a temp file, don't send the email.
        else:
            pass
        # Cleanup the temp files.
        u_DeadlineToolbox.cleanup_files(path=farm_email_path)
