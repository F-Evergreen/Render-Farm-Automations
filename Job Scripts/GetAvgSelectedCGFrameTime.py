from __future__ import absolute_import

from Deadline.Scripting import *
from DeadlineUI.Controls.Scripting.DeadlineScriptDialog import DeadlineScriptDialog


def __main__():
    # type: () -> None
    """
    Monitor based job script get the average frame time of multiple selected CG jobs.
    Useful for projecting future render times.
    """
    selected_jobs = MonitorUtils.GetSelectedJobs()
    cg_plugins = ["CommandLine", "Arnold"]

    if selected_jobs:
        total_job_render_times = []
        total_frames = 0
        for job in selected_jobs:
            if job.JobPlugin in cg_plugins:
                taskCollection = RepositoryUtils.GetJobTasks(job, True)
                tasks = taskCollection.TaskCollectionTasks
                total_frames += job.JobCompletedTasks
                for task in tasks:
                    task_render_time = task.TaskRenderTime
                    # No idea what this number is, but it occurs and throws the calculation way off.
                    if int(task_render_time.TotalSeconds) != 922337203685:
                        total_job_render_times.append(int(task_render_time.TotalSeconds))

        avg_task_time = int((sum(total_job_render_times) / 60) / total_frames)
        print("Total frames: ", total_frames)
        print("Total render time in minutes: ", (sum(total_job_render_times) / 60))
        print("Average task time of CG job(s): ", avg_task_time)
