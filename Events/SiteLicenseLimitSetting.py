#!/usr/bin/python3
from Deadline.Events import *
from Deadline.Scripting import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox
from System.Collections.Specialized import *


def GetDeadlineEventListener():
    return OnSubmission()


def CleanupDeadlineEventListener(eventListener):
    eventListener.Cleanup()


class OnSubmission(DeadlineEventListener):

    # We're only setting site based limits for these plugins at the moment.
    # todo: add "houdini" and "arnold license limit", when they have licenses in mtl.
    site_based_limits = ["nuke render license limit"]

    # Set up the event callbacks here
    def __init__(self):
        self.OnJobSubmittedCallback += self.OnJobSubmitted

    def Cleanup(self):
        del self.OnJobSubmittedCallback

    def OnJobSubmitted(self, job):

        # We check that the submit machine contains "mtl". I'm using this instead of a Deadline group as jobs can be
        # submitted by machines which don't exist on Deadline, which breaks this.
        # We could also use SG integration with the Systems project page, though connecting to SG for every job
        # submitted would be a lot of overhead to just get usually the same list of strings back.
        if "mtl" in job.JobSubmitMachine:
            self.set_site_limits(job, site="na_ne")

        elif "mtl" not in job.JobSubmitMachine:
            # We don't want to alter hermes limits at all.
            if job.JobPool != "hermes":
                self.set_site_limits(job, site="eu_w")

    def set_site_limits(self, job, site=""):

        # Get the limits the job was submitted with
        submitted_limit_list = u_DeadlineToolbox.get_job_limits_as_list(job)
        # First set the site limit.
        submitted_limit_list.append(site)
        # Then add the site name to the beginning of the site based limit.
        for limit in submitted_limit_list:
            if limit in self.site_based_limits:
                # this changes the limit from e.g. "houdini" to "na_ne_houdini"
                new_site_limit = site + "_" + limit
                # remove the original limit from the list
                submitted_limit_list.remove(limit)
                # add the new limit with the site info.
                submitted_limit_list.append(new_site_limit)
        # Once we've processed them remove duplicates that can occasionally occur
        new_limit_list = list(dict.fromkeys(submitted_limit_list))
        job.SetJobLimitGroups(new_limit_list)
        RepositoryUtils.SaveJob(job)
        print("Set the {} site limits for this job: {}".format(site, new_limit_list))
