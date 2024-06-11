#! /usr/bin/python
"""

Script to handle when an error happens with .ass file generation.

More often we can requeue the task and it will generate it properly, so in this script we do that automatically.

If the file still isnt correct, we fail JUST the task so the rest of the job can render as normal.

"""

from Deadline.Events import *
from Deadline.Scripting import *
import re
from System.Collections.Specialized import *


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

        self.ass_error_handling(errorReport, job)

    def ass_error_handling(self, errorReport, job):

        """
        This function aims to pend/fail just the TASK for specific errors.

        Then if the error hasn't occurred before, it calls the auto_requeue_ass_file function to requeue the ass file.
        If this doesn't work, it just fails the task.

        This is useful for errors that are'nt fatal to the job. Aiming to get most of the jobs through out of office
        hours.

        Args:
            errorReport:
            job:

        Returns:
        """

        # Set up the list of errors to look for
        fail_task_errors = [".*\[ass\] can't read in.*",
                            ".*\[ass\] line.*"]
        # Loop through tasks and errors
        for regex_pattern in fail_task_errors:
            match_result = re.match(regex_pattern, errorReport.ReportMessage)
            if match_result:
                # Set up a list of tasks to fail
                tasks_to_fail = []
                # Set up a list of tasks to pend
                tasks_to_pend = []
                # Get the task ID of the task with the error
                job_task_id = str(errorReport.ReportTaskID)
                # Get the tasks on the job
                job_task_collection = RepositoryUtils.GetJobTasks(job, True)
                job_tasks = job_task_collection.TaskCollectionTasks
                job_batch = job.JobBatchName
                # find the task object for the task with the error
                for task in job_tasks:
                    if task.TaskId == job_task_id:

                        # only fail the task if we have already tried to pend and requeue the .ass file. FYI the error
                        # count will always be at least 1 when this gets run as it gets run on error.
                        # we want to fail the task if the error count is 2 or more
                        if task.TaskErrorCount > 1:
                            # Add the erroring task object to the list of tasks_to_fail
                            tasks_to_fail.append(task)
                            # break as we don't need to look for more tasks
                            break

                        # If it is a job which is not part of a batch, there is no corresponding maya / houdini task
                        # therefore without this check it will requeue every matching task id, which we dont want.
                        # This check stops this.
                        elif not job_batch:
                            # Add the erroring task object to the list of tasks_to_fail
                            tasks_to_fail.append(task)
                            # break as we don't need to look for more tasks
                            break

                        else:
                            # Add the task to the tasks_to_pend list
                            tasks_to_pend.append(task)
                            # break as we don't need to look for more tasks
                            break

                # only try to requeue the ass file if the error count is 0, to avoid multiple requeueings.
                if tasks_to_fail:
                    print("Failing this task as there is more than 1 error on it, assuming the .ass file requeue didn't"
                          "work, or there are other errors to take into account.")
                    RepositoryUtils.FailTasks(job, tasks_to_fail)
                if tasks_to_pend:
                    print(
                        "Found a .ass file error! Pending this task and attempting to requeue the .ass file generation"
                        "task.")
                    RepositoryUtils.PendTasks(job, tasks_to_pend)
                    self.auto_requeue_ass_file(job, job_task_id)

        # todo: get the job dependencies and instead modify the job that the erroring job is dependent on

    def auto_requeue_ass_file(self, job, job_task_id):

        """
        This function aims to automatically requeue the corresponding Maya .ass file, when the
        "[ass] can't read" error occurs.

        Args:
            job:
            job_task_id:
        Returns:

        """
        # Get the batch name of the job with the error.
        job_batch_name = job.JobBatchName
        # Get a list of all the jobs on the farm
        all_jobs = RepositoryUtils.GetJobs(True)
        # Set up lists for later
        batch_jobs_found = []
        jobs_to_requeue = []
        # The list of plugins which could create .ass files
        plugins_to_requeue = ["MayaCmd", "Houdini"]
        # Loop through all the jobs on the farm and find jobs with the batch name in the job name.
        # This essentially finds all the jobs in the batch.
        for test_job in all_jobs:
            if job_batch_name in test_job.JobName:
                # Put those jobs in the batch_jobs_found list
                batch_jobs_found.append(test_job)
        # Loop through the list of jobs we found and compare the plugin with the plugins_to_requeue list.
        for batch_job in batch_jobs_found:
            if batch_job.JobPlugin in plugins_to_requeue:
                # Put the jobs with those plugins in the jobs_to_requeue list.
                jobs_to_requeue.append(batch_job)
        # Loop through every job in this list. This accounts for Houdini jobs where multiple jobs in the batch could
        # have created the .ass file. We will requeue them all as the blade time for .ass files is usually under
        # 1 min.
        for requeue_job in jobs_to_requeue:
            # Get all the tasks for the job
            requeue_job_task_collection = RepositoryUtils.GetJobTasks(requeue_job, True)
            requeue_job_tasks = requeue_job_task_collection.TaskCollectionTasks
            # Set up a list of tasks to requeue
            task_to_requeue = []
            # Loop through the tasks looking for taks with the same Task ID as the Error's Task ID
            for requeue_job_task in requeue_job_tasks:
                if requeue_job_task.TaskId == job_task_id:
                    # Add the task to the list of tasks_to_requeue
                    task_to_requeue.append(requeue_job_task)
                    print(
                        "Requeing the .ass file generation task: {} from job: {}.".format(task_to_requeue,
                                                                                          requeue_job)
                         )
                    # Break out of the loop as we don't need to keep checking for tasks.
                    break
            # If we found tasks to requeue find out the job's status as we may need to resume the task first.
            if task_to_requeue:
                if requeue_job.JobStatus == "Failed":
                    print(
                        "Job status is {}, resuming the task before requing the corresponding {} job task".format(
                            requeue_job.JobStatus,
                            requeue_job.JobPlugin)
                    )
                    RepositoryUtils.ResumeFailedTasks(requeue_job,
                                                      task_to_requeue
                                                      )
                    RepositoryUtils.RequeueTasks(requeue_job,
                                                 task_to_requeue
                                                 )
                elif requeue_job.JobStatus == "Suspended":
                    print(
                        "Job status is {}, resuming the task before requing the corresponding {} job task".format(
                            requeue_job.JobStatus,
                            requeue_job.JobPlugin
                        )
                    )
                    RepositoryUtils.ResumeTasks(requeue_job,
                                                task_to_requeue
                                                )
                    RepositoryUtils.RequeueTasks(requeue_job,
                                                 task_to_requeue
                                                 )
                # If the status is "Complete" (most likely), it will requeue the task.
                else:
                    RepositoryUtils.RequeueTasks(requeue_job,
                                                 task_to_requeue
                                                 )
            # In some cases the .ass file is made locally or in  a different format. E.g. a job with 10 tasks
            # creating the .ass files for a job with 100 tasks. In this case it may not find the task so will
            # instead print the statement below and likely requeue and fail due to it having more than 1 error.
            if not task_to_requeue:
                print("No match found for task ID, failing the task on next run through.")
