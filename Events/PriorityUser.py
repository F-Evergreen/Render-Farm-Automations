"""
Force priority if the user is in a specific user group

Copyright Union VFX 2020

"""

from Deadline.Events import *
from Deadline.Scripting import *

def GetDeadlineEventListener():
    return OnSubmission()

def CleanupDeadlineEventListener (eventListener):
    eventListener.Cleanup()


class OnSubmission(DeadlineEventListener):

    # Set up the event callbacks here
    def __init__(self):
        self.OnJobSubmittedCallback += self.OnJobSubmitted

    def Cleanup(self):
        del self.OnJobSubmittedCallback

    def OnJobSubmitted(self, job):

        # todo Add the ability to add multiple users from UI

        # Get The User
        user = job.JobUserName
        # Get the User if set in UI
        manual_user = self.GetConfigEntry("User")
        # Add Manual user to group U_Priority_User
        RepositoryUtils.AddUsersToUserGroups([manual_user], ["u_PriorityUsers"])
        # Get All groups
        groups = RepositoryUtils.GetUserGroupsForUser(user) # get the user assigned groups
        # Get the machine limit from the config
        machine_limit = int(self.GetConfigEntry("Machine Limit"))
        # Get the job id
        job_id = job.JobId
        # if user in the priority Group
        for group in groups:
            if group == "u_PriorityUsers":
                # Set Priority Value from UI or default 95
                job.JobPriority = self.GetIntegerConfigEntryWithDefault("Priority", 95)
                RepositoryUtils.SaveJob(job)
                # Only set the machine limit if it isnt 0 in the UI
                if machine_limit:
                    RepositoryUtils.SetMachineLimitMaximum(job_id, machine_limit)



