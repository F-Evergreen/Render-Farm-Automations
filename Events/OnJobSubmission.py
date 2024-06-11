#!/usr/bin/python
"""
On Submission Event- Environment setup

Copyright Union VFX 2021

"""
import os
import subprocess
import datetime

from Deadline.Events import *
from Deadline.Scripting import *
from System.Collections.Specialized import *
from scripts.General.u_SplitMachineModify import u_SplitMachineModify


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
        """
        Run on job submission, sets various overrides for the job before it renders.
        :param Deadline.Jobs.Job job: job instance that's been submitted to the farm
        :return:
        """

        # ----------------------------------------- NEW ENVIRONMENT PRE-SETUP -----------------------------------------
        # set a job's extra info based on current environment variables
        # don't override any info if it's already there
        print("Setting up Job Extra Info")
        extra_info_keys = job.GetJobExtraInfoKeys()

        for key in extra_info_keys:
            extra_info_value = job.GetJobExtraInfoKeyValue(key)
            print("{}: {}".format(key, extra_info_value))

        if "project_name" not in extra_info_keys:
            project_name = os.environ.get("U_PROJECT", "")
            print("project_name is not in extra info keys. Setting from env var U_PROJECT={}".format(os.getenv("U_PROJECT")))
            if not project_name:
                project_name = job.GetJobEnvironmentKeyValue("U_PROJECT")
            job.SetJobExtraInfoKeyValue("project_name", project_name)
            RepositoryUtils.SaveJob(job)
            print("# Job updated and saved")

        if "package_name" not in extra_info_keys:
            print("package_name is not in extra info keys. Setting from env var U_PACKAGE_NAME={}".format(
                os.getenv("U_PACKAGE_NAME")))
            package_name = os.environ.get("U_PACKAGE_NAME", "")
            if not package_name:
                package_name = job.GetJobEnvironmentKeyValue("U_PACKAGE_NAME")
            job.SetJobExtraInfoKeyValue("package_name", package_name)
            RepositoryUtils.SaveJob(job)
            print("# Job updated and saved")

        if "app_major_python_version" not in extra_info_keys:
            print("app_major_python_version is not in extra info keys. Setting from env var U_APP_MAJOR_PYTHON_VERSION={}".format(
                os.getenv("U_APP_MAJOR_PYTHON_VERSION")))
            app_major_python_version = os.environ.get("U_APP_MAJOR_PYTHON_VERSION", "")
            if not app_major_python_version:
                app_major_python_version = job.GetJobEnvironmentKeyValue("U_APP_MAJOR_PYTHON_VERSION")
            job.SetJobExtraInfoKeyValue("app_major_python_version", app_major_python_version)
            RepositoryUtils.SaveJob(job)
            print("# Job updated and saved")

        if "task_id" not in extra_info_keys:
            print(
                "task_id is not in extra info keys. Setting from env var U_TASK_ID={}".format(
                    os.getenv("U_TASK_ID")))
            job.SetJobExtraInfoKeyValue("task_id", os.environ.get("U_TASK_ID", ""))
            RepositoryUtils.SaveJob(job)
            print("# Job updated and saved")

        # force set `U_PROJECT_ID` as an environment variable
        # allows all jobs submitted from a project have the ability to bootstrap sgtk
        if not job.GetJobEnvironmentKeyValue("U_PROJECT_ID"):
            print("Setting up Project ID Environment Variable to: {}".format(os.getenv("U_PROJECT_ID")))
            job.SetJobEnvironmentKeyValue("U_PROJECT_ID", os.environ.get("U_PROJECT_ID", ""))
            RepositoryUtils.SaveJob(job)
            print("# Job updated and saved")

        # add an environment variable for the job ID so it's easy to identify when a process is running on the farm
        # and that job it's running for
        print("Setting up Job ID Environment Variable to: {}".format(job.JobId))
        job.SetJobEnvironmentKeyValue("DEADLINE_JOB_ID", job.JobId)
        RepositoryUtils.SaveJob(job)
        print("# Job updated and saved")

        # ------------------------------------ Other OnJobSubmitted Scripts -------------------------------------------

        # -------------------------------- Remove auto timeout from MM Slap Comps -------------------------------------
        # disables auto task timeout on slapcomp jobs as they vary in frame times
        slapcomp_names = ["slapcomp", "slap"]
        if job.JobPlugin == "Nuke":
            for naming_scheme in slapcomp_names:
                if naming_scheme in job.JobName:
                    job.JobEnableAutoTimeout = False
                    RepositoryUtils.SaveJob(job)
