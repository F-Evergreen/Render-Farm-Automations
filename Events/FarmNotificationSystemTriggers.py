#!/usr/bin/python

"""
This script handles the triggers for the u_FarmNotificationSystem

For more information on how this works see the u_FarmNotificationSystem.py docstring

"""

from Deadline.Events import *
from scripts.General.u_FarmNotificationSystem import u_FarmNotificationSystem
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox
from System.Collections.Specialized import *


def GetDeadlineEventListener():
    return FarmNotificationSystemTriggers()


def CleanupDeadlineEventListener(eventListener):
    eventListener.Cleanup()


class FarmNotificationSystemTriggers(DeadlineEventListener):

    # Set up the event callbacks here
    def __init__(self):
        self.OnJobFinishedCallback += self.OnJobFinished
        self.OnJobFailedCallback += self.OnJobFailed

    def Cleanup(self):
        del self.OnJobFinishedCallback
        del self.OnJobFailedCallback

    def OnJobFinished(self, job):
        fns_needed = u_DeadlineToolbox.farm_notification_system_check(job)
        if fns_needed:
            subject_string = "finished on the farm."
            # Instantiate the class to get the job info needed.
            fns = u_FarmNotificationSystem.FarmNotificationSystem(job)
            # Then email the producers and artist.
            fns.set_up_and_send_email_to_producer(subject_string)
            fns.set_up_and_send_email_to_artist(subject_string)

    def OnJobFailed(self, job):
        fns_needed = u_DeadlineToolbox.farm_notification_system_check(job)
        if fns_needed:
            subject_string = "failed on the farm."
            # Instantiate the class to get the job info needed.
            fns = u_FarmNotificationSystem.FarmNotificationSystem(job)
            # Then email the producers and artist.
            fns.set_up_and_send_email_to_producer(subject_string)
            fns.set_up_and_send_email_to_artist(subject_string)


