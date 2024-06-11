"""
On Submission Event- Force Groups - Used for houdini simulations at the moment

Copyright Union VFX 2021

"""


from Deadline.Events import *
from Deadline.Scripting import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox


def GetDeadlineEventListener():
    return OnSubmission()


def CleanupDeadlineEventListener(eventListener):
    eventListener.Cleanup()


class OnSubmission(DeadlineEventListener):

    # Set up the event callbacks here
    def __init__(self):
        # Set up datetime variables to be changed when the event is called.
        self.day_of_week = 0
        self.hour_of_day = 0
        self.job_limit_list = []
        # This dict contains CG plugins / limits and the groups we want to put them into.
        self.default_CG_group_dict = {
            "MayaCmd": "split_machines",
            "Arnold": "251gb",
            "Mantra": "251gb",
            "arnold license limit": "251gb"
        }
        self.qt_list = ["QT", "RenderMovFile", "Movie"]
        # For PDG and CommandLine jobs they can use many renderers, so win instead discern the plugin they're
        # using from the limits on the job. Then set the group based on that limit.
        self.pdg_plugin_group_dict = {
            "houdini": "split_machines",
            "arnold license limit": "128up"
        }
        self.OnJobSubmittedCallback += self.OnJobSubmitted

    def Cleanup(self):
        del self.OnJobSubmittedCallback

    def OnJobSubmitted(self, job):
        # Get the current time when the event is called, so we can do things inside and outside of office hours.
        # Get London time as we are currently only rendering CG in London. This is as the vast majority of our render
        # power is located in London for now.
        london_time = u_DeadlineToolbox.LondonDatetime()
        self.day_of_week = london_time.get_day_of_week()
        self.hour_of_day = london_time.get_hour_of_day()
        # get the current job limits
        self.job_limit_list = u_DeadlineToolbox.get_job_limits_as_list(job)

        # find the type of job, and set it to the right group
        if any(qt_string in job.JobName for qt_string in self.qt_list):
            self.set_qt_job_group(job)
        elif job.JobPlugin in self.default_CG_group_dict:
            self.set_default_cg_groups(job)
        elif job.JobPlugin == "PDGDeadline":
            self.set_pdg_groups(job)
        # This is for u_render jobs.
        elif job.JobPlugin == "CommandLine":
            if "arnold license limit" in self.job_limit_list:
                self.set_default_cg_groups(job)
        elif job.JobPlugin == "Houdini":
            self.set_houdini_groups(job)
        else:
            self.set_other_job_groups(job)

    def set_default_cg_groups(self, job):
        # If we are in LDN office hours, set up groups for CG jobs using the default dict above.
        if self.day_of_week < 5 and 19 > self.hour_of_day > 8:
            if job.JobPlugin in self.default_CG_group_dict:
                job.JobGroup = self.default_CG_group_dict[job.JobPlugin]
            elif "arnold license limit" in self.job_limit_list:
                job.JobGroup = "251gb"
            # Save the changes on the job
            RepositoryUtils.SaveJob(job)

    def set_pdg_groups(self, job):
        # Set the groups of CommandLine and PDG Jobs based on limits set on the job.
        for limit in self.job_limit_list:
            if limit in self.pdg_plugin_group_dict:
                job.JobGroup = self.pdg_plugin_group_dict[limit]
                # Save the changes on the job
                RepositoryUtils.SaveJob(job)
                break

    def set_houdini_groups(self, job):
        # if the job plugin is Houdini, the task count is 1 and the frames per task are more than 1
        # - in most scenarios it's a simulation
        if job.JobPlugin == "Houdini":
            if job.JobTaskCount == 1 and job.JobFramesPerTask > 1:
                # assign the group sim to the job so that it can get the best machines for that
                job.JobGroup = "sims"
                # Set them to only allow 1 error on them so we avoid repeated renders of heavy erroring sims
                job.JobOverrideTaskFailureDetection = True
                job.JobFailureDetectionTaskErrors = 1
            # if its not a simulation, put it in the split_machines group for maximum houdini license efficiency
            else:
                if not "mtl" in job.JobSubmitMachine:
                    job.JobGroup = "split_machines"
            # save the job
            RepositoryUtils.SaveJob(job)

    def set_other_job_groups(self, job):
        # Client submission nuke jobs tend to get stuck on Union machines, therefore as a temporary fix it would be
        # useful to make sure they only go on render nodes for now.
        if job.JobPlugin == "Nuke" and "[Client]" in job.JobBatchName:
            job.JobGroup = "render_nodes"

        # temp fix for cg aov publishes failing on workstations. It may be beneficial to leave python jobs to be on
        # the render nodes, as we can more confidently know that they will have the correct python compatibility.
        if job.JobPlugin == "Python":
            job.JobGroup = "render_nodes"

        # Save the changes on the job
        RepositoryUtils.SaveJob(job)

    def set_qt_job_group(self, job):
        # Set qt jobs to qt group and secondary pool so we can set qt jobs to go to machines that are too poor to
        # render regular Nuke jobs without them rendering normal Nuke jobs.
        job.JobGroup = "qt"
        job.JobSecondaryPool = "qt"
        # Save the changes on the job
        RepositoryUtils.SaveJob(job)
