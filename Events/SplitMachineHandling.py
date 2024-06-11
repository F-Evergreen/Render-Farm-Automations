#!/usr/bin/python

"""
This file combines the automatic disabling and re-enabling of the split machine scripts in u_SplitMachineModify.py
It needs to be run AFTER the u_ForceGroup.py script within deadline. Otherwise the "split_machines" group will not
have been applied yet for this script to work.
"""

from Deadline.Events import *
from Deadline.Scripting import *
from System.Collections.Specialized import *
from scripts.General.u_SplitMachineModify import u_SplitMachineModify


def GetDeadlineEventListener():
    return SplitMachineHandling()


def CleanupDeadlineEventListener (eventListener):
    eventListener.Cleanup()
 

class SplitMachineHandling(DeadlineEventListener):

    # Set up the event callbacks here
    def __init__(self):
        self.OnJobSubmittedCallback += self.OnJobSubmitted
        self.OnJobFinishedCallback += self.OnJobFinished
        self.OnJobFailedCallback += self.OnJobFailed
        self.OnJobSuspendedCallback += self.OnJobSuspended
        self.OnJobDeletedCallback += self.OnJobDeleted
        self.OnJobRequeuedCallback += self.OnJobRequeued

    def Cleanup(self):
        del self.OnJobSubmittedCallback
        del self.OnJobFinishedCallback
        del self.OnJobFailedCallback
        del self.OnJobSuspendedCallback
        del self.OnJobDeletedCallback
        del self.OnJobRequeuedCallback

    def OnJobSubmitted(self, job):
        """
        This automatically runs u_SplitMachineModify.reset_splits() if a Houdini or Maya job is submitted to the farm
        and one of the split workers is disabled. This helps with Houdini and Maya jobs as they're light and can run on
        split machines.
        """
        # Set up a variable in case we need to change the split machine group name
        split_machine_group = "split_machines"
        # Get the nuke limit to check if the Big Red Button is active
        current_nuke_limit_group = RepositoryUtils.GetLimitGroup("eu_w_nuke render license limit", True)
        # This is the DENY list
        current_nuke_limit_group_workers = current_nuke_limit_group.LimitGroupListedSlaves
        # Check to see if render27-01 is enabled
        worker_info = RepositoryUtils.GetSlaveSettings("render27-01", True)
        worker_status = worker_info.SlaveEnabled
        # Check to see if one of the epic machines is already in the Nuke limit, if so we dont want to adjust it until
        # we reset the "big red button" - which stops all CG and allows nuke jobs to render on the epic machines.
        if "render42" in current_nuke_limit_group_workers:
            # If a job is submitted with one of these plugins get the worker status of render27-01
            if job.JobGroup == split_machine_group:
                # If render27-01 is disabled, run the script to enable the splits and remove them from the
                # nuke limit
                if not worker_status:
                    u_SplitMachineModify.reset_splits()

    # Here we are checking for if a job, finishes, fails or is suspended, deleted or requeued...
    # Then checking if we need to run the script.
    def OnJobFinished(self, job):
        self.on_job_complete(job)

    def OnJobFailed(self, job):
        self.on_job_complete(job)

    def OnJobSuspended(self, job):
        self.on_job_complete(job)

    def OnJobDeleted(self, job):
        self.on_job_complete(job)

    def OnJobRequeued(self, job):
        self.on_job_complete(job)

    def on_job_complete(self, job):

        """
        When a "split_machines" job is finished, this script will check to see if there are any more jobs of the same
        type on the farm. If not it will run the u_SplitMachineModify.disable_splits() function. This helps with
        efficiency to make sure we have the most machines available for each job type.
        """
        # Set up a variable in case we need to change the split machine group name
        split_machine_group = "split_machines"
        # Get the nuke limit to check if the Big Red Button is active
        current_nuke_limit_group = RepositoryUtils.GetLimitGroup("eu_w_nuke render license limit", True)
        # This is the DENY list
        current_nuke_limit_group_workers = current_nuke_limit_group.LimitGroupListedSlaves
        # Get all the active jobs on the farm
        all_active_jobs = RepositoryUtils.GetJobsInState("Active")
        # Check if the current job group is "split_machines" - a job we want to potentially run the script for.
        if job.JobGroup == split_machine_group:
            # Set up a bool to run the script if the CURRENT job's group is "split_machines"
            run_script = True
            # Check to see if BRB is active
            brb_active = False
            if "render42" not in current_nuke_limit_group_workers:
                # If it is we don't want to run the script or check for any more split machine jobs
                run_script = False
                brb_active = True
            # If the BRB is not active, check every active (queued and rendering) job to see if we have more
            # "split_machine" jobs
            if not brb_active:
                for active_job in all_active_jobs:
                    # if an active job's group is "split_machines", we still need them to be split, so don't run the
                    # script. If we've found this then break out of the loop.
                    if active_job.JobGroup == split_machine_group:
                        run_script = False
                        break
            # If we've got through all of the jobs and none of them have the "split_machine" group, Run the script to
            # disable the splits and add the machines to be able to render nuke jobs
            if run_script:
                u_SplitMachineModify.disable_splits()
