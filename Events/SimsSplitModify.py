"""
When a sim is submitted to the farm and starts rendering, we disable the OTHER splits than the one it picked up on.
e.g. if it picked up on render37-01, we disable render37.

In theory this has two advantages, the sim completes quicker as it can use the whole machine. And it could help with
license issues. (sims have been causing me a headache in regards to this)

When the sim completes, it re-enables the other splits we disabled previously.

IMPORTANT: This needs to run AFTER u_ForceGroup.py, as otherwise the job's group will not be set to sims, which we need
to check for this script to function

"""

from Deadline.Events import *
from Deadline.Scripting import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox


def GetDeadlineEventListener():
    return SimsSplitModify()


def CleanupDeadlineEventListener(eventListener):
    eventListener.Cleanup()


class SimsSplitModify(DeadlineEventListener):

    def __init__(self):
        # Set up the event callbacks we will be invoking.
        self.OnJobStartedCallback += self.OnJobStarted
        self.OnJobFinishedCallback += self.OnJobFinished
        self.OnJobFailedCallback += self.OnJobFailed
        self.OnJobDeletedCallback += self.OnJobDeleted
        self.OnJobSuspendedCallback += self.OnJobSuspended
        self.OnJobRequeuedCallback += self.OnJobRequeued

        # Get London time as we set all of our automation using that at the moment
        self.london_time = u_DeadlineToolbox.LondonDatetime()
        self.day_of_week = self.london_time.get_day_of_week()
        self.hour_of_day = self.london_time.get_hour_of_day()
        # Get all the workers in the "sims" group on Deadline
        self.sims_render_group = u_DeadlineToolbox.get_slave_names_in_group("sims")
        # Set up a variable to store the worker the sim is rendering on
        self.sim_worker = ""
        # Set up a list of workers to enable or disable, depending on when we run this
        self.workers_to_modify = []
        # List of workers to ignore altering
        self.workers_to_ignore = ["render35", "render35-01", "render36", "render36-01"]
        # If we are in working hours we want to leave 35 and 36's split disabled, as we also use them for nuke, which
        # doesnt play nice with splits.
        if self.day_of_week < 5 and 19 > self.hour_of_day > 8:
            for worker in self.workers_to_ignore:
                self.sims_render_group.remove(worker)

    def Cleanup(self):
        del self.OnJobStartedCallback
        del self.OnJobFinishedCallback
        del self.OnJobFailedCallback
        del self.OnJobDeletedCallback
        del self.OnJobSuspendedCallback
        del self.OnJobRequeuedCallback
    def worker_processing(self, job, worker_state=None):
        # Get the worker for the sim
        job_task_collection = RepositoryUtils.GetJobTasks(job, True)
        for task in job_task_collection.TaskCollectionTasks:
            # theres only one task for a sim so we dont need to worry about getting all the tasks here.
            self.sim_worker = task.TaskSlaveName
        # Get Slave info for the worker...
        slave_info = [RepositoryUtils.GetSlaveInfo(self.sim_worker, True)]
        # ...so we can get the machine name ie. just "render38" without the "-XX"
        sim_machine_name = SlaveUtils.GetMachineNames(slave_info)
        # Because this returns a list, get a string of the one item in the list to use later
        sim_rendering_on = ""
        for machine_name in sim_machine_name:
            sim_rendering_on = machine_name
        # Find all the splits of the worker rendering the sim and add them to the list of workers to disable.
        for worker in self.sims_render_group:
            if sim_rendering_on in worker:
                self.workers_to_modify.append(worker)
        # Modify the associated workers
        for worker_to_modify in self.workers_to_modify:
            # Ignore if it is the same worker the sim is running on as this will always be enabled.
            if not worker_to_modify == self.sim_worker:
                u_DeadlineToolbox.modify_worker(worker_to_modify, set_worker_state=worker_state)

    # When a sim starts rendering, disable the rest of the splits for that machine.
    def OnJobStarted(self, job):
        if job.JobGroup == "sims":
            init = SimsSplitModify()
            init.worker_processing(job, worker_state=False)

    def OnJobFinished(self, job):
        self.on_job_completed(job)

    # If a sim fails, is suspended, deleted or requeued... still re-enable the splits
    def OnJobFailed(self, job):
        self.on_job_completed(job)

    def OnJobSuspended(self, job):
        self.on_job_completed(job)

    def OnJobDeleted(self, job):
        self.on_job_completed(job)

    def OnJobRequeued(self, job):
        self.on_job_completed(job)

    # When the job has finished re-enable the splits
    def on_job_completed(self, job):
        if job.JobGroup == "sims":
            init = SimsSplitModify()
            init.worker_processing(job, worker_state=True)
