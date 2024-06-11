from __future__ import absolute_import

from Deadline.Scripting import MonitorUtils
from DeadlineUI.Controls.Scripting.DeadlineScriptDialog import DeadlineScriptDialog


def __main__():
    # type: () -> None
    """Monitor based job script to copy selected job batch names
    to the system clipboard."""
    selected_jobs = MonitorUtils.GetSelectedJobs()

    if selected_jobs:
        job_batch_names = []
        for job in selected_jobs:
            if job.JobBatchName not in job_batch_names:
                job_batch_names.append(job.JobBatchName)
        str_job_batch_names = '\n'.join(job_batch_names)

        script_dialog = DeadlineScriptDialog()
        script_dialog.CopyToClipboard(str_job_batch_names)
