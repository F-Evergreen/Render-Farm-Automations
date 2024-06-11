#!/usr/bin/python

"""
In busy times we can use render27, 33 and 34 for nuke / CG jobs, but they need to be un-split and added back into the
nuke limit allow list. This does this, and undoes this automatically.
"""
from Deadline.Scripting import *
from System.Collections.Specialized import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox
import datetime


class SplitModifySetup:

    def __init__(self):
        self.day_of_week = datetime.datetime.now().today().weekday()
        self.hour_of_day = datetime.datetime.now().hour
        self.workers_to_modify_list = u_DeadlineToolbox.get_slave_names_in_group("split_non_epic_machines")
        self.split_workers_to_modify = []
        self.non_split_workers_to_modify = []
        self.cg_limits = ["mantra_houdini_renders",
                          "arnold license limit"
                          ]
        self.limit_group_to_modify = ["eu_w_nuke render license limit"]

        # Sort the list above into 2 usable lists: Splits, and non.
        for worker in self.workers_to_modify_list:
            if "-" in worker:
                self.split_workers_to_modify.append(worker)
            elif "-" not in worker:
                self.non_split_workers_to_modify.append(worker)

        # if it is out of office hours, every time alter the limit group, we want to include the cg limits, so we can
        # use those 3 machines for cg.
        if self.day_of_week < 5 and self.hour_of_day > 18 or self.hour_of_day < 8:
            for limit in self.cg_limits:
                self.limit_group_to_modify.append(limit)

    def disable_splits_and_add_to_limit(self):
        """
        Disables render27, 33 and 34 splits, then adds the limits to them.
        """

        # Disable the Splits.
        for worker in self.split_workers_to_modify:
            u_DeadlineToolbox.modify_worker(worker, set_worker_state=False)

        # This removes workers to the DENY list, effectively enabling their ability to render nuke jobs.
        for limit_group in self.limit_group_to_modify:
            RepositoryUtils.RemoveSlavesFromLimitGroupList(limit_group, self.non_split_workers_to_modify)

    def enable_splits_remove_from_limit_requeue_tasks(self):
        """
        Enables render27, 33 and 34 splits, re-queues any tasks on them, then removes the limits from them.
        """

        # This adds workers to the DENY list, effectively removing their ability to render nuke jobs.
        for limit_group in self.limit_group_to_modify:
            RepositoryUtils.AddSlavesToLimitGroupList(limit_group, self.non_split_workers_to_modify)

        # Requeue any tasks on the non-split workers to free them up for houdini/maya
        u_DeadlineToolbox.requeue_tasks_on_workers(re_queue_worker_list=self.non_split_workers_to_modify)

        for worker in self.split_workers_to_modify:
            u_DeadlineToolbox.modify_worker(worker, set_worker_state=True)


def disable_splits():
    setup = SplitModifySetup()
    setup.disable_splits_and_add_to_limit()


def reset_splits():
    setup = SplitModifySetup()
    setup.enable_splits_remove_from_limit_requeue_tasks()
