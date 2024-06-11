#!/usr/bin/python

"""
This script notifies the producer and artist when a job has failed, finished or had some parameters changed on the farm,
if the priority is above 80 and has been changed by the wrangler.

It does this by:
Getting a list of the producers on the show by comparing the job's pool with the shotgrid group i.e. if pool = pal
prod group = pal_PROD
Setting up canned emails with all the information they need such as the job name and what parameters have changed
Then sends an email to the producers and the artist.

This does not affect automatic raised priority job types as we now set a JobExtraInfo9 on them to signify they were
raised automatically and can therefore be ignored here.
"""
from Deadline.Scripting import *
from System.Collections.Specialized import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox
# Set up the union environment, so we have access to our repositories, env vars are set, etc.
# We need access to this so we can import emailutils
from scripts.General import u_environment_utils
u_environment_utils.setup_environment()
from utilities import emailutils


class FarmNotificationSystem:
    # Set up Shotgrid connection here instead of top level. This reduces unnecessary SG connections on the farm
    from upy.udbWrapper import udb_connection
    SG = udb_connection.db

    # Set up the common info we need to attain here
    def __init__(self, job):

        self.prod_email_list = []
        self.sender_reply_email = "wrangler@unionvfx.com"
        self.pool = job.JobPool
        self.job_user = job.JobUserName
        # get the artist's email.
        user_info = RepositoryUtils.GetUserInfo(self.job_user, True)
        # This needs to be a list for the emailutils
        self.artist_email = [user_info.UserEmailAddress]
        self.job_name = job.JobName
        self.pipe_group = RepositoryUtils.GetUserGroup("pipeline")
        # Run the function to get the producer emails.
        self.get_job_producer_emails()

    def get_job_producer_emails(self):

        # We need to get the full prod group name as for shows such as "rt" this will search for any group with rt in
        # the name e.g. aRTist... which we don't want.
        production_sg_group = self.pool + "_PROD"
        # Set up the fields and filters to search for on shotgrid
        fields = ["email", "tags"]
        filters = [["sg_status_list", "is", "act"],
                   ["groups", "name_contains", "{}".format(production_sg_group)],
                   ["tags", "name_not_contains", "AutomationExemption_FarmNotificationSystem"]
                   ]
        # use those to find the producers for the show in question.
        found_producers = self.SG.find("HumanUser", filters, fields)
        # Append their emails to the prod email list
        for producer in found_producers:
            email = producer["email"]
            self.prod_email_list.append(email)
        # Confirm who's emails we have in a print
        if self.prod_email_list:
            print("This is the list of production staff who will be emailed: {}.".format(self.prod_email_list))
        else:
            print("No producers found for this pool - {}. It is likely not a project pool. No email sent.".format(self.pool))

    def set_up_and_send_email_to_producer(self, subject_string, params_changed_message=None):
        """
        This gets run by the thing that triggered it. e.g. u_FarmNotificationSystemTriggers.py
        """
        subject = "{}'s Job: {} has {}".format(self.job_user, self.job_name, subject_string)
        # if it's a parameters changed email we want the email to have a different body
        if params_changed_message:
            message = params_changed_message
        else:
            message = ["Your artist {}'s job: {}, has {}."
                       "\n\nPlease contact the wrangler or your artist for more information.".format(self.job_user,
                                                                                                     self.job_name,
                                                                                                     subject_string)
                       ]
        # Send the email if we found producers.
        if self.prod_email_list:
            emailutils.send_email(msg_from_addr=self.sender_reply_email,
                                  reply_to_addr=self.sender_reply_email,
                                  use_reply_to_addr=True,
                                  msg_subject=subject,
                                  msg_body=message,
                                  msg_to_addrs=self.prod_email_list
                                  )

    def set_up_and_send_email_to_artist(self, subject_string, params_changed_message=None):

        # For artist's we want a slightly different email too
        subject = "Your job: {} has {}.".format(self.job_name, subject_string)
        if params_changed_message:
            message = params_changed_message
        else:
            message = ["Your job: {} has {}"
                       "\n\nPlease contact the wrangler for more information.".format(self.job_name, subject_string)
                       ]
        # Send the email to the artist.
        emailutils.send_email(msg_from_addr=self.sender_reply_email,
                              reply_to_addr=self.sender_reply_email,
                              use_reply_to_addr=True,
                              msg_subject=subject,
                              msg_body=message,
                              msg_to_addrs=self.artist_email
                              )

    def on_parameters_changed(self,
                              job,
                              parameters_changed="",
                              job_params_changed_reason="",
                              job_params_changed_artist_suggestion="",
                              job_params_changed_prod_suggestion=""):
        """
        This function gets run by other events such as u_OnJobErrors.py
        """
        # This function is slightly more involved as we want to pass in lots of different data dependent on what
        # parameters have changed. Therefore, I've split the email body into 3 parts.
        fns_needed = u_DeadlineToolbox.farm_notification_system_check(job)
        if fns_needed:
            subject_string = "had some job parameters changed on the farm."
            # ---------------------------First part of params changed message----------------------------------
            prod_params_changed_first_line = "Your artist {}'s job: {} has {}.".format(self.job_user,
                                                                                       self.job_name,
                                                                                       subject_string
                                                                                       )
            artist_params_changed_first_line = "Your job: {} has {}".format(self.job_name,
                                                                            subject_string
                                                                            )

            # -----------------Second part of message detailing what has changed---------------------------------------

            params_changed_detail = "\n\nThe parameters that have changed are:" \
                                    "\n{}".format(parameters_changed)

            # --------------------------Third part of params changed message detailing why things were changed---------
            prod_reason = job_params_changed_reason + job_params_changed_prod_suggestion
            artist_reason = job_params_changed_reason + job_params_changed_artist_suggestion
            prod_reason_string = "\n\nThese were changed because:" \
                                 "\n{}" \
                                 "\n\nPlease contact the wrangler or your artist " \
                                 "for more information.".format(prod_reason)
            artist_reason_string = "\n\nThese were changed because:" \
                                   "\n{}" \
                                   "\n\nPlease contact the wrangler for more information.".format(artist_reason)


            # Combine the parts into one message list for the email
            artist_params_changed_message = [
                artist_params_changed_first_line + params_changed_detail + artist_reason_string]
            prod_params_changes_message = [
                prod_params_changed_first_line + params_changed_detail + prod_reason_string]

            # Send the emails
            self.set_up_and_send_email_to_artist(subject_string,
                                                 params_changed_message=artist_params_changed_message)
            self.set_up_and_send_email_to_producer(subject_string,
                                                   params_changed_message=prod_params_changes_message)
