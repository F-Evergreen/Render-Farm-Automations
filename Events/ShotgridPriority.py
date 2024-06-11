"""
This event script handles the setting of priority based on shotgrid data.
It is in its own file as we need to be able to control it in the event of issues and so that it doesn't impact other
scripts. e.g. when it was in the u_ForcePriority it was causing inconsistencies with connecting to SG.

"""
from Deadline.Events import *
from Deadline.Scripting import *
from scripts.General import u_environment_utils
u_environment_utils.setup_environment()


def GetDeadlineEventListener():
    return OnSubmission()


def CleanupDeadlineEventListener(eventListener):
    eventListener.Cleanup()


class OnSubmission(DeadlineEventListener):

    def __init__(self):
        self.OnJobSubmittedCallback += self.OnJobSubmitted

    def Cleanup(self):
        del self.OnJobSubmittedCallback

    def OnJobSubmitted(self, job):
        # grab the task_id from the job
        sg_task_id = job.GetJobExtraInfoKeyValue("task_id")
        # if job does not have a shotgrid task_id, skip (e.g. hermes jobs)
        if sg_task_id:
            from scripts.General.u_ShotgridUtils import u_SetShotgridPrio
            u_SetShotgridPrio.set_shotgrid_prio(job)
        # This checks the prio of the pdg monitor job and sets it to that. This is needed as the spawned jobs don't have
        # SG Task IDs, so don't get the prio set from SG.
        # I get the prio from the existing farm job which has picked up the prio instead of getting it from SG again as
        # we should really limit the amount SG interacts with the farm as this can cause issues.
        if not sg_task_id:
            if job.JobPlugin == "PDGDeadline":
                # Get the default pdg prio from the u_ForcePriority.param
                force_prio_config = RepositoryUtils.GetEventPluginConfig("u_ForcePriority")
                default_pdg_prio = force_prio_config.GetIntegerConfigEntry("Priority PDG")
                # Check if the pdg job submitted is the default pdg prio set from the deadline UI.
                if job.JobPriority == default_pdg_prio:
                    job_batch_name = job.JobBatchName
                    all_jobs = RepositoryUtils.GetJobsInState("Active")
                    for farm_job in all_jobs:
                        if farm_job.JobBatchName == job_batch_name:
                            batch_prio = farm_job.JobPriority
                            job.JobPriority = batch_prio
                            RepositoryUtils.SaveJob(job)
                            break
