"""
Sets the priority of different types of jobs on submission.
This uses the set_prio function in u_DeadlineToolbox, which includes a flag for "automatic_raised_priority" if the prio
is raised above 50. This is so we do not spam production with emails using the Farm Notification System.
"""
from scripts.General import u_environment_utils
u_environment_utils.setup_environment()

from Deadline.Events import *
from Deadline.Scripting import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox
from datetime import datetime


def GetDeadlineEventListener():
    return OnSubmission()


def CleanupDeadlineEventListener(eventListener):
    eventListener.Cleanup()


class OnSubmission(DeadlineEventListener):

    def __init__(self):
        self.OnJobSubmittedCallback += self.OnJobSubmitted
        # Set up variables used / useful for multiple functions.
        self.eu_w_day_of_week = 0
        self.eu_w_hour_of_day = 0
        self.local_day_of_week = 0
        self.local_hour_of_day = 0
        self.prio_users = []
        # Low priority CG is determined from the job's pool.
        self.low_prio_cg = ["rnd", "cg_assets"]
        # CG renderers are determined from the jobs plugin.
        self.cg_renderers = ["Arnold", "Mantra"]
        # This is a list of strings to catch in the job name to determine if it is a QT maker job.
        self.qt_publish_list = ["CG AOV Publish",
                                "[QT2 Copy]",
                                "[QT2]",
                                "Publish"
                                ]

    def Cleanup(self):
        del self.OnJobSubmittedCallback

    def OnJobSubmitted(self, job):
        # Get london and local datetime.
        london_time = u_DeadlineToolbox.LondonDatetime()
        self.eu_w_day_of_week = london_time.get_day_of_week()
        self.eu_w_hour_of_day = london_time.get_hour_of_day()

        self.local_day_of_week = datetime.now().today().weekday()
        self.local_hour_of_day = datetime.now().hour

        # Get up to date prio users
        self.prio_users = RepositoryUtils.GetUserGroup("u_PriorityUsers")

        # Run the priority functions one after the other
        self.set_pdg_priority(job)
        self.set_client_send_priority(job)
        self.set_rsmb_priority(job)
        self.set_out_of_hours_nuke_priority(job)
        self.set_cg_renderer_priority(job)
        self.set_command_line_priority(job)
        self.set_element_lib_render_priority(job)
        self.temp_mm_location_limit_fix(job)
        self.prioritise_CG_tests(job)

    def set_pdg_priority(self, job):
        # We set PDG prio from the UI, so we can change it easily if needed.
        if job.JobPlugin == "PDGDeadline":
            u_DeadlineToolbox.set_prio(job, prio=int(self.GetConfigEntry('Priority PDG')))

    def set_client_send_priority(self, job):
        if "[Client]" in job.JobBatchName:
            u_DeadlineToolbox.set_prio(job, prio=95)

    def set_rsmb_priority(self, job):
        if "rsmb_render" in job.JobLimitGroups:
            u_DeadlineToolbox.set_prio(job, prio=95)

    def set_out_of_hours_nuke_priority(self, job):
        # for Nuke jobs we can use the normal site datetime. As we only render Nuke locally, so we only want to
        # raise prio out of the local office hours.
        if self.local_day_of_week < 5 and self.local_hour_of_day > 18:
            if job.JobPlugin == "Nuke":
                u_DeadlineToolbox.set_prio(job, prio=95)

    def set_cg_renderer_priority(self, job):
        if job.JobPlugin in self.cg_renderers:
            # Exclude prio users from default CG prio.
            if job.JobUserName not in self.prio_users:
                # jobs with more than 5 tasks should go on at prio 20 or 40.
                # NB: jobs that are 5 frames or less will be handled by self.prioritise_CG_tests()
                #     to set prio at between 75-95 depending on the task count.
                if job.JobTaskCount > 5:
                    if job.JobPool in self.low_prio_cg:
                        u_DeadlineToolbox.set_prio(job, prio=20)
                    else:
                        u_DeadlineToolbox.set_prio(job, prio=40)

    def set_command_line_priority(self, job):
        # we don't want to alter hermes job prios.
        if job.JobPlugin == "CommandLine" and job.JobPool != "hermes":
            # Set matchmove jobs to high prio to get them picked up asap.
            if job.JobPool == "mm":
                u_DeadlineToolbox.set_prio(job, prio=95)
            # For single frame jobs they're likely tests or other quick things, so prio them high.
            elif job.JobTaskCount == 1:
                u_DeadlineToolbox.set_prio(job, prio=95)
            # For low priority CG we want to lower it beyond normal CG prio.
            elif job.JobPool in self.low_prio_cg:
                u_DeadlineToolbox.set_prio(job, prio=20)
            # Other commandline jobs are likely CG (u_render), set it to cg prio (40)
            else:
                u_DeadlineToolbox.set_prio(job, prio=40)
            # Set QT / Publish jobs to 95 prio, so they're picked up ASAP.
            for qt_job in self.qt_publish_list:
                if qt_job in job.JobName:
                    u_DeadlineToolbox.set_prio(job, prio=95)

    def set_element_lib_render_priority(self, job):
        # Force Element Lib Render jobs to a lower prio than normal comps as they are usually massive frame
        # ranges and can block up the farm.
        if "Element Lib Render" in job.JobBatchName:
            u_DeadlineToolbox.set_prio(job, prio=40)

    def temp_mm_location_limit_fix(self, job):
        # todo: -------------------Temp MM site limit applying - Will be fixed when mm on config2----------------------
        if "mm" in job.JobPool:
            current_job_limits = job.JobLimitGroups
            limit_list = []
            for limit in current_job_limits:
                limit_list.append(limit)
            if "mtl" in job.JobSubmitMachine:
                limit_list.append("na_ne")
            elif "mtl" not in job.JobSubmitMachine:
                limit_list.append("eu_w")
            job.SetJobLimitGroups(limit_list)
            RepositoryUtils.SaveJob(job)

    def prioritise_CG_tests(self, job):
        # Auto prioritise CG renders under 5 frames, as these are usually tests.
        # Stagger the prio to help the single frames through first etc..
        u_render = u_DeadlineToolbox.is_job_u_render(job)
        plugin_list = ["Houdini", "Arnold", "Mantra", "MayaCmd"]
        if u_render or job.JobPlugin in plugin_list:
            if job.JobTaskCount > 5:
                return
            if job.JobTaskCount == 1:
                u_DeadlineToolbox.set_prio(job, prio=95)
            elif job.JobTaskCount == 2:
                u_DeadlineToolbox.set_prio(job, prio=90)
            elif job.JobTaskCount == 3:
                u_DeadlineToolbox.set_prio(job, prio=85)
            elif job.JobTaskCount == 4:
                u_DeadlineToolbox.set_prio(job, prio=80)
            elif job.JobTaskCount == 5:
                u_DeadlineToolbox.set_prio(job, prio=75)
            print("Setting priority to {} as the job has {} task(s). "
                  "This helps test renders get through quicker.".format(job.JobPriority, job.JobTaskCount))
