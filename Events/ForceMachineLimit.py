"""
On Submission Event- Force Limits - Assign different limits based on the job plugin type

Copyright Union VFX 2021

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

        # MACHINE LIMIT
        # Get plugin for current job
        plugin = job.JobPlugin
        # List of Plugins we currently use the the most
        plugin_list = ['Nuke', 'MayaCmd', 'Arnold', 'Mantra', 'Houdini']
        prio_users = RepositoryUtils.GetUserGroup("u_PriorityUsers")
        # If the job plugin is in our plugin list
        if plugin in plugin_list:
            # Get the value of the Limit from the UI - the name of the Limit field is set in the param file
            limit_value = int(self.GetConfigEntry("Limit_{}".format(plugin)))
            # only alter the machine limit if the limit value from the ui isnt 0
            if limit_value:
                # check if the user is not in the u_priorityuser group, we don't want to limit these users
                if job.JobUserName not in prio_users:
                    # We don't want to limit client sends
                    if "[Client]" not in job.JobBatchName:
                        # Set the machine limit to the job based on the value set from the UI
                        RepositoryUtils.SetMachineLimitMaximum(job.JobId, limit_value)
                # For prio users, if we're setting a global machine limit set the value for those jobs to be 2 x the limit
                # of other jobs
                else:
                    prio_limit_value = limit_value * 2
                    RepositoryUtils.SetMachineLimitMaximum(job.JobId, prio_limit_value)

        # LICENSE LIMIT
        # Make sure houdini jobs have license assigned
        job_plugin = job.JobPlugin
        limits = ["houdini"]
        if job_plugin == "Houdini":
            job.SetJobLimitGroups(limits)
            RepositoryUtils.SaveJob(job)
