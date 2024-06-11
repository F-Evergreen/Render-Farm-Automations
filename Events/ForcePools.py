"""
On Submission Event- Force Pools -if the pool is none assign to backup pool

Copyright Union VFX 2020

"""

from Deadline.Events import *
from Deadline.Scripting import *


def GetDeadlineEventListener():
    return OnSubmission()


def CleanupDeadlineEventListener(eventListener):
    eventListener.Cleanup()


class OnSubmission(DeadlineEventListener):

    # Set up the event callbacks here
    def __init__(self):
        self.OnJobSubmittedCallback += self.OnJobSubmitted

    def Cleanup(self):
        del self.OnJobSubmittedCallback

    def OnJobSubmitted(self, job):
        #todo replace this with project_name JobExtraInfoKEyValue projectName = job.GetJobExtraInfoKeyValue("project_name")
        # Get name of the department that usually correspond to the project name
        department = str(job.JobDepartment)
        # Get name of all pools
        all_pools = str(ClientUtils.ExecuteCommandAndGetOutput("-GetPoolNames"))
        # Get path of the submitting scene
        scene_file = job.GetJobPluginInfoKeyValue("SceneFile")
        # If pool is None try to get the department name from department field
        if job.JobPool == "none":
            if department != "" and department in all_pools:
                job.JobPool = department
                RepositoryUtils.SaveJob(job)
            # If pool department field is empty try to get from Scene file for Houdini and Mantra
            elif job.JobPlugin == "Houdini" or job.JobPlugin == "Mantra":
                project = scene_file.split("/")[3]
                job.JobPool = project
                RepositoryUtils.SaveJob(job)
                print ("The pool has been changed to", project)
            # If still no luck assign to backup pool
            else:
                job.JobPool = "backup_pool"
                RepositoryUtils.SaveJob(job)
        if job.JobPlugin == "Houdini" and not "mtl" in job.JobSubmitMachine:
            job.JobSecondaryPool = "houdini"
            RepositoryUtils.SaveJob(job)

        # Set qt jobs to qt secondary pool so we can set qt jobs to go to machines that are too poor to render
        # regular Nuke jobs. This means we can leave the primary pool as the project.
        qt_list = ["QT", "RenderMovFile", "Movie"]
        for qt_string in qt_list:
            if qt_string in job.JobName:
                job.JobSecondaryPool = "qt"
                RepositoryUtils.SaveJob(job)
