#!/usr/bin/python

"""
In extremely busy times we can use ALL of the split machines for nuke jobs, but they need to be un-split and added back
into the nuke limit allow list.

This script contains functions for both activating and resetting it, and is controlled with the u_BigRedButtonUI.py.

"""
from Deadline.Scripting import *
from System.Collections.Specialized import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox
from scripts.General.u_SplitMachineModify import u_SplitMachineModify


class TheBigRedButton:

    def __init__(self):
        # Set up all the default values and lists to use in the big red button function
        self.maya_houdini_list = ["MayaCmd", "Houdini"]
        self.excluded_list = []
        self.nuke_limit_deny_list = ["playback01",
                                     "render07",
                                     "union38win"
                                     ]
        self.leave_disabled_workers = ["render35-01",
                                       "render36-01"
                                       ]
        self.add_to_deny_list = ["render27",
                                 "render33",
                                 "render34",
                                 "render37",
                                 "render38",
                                 "render39",
                                 "render40",
                                 "render41",
                                 "render42"
                                 ]
        self.split_machines_to_modify = u_DeadlineToolbox.get_slave_names_in_group(group_name="split_machines")
        self.job_states = []
        self.worker_state = None
        self.requeue_tasks = None
        self.leave_disabled = None
        self.houdini_check = None
        self.jobs_in_state = []

    def on_or_off(self, brb_on):
        # Here we are changing some values for it we are activating or resetting the button
        if brb_on:
            self.job_states = ["Active"]
            self.worker_state = False
            self.requeue_tasks = True
            self.leave_disabled = False
            self.houdini_check = False

        if not brb_on:
            self.job_states = ["Active", "Pending"]
            self.worker_state = True
            self.requeue_tasks = False
            for worker in self.add_to_deny_list:
                self.nuke_limit_deny_list.append(worker)
            self.leave_disabled = True
            self.houdini_check = True
            for worker in self.leave_disabled_workers:
                self.split_machines_to_modify.remove(worker)
        # We need to get the jobs in state here as we need to determine which states we need first.
        self.jobs_in_state = RepositoryUtils.GetJobsInState(self.job_states)

    def the_big_red_button(self):

        # ---------------------------------- First modify the workers ------------------------------------------------
        for worker in self.split_machines_to_modify:
            # for every machine disable the ones with - in the name, i.e. the splits.
            if "-" in worker:
                u_DeadlineToolbox.modify_worker(slave=worker, set_worker_state=self.worker_state)

        # ----------------------------------- Then Requeue the tasks on them if needed---------------------------------
        if self.requeue_tasks:
            for job in self.jobs_in_state:
                # We want to leave sims unaffected as they could be multiple hours in length
                if job.JobGroup != "sims":
                    # get the TaskCollection on that job
                    job_task_collection = RepositoryUtils.GetJobTasks(job, True)
                    # set up a list to add tasks to be re-queued into
                    task_that_need_to_be_requeued = []
                    # loop through the tasks to see if we need to requeue any
                    for task in job_task_collection.TaskCollectionTasks:
                        if task.TaskSlaveName in self.split_machines_to_modify:
                            if task.TaskStatus == "Rendering":
                                task_that_need_to_be_requeued.append(task)
                    # Requeue the tasks
                    RepositoryUtils.RequeueTasks(job, task_that_need_to_be_requeued)

        # ----------------------------- Edit the Nuke limit to add or remove the split machines----------------------
        RepositoryUtils.SetLimitGroup("nuke render license limit",
                                      40,
                                      self.nuke_limit_deny_list,
                                      False,
                                      self.excluded_list,
                                      100
                                      )

        # ------ See if we need to run the Disable 27, 33, 34 script if there arent any Houdini jobs on the farm.------
        if self.houdini_check:
            # Loop through all of the jobs on the farm, if we find a houdini job that isnt a sim, change
            # disable_split_needed to false, else run the script to use those machines for Nuke.
            disable_split_needed = True
            for job in self.jobs_in_state:
                if job.JobPlugin in self.maya_houdini_list:
                    print("found a {} job".format(job.JobPlugin))
                    if job.JobGroup == "sims":
                        print("its a sim so we can still run the script")
                    else:
                        print("found a {} job, we don't need to disable the splits".format(job.JobPlugin))
                        disable_split_needed = False
                        # Once we've found any houdini job that's not a sim, break as we know we don't need to run it.
                        break
            # If we didnt find a maya or houdini job, run the script, as we can use these machines to render nuke jobs
            if disable_split_needed:
                u_SplitMachineModify.disable_splits()

    def run(self, brb_on=None):
        self.on_or_off(brb_on)
        self.the_big_red_button()

# The following functions are separate for debugging purposes.


def activate_button():
    brb = TheBigRedButton()
    brb.run(brb_on=True)
    print("The Big Red Button activated!")


def reset_button():
    brb = TheBigRedButton()
    brb.run(brb_on=False)
    print("The Big Red Button has been reset.")
