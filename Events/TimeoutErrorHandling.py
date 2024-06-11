#! /usr/bin/python
"""
This Event occurs when a job times out due to hitting the timeouts we've set
These timeout values are set in the OnJobSubmitted function and in the Deadline UI

When a timeout occurs this also handles what actions we take.
"""
from Deadline.Events import *
from Deadline.Scripting import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox
from scripts.General.u_FarmNotificationSystem import u_FarmNotificationSystem
import os
from System.Collections.Specialized import *


def GetDeadlineEventListener():
    return TimeoutErrorHandling()


def CleanupDeadlineEventListener(deadlinePlugin):
    deadlinePlugin.Cleanup()


class TimeoutErrorHandling(DeadlineEventListener):

    def __init__(self):

        self.OnJobSubmittedCallback += self.OnJobSubmitted
        self.OnJobErrorCallback += self.OnJobError

        # CG renderers are determined from the jobs plugin.
        self.cg_renderers = ["Arnold", "Mantra"]
        # IFD/.ass gen jobs are determined from the job's plugin.
        self.ass_ifd_gens = ["Houdini", "MayaCmd"]
        # This is a list of job plugins which are not CG renderers for timeouts we still want to set.
        self.non_cg_renderer_plugin_list = ["MayaCmd", "Houdini", "Nuke"]
        # This list will be populated when the job's limits are determined. This is then used when determining if
        # a CommandLine job is rendering CG and so needs a timeout set.
        self.limit_groups = []
        # These are used for the FNS and populated if needed.
        self.parameters_changed = ""
        self.job_params_changed_reason = ""
        self.job_params_changed_artist_suggestion = ""
        self.job_params_changed_prod_suggestion = ""

    def Cleanup(self):

        del self.OnJobSubmittedCallback
        del self.OnJobErrorCallback

    def OnJobSubmitted(self, job):
        # Get the limit groups of a job, this helps with u_render commandline arnold jobs
        self.limit_groups = u_DeadlineToolbox.get_job_limits_as_list(job)
        self.set_timeouts(job)

    def OnJobError(self, job, task, errorReport):
        # Get the limit groups of a job, this helps with u_render commandline arnold jobs
        self.limit_groups = u_DeadlineToolbox.get_job_limits_as_list(job)
        self.timeout_error_handling(errorReport, job)

    def set_timeouts(self, job):
        """
        1. Set [Client] Nuke jobs to have a max task time of 3 minutes. This is because they can get stuck and never
        should take longer than 3 minutes. When it reaches 3 minutes, it will error and requeue.
        2. Set regular Nuke jobs to have a max task time of 15 minutes. Upon which it will error and change frames per
        task and concurrent tasks to 1 as well as limit it to max 4 machines in the timeout_error_handling function.
        Only set these during work hours, as outside of work hours they should have priority and be unrestricted
        3. Set CG jobs to have a max task time out 3 hours. When that timeout occurs, it will be picked up in the
        timeout_error_handling function and handled in there.
        4. Set Houdini (not sims) and Maya jobs to have a timeout of 10 minutes, then set concurrent tasks to 1
        """

        # Set a default max time, 0 = infinity
        timeout_in_mins = 0
        # Get Config Entry values set in deadline UI to use in the script
        nuke_timeout = int(self.GetConfigEntry("Nuke Timeout"))
        maya_and_houdini_timeout = int(self.GetConfigEntry("Maya and Houdini Timeout"))
        arnold_and_mantra_timeout = int(self.GetConfigEntry("Arnold and Mantra Timeout"))

        # Check if a manual timeout value hasn't already been set and it's not a test job.
        if job.JobTaskTimeoutSeconds == 0 and "render_testing" not in job.JobPool:
            office_hours = u_DeadlineToolbox.office_hours()
            # Set the timeouts
            # Only set the timeouts for nuke and ifd/ass gens during work hours
            if office_hours:
                # Set Nuke timeouts to the default value in the Deadline UI, unless its a Client job
                if job.JobPlugin == "Nuke":
                    if "[Client]" in job.JobBatchName:
                        timeout_in_mins = 3
                    else:
                        timeout_in_mins = nuke_timeout

                # Set Houdini/Maya timeouts to the UI value, unless it's a sim / test (single task).
                elif job.JobPlugin in self.ass_ifd_gens:
                    if job.JobTaskCount == 1:
                        timeout_in_mins = 0
                    else:
                        timeout_in_mins = maya_and_houdini_timeout

            # CG timeouts are not office hours dependent.
            if job.JobPlugin in self.cg_renderers or "arnold license limit" in self.limit_groups:
                # only change the timeout for tasks that aren't tests (single task count)
                if job.JobTaskCount == 1:
                    timeout_in_mins = 0
                else:
                    timeout_in_mins = arnold_and_mantra_timeout

            # Set PDG monitor tasks to time themselves out at 1 hour
            if job.JobPlugin == "PDGDeadline" and "pdg_mq" in job.JobLimitGroups:
                timeout_in_mins = 60
        # Set the timeout.
        u_DeadlineToolbox.set_job_timeout(job, timeout_in_minutes=timeout_in_mins)

        # Set up a minimum task time for a render to be considered successful. This stops false "completed" renders.
        # Exclude cmd and PDG jobs as these can have all sorts of different times for different reasons. e.g. a
        # small copy job script that runs as part of a batch
        excluded_plugin_list = ["CommandLine", "PDGDeadline"]
        if job.JobMinRenderTimeSeconds == 0:
            if job.JobPlugin not in excluded_plugin_list:
                job.JobMinRenderTimeSeconds = 2
                RepositoryUtils.SaveJob(job)

    def timeout_error_handling(self, errorReport, job):
        """
        What to do when a specific timeout error occurs.
        Args:
            errorReport:
            job:
        """
        timeout_errors = ["The Worker did not complete the task before the Regular Task Timeout limit"]

        # Get Config Entry values set in deadline UI to use in the script
        nuke_concurrent_tasks = int(self.GetConfigEntry("Nuke Concurrent Tasks"))
        nuke_frames_per_task = int(self.GetConfigEntry("Nuke Frames Per Task"))
        ui_nuke_machine_limit = int(self.GetConfigEntry("Nuke Machine Limit"))
        current_machine_limit = job.JobMachineLimit
        maya_houdini_machine_limit = int(self.GetConfigEntry("Maya and Houdini Machine Limit"))
        maya_houdini_priority = int(self.GetConfigEntry("Maya and Houdini Priority"))
        maya_houdini_concurrent_tasks = int(self.GetConfigEntry("Maya and Houdini Concurrent Tasks"))
        # A check for the current machine limit. If we've already limited a job, and then it is changed by this script
        # we want to keep the manual set machine limit, if not, use the value from the GUI
        if ui_nuke_machine_limit == 0:
            nuke_machine_limit = current_machine_limit
        else:
            nuke_machine_limit = ui_nuke_machine_limit

        # ----------------------------------- Timeout Error Strings ----------------------------------------------------
        cg_timeout_reason = "the task reached our set timeout limit of 3 hours. " \
                            "We do this to ensure jobs don't get stuck behind unexpectedly heavy ones."
        cg_timeout_prod_suggestion = "\n\nIf this was expected, please make sure to notify the wrangler using the" \
                                     " Render Planner for the next submission, so we can remove this timeout and " \
                                     "prevent wasted render time."\
                                     "\n\nIf this was unexpected, please work with your artist to optimise their job."
        cg_timeout_artist_suggestion = "\n\nIf this was expected, please make sure to notify your producer so they " \
                                       "can put this on the Render Planner for the next submission. We can then " \
                                       "remove this timeout and prevent wasted render time." \
                                       "\n\nIf this was unexpected, please optimise your job."
        non_cg_timeout_reason = "The job's tasks reached {} minutes. These settings have been changed to help the job" \
                                " get through faster.".format(job.JobTaskTimeoutSeconds / 60)
        non_cg_artist_suggestion = "\n\nIf this is unexpected, please try to optimise your script."
        non_cg_prod_suggestion = "\n\nIf this is unexpected, please ask your artist to optimise their script."
        # Get job dependencies
        job_dependencies = job.JobDependencyIDs
        # Get the job info before changes are made
        prev_job_info = {
            "concurrent": job.JobConcurrentTasks,
            "machine limit": job.JobMachineLimit,
            "frames per task": job.JobFramesPerTask,
            "priority": job.JobPriority
        }
        # Check for timeout error in the error report.
        if any(timeout_error in errorReport.ReportMessage for timeout_error in timeout_errors):
            # ------------------------ CG timeout handling -----------------------------------------------------------
            if job.JobPlugin in self.cg_renderers or "arnold license limit" in self.limit_groups:
                # This is a CG job, so set the FNS strings to be the CG ones.
                self.job_params_changed_reason = cg_timeout_reason
                self.job_params_changed_prod_suggestion = cg_timeout_prod_suggestion
                self.job_params_changed_artist_suggestion = cg_timeout_artist_suggestion
                # For high prio jobs we don't want to alter the prio.
                if job.JobPriority >= 90:
                    u_DeadlineToolbox.modify_job(job,
                                                 set_timeout_to_0=True)
                    self.parameters_changed = "The priority of this job was above 90, so the priority was not lowered."
                # For anything other than the highest prio jobs we alter them.
                else:
                    u_DeadlineToolbox.modify_job(job,
                                                 set_priority=10,
                                                 set_timeout_to_0=True,
                                                 set_group="251gb",
                                                 )
                    self.parameters_changed = "Job Priority {} > {}".format(prev_job_info["priority"], 10)

            elif job.JobPlugin in self.non_cg_renderer_plugin_list:
                # This is a Non-CG job, so set the FNS strings to be the Non-CG ones.
                self.job_params_changed_reason = non_cg_timeout_reason
                self.job_params_changed_prod_suggestion = non_cg_prod_suggestion
                self.job_params_changed_artist_suggestion = non_cg_artist_suggestion
                # Make sure we haven't already modified the job.
                timeout_error_path = u_DeadlineToolbox.create_temp_txt_file_path(job, "timeouts")
                if not os.path.isfile(timeout_error_path):
                    office_hours = u_DeadlineToolbox.office_hours()
                    # -----------------------SET THE BEHAVIOUR FOR NUKE JOBS-----------------------------------
                    if job.JobPlugin == "Nuke" and "[Client]" not in job.JobBatchName:
                        # In office hours, we want to set the values from the deadline UI.
                        if office_hours:
                            # If the frames per task is already 1, don't set the frames per task to any other number,
                            # as if its hit the timeout with 1 frame per task, we'd never want to increase it.
                            if job.JobFramesPerTask == 1:
                                # we re-set the prio to the value of the original prio as sometimes it would set to 50.
                                u_DeadlineToolbox.modify_job(job,
                                                             set_timeout_to_0=True,
                                                             set_concurrent_tasks=1,
                                                             set_machine_limit=nuke_machine_limit,
                                                             set_priority=job.JobPriority
                                                             )
                                # For use if FNS needed.
                                self.parameters_changed = "Concurrent Tasks {} > {}" \
                                                          "\nMachine Limit {} > {}".format(prev_job_info["concurrent"], 1,
                                                                                           prev_job_info["machine limit"],
                                                                                           nuke_machine_limit
                                                                                           )
                            else:
                                u_DeadlineToolbox.modify_job(job,
                                                             set_timeout_to_0=True,
                                                             set_concurrent_tasks=nuke_concurrent_tasks,
                                                             set_frames_per_task=nuke_frames_per_task,
                                                             set_machine_limit=nuke_machine_limit,
                                                             set_priority=job.JobPriority
                                                             )
                                self.parameters_changed = "Concurrent Tasks {} > {}" \
                                                          "\nMachine Limit {} > {}" \
                                                          "\nFrames Per Task {} > {}".format(prev_job_info["concurrent"],
                                                                                             1,
                                                                                             prev_job_info["machine limit"],
                                                                                             nuke_machine_limit,
                                                                                             prev_job_info["frames per task"],
                                                                                             nuke_frames_per_task
                                                                                             )

                        # Outside of work hours we can modify the job more extremely.
                        else:
                            u_DeadlineToolbox.modify_job(job,
                                                         set_timeout_to_0=True,
                                                         set_concurrent_tasks=1,
                                                         set_frames_per_task=1,
                                                         set_priority=job.JobPriority
                                                         )
                            self.parameters_changed = "Concurrent Tasks {} > {}" \
                                                      "\nFrames Per Task {} > {}".format(prev_job_info["concurrent"], 1,
                                                                                         prev_job_info["frames per task"], 1
                                                                                         )

                    # ----------------------SET THE BEHAVIOUR FOR HOUDINI AND MAYA JOBS------------------------
                    if job.JobPlugin == "Houdini" or job.JobPlugin == "MayaCmd":
                        if office_hours:
                            if job.JobPriority >= 80:
                                # For high prio jobs we don't want to lower the prio or change the machine limit.
                                u_DeadlineToolbox.modify_job(job,
                                                             set_timeout_to_0=True,
                                                             set_concurrent_tasks=maya_houdini_concurrent_tasks,
                                                             set_priority=job.JobPriority
                                                             )
                                self.parameters_changed = "Concurrent Tasks {} > {}".format(prev_job_info["concurrent"],
                                                                                            maya_houdini_concurrent_tasks
                                                                                            )
                            else:
                                u_DeadlineToolbox.modify_job(job,
                                                             set_timeout_to_0=True,
                                                             set_concurrent_tasks=maya_houdini_concurrent_tasks,
                                                             set_priority=maya_houdini_priority,
                                                             set_machine_limit=maya_houdini_machine_limit
                                                             )
                        # Outside of work hours we can modify the job more extremely.
                        else:
                            u_DeadlineToolbox.modify_job(job,
                                                         set_timeout_to_0=True,
                                                         set_concurrent_tasks=1,
                                                         set_priority=job.JobPriority
                                                         )
                            self.parameters_changed = "Concurrent Tasks {} > {}".format(prev_job_info["concurrent"], 1)
                        # If the houdini job has dependencies we don't want to just resume the job, otherwise
                        # the dependencies will break, we want to re-pend the job.
                        if job.JobPlugin == "Houdini":
                            if job_dependencies:
                                RepositoryUtils.PendJob(job)

                    # Write the file to avoid repeated job modifying.
                    with open(timeout_error_path, "w") as timeout_error_file:
                        timeout_error_file.write(errorReport.ReportMessage)
                # If a file is found do nothing.
                else:
                    pass
            # If it's a plugin we aren't expecting, pass.
            else:
                pass

            # -------------------------- Farm Notification System check -----------------------------------------------
            fns_needed = u_DeadlineToolbox.farm_notification_system_check(job)
            if fns_needed:
                # We import the FNS only if needed to limit the amount of SG interaction with the farm.
                # When it was at top level it would cause issues with other event scripts, causing them
                # to not run properly or at all.
                fns = u_FarmNotificationSystem.FarmNotificationSystem(job)
                fns.on_parameters_changed(job,
                                          self.parameters_changed,
                                          self.job_params_changed_reason,
                                          self.job_params_changed_artist_suggestion,
                                          self.job_params_changed_prod_suggestion
                                          )
