#! /usr/bin/python

"""
This script gets all the CG jobs on the farm, gathers usable info from them and puts that into a CSV.
This helps the evening wrangler with scheduling heavy jobs.
The logs are saved here: /Volumes/resources/pipeline/logs/deadline/render_planner_exports
Depending on which site this is run at, it will get the CG jobs for that site

"""

import csv
from datetime import datetime
import os
import copy
import socket
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox
from Deadline.Scripting import *
# setup the union environment so we have access to our repositories, env vars are set, etc.
from scripts.General import u_environment_utils

u_environment_utils.setup_environment()
from utilities import emailutils


# Set up a class to put all the re-used data into
# This then processes the data once it has been gathered
class RenderPlannerJob:
    def __init__(self, batch_name, job_name, user, show, job_plugin, job_group, no_of_frames, completed_frames,
                 task_render_times_in_secs_list, job_priority_number):
        self.batch_name = batch_name
        self.job_name = job_name
        self.user = user
        self.show = show
        self.job_plugin = job_plugin
        self.job_group = job_group
        self.no_of_frames = float(no_of_frames)
        self.completed_frames = float(completed_frames)
        self.frames_remaining = self.no_of_frames - self.completed_frames
        self.task_render_times_in_secs_list = task_render_times_in_secs_list
        self.percentage_complete_int = 0
        self.average_job_task_time_in_mins = 0
        self.total_job_render_mins = 0
        self.remaining_render_mins = 0
        self.total_est_job_render_mins = 0
        self.avg_est_frame_render_time = 0
        self.job_priority_number = job_priority_number

        # Set up averages for estimating frame render times once class is instantiated
        if self.job_plugin == "Houdini":
            if self.job_group == "sims":
                self.avg_est_frame_render_time = 120
            else:
                self.avg_est_frame_render_time = 5
        elif self.job_plugin in ["Arnold", "Mantra"]:
            self.avg_est_frame_render_time = 20
        elif self.job_plugin == "MayaCmd":
            self.avg_est_frame_render_time = 5

    def process_job_data(self):

        # When there are completed frames on a job, process the data using the frame times from the completed frames...
        if self.completed_frames:
            self.percentage_complete_int = int((100 * (self.completed_frames / self.no_of_frames)))
            self.average_job_task_time_in_mins = int(
                (sum(self.task_render_times_in_secs_list) / self.completed_frames) / 60)
            self.total_job_render_mins = int(self.average_job_task_time_in_mins * self.no_of_frames)
            self.remaining_render_mins = int(self.frames_remaining * self.average_job_task_time_in_mins)

        # ...Else use a default value to ESTIMATE the render times.
        else:
            self.total_est_job_render_mins = int(self.avg_est_frame_render_time * self.no_of_frames)


class RenderPlannerExporter:
    # This class does the actions to collect the data and create the log
    def __init__(self, site):

        self.cg_export_site = site
        # Get the current month to set a folder for that month
        self.current_month = datetime.now().strftime("%Y-%B")
        # Get current day to use as the file name
        self.current_day = datetime.now().strftime("%d-%m-%Y")
        # Get the current time for use in the email
        self.current_time = datetime.now().strftime("%H:%M")
        # Set up default values for if frame estimates have been used...
        self.frame_estimates_used = False
        # ... and to total est render mins
        self.sum_total_est_render_mins = 0
        # Set up daily budget based on day of the week
        self.render_budget = 0
        self.render_limit = 0
        self.day_of_week = datetime.now().today().weekday()
        # If it is friday, the budget is set using the render mins calculated for over the weekend, otherwise, use the
        # weekday budget
        if self.day_of_week == 4:
            self.render_budget = 355020
            self.render_limit = 250000
        else:
            self.render_budget = 75660
            self.render_limit = 50000

        # Set up a template dict to reference later on
        self.template_job_dict = {
            "frame_count": 0,
            "completed_frames": 0,
            "frames_remaining": 0,
            "average_job_task_time_list": [],
            "average_batch_task_time": None,
            "est_total_job_render_mins": 0,
            "est_remaining_render_mins": 0,
            "percentage_complete_list": [],
            "avg_percentage_complete": None,
            "frame_estimates_used": ""
        }
        # Set up empty dicts we can put data into
        self.dict_of_unique_jobs = {}
        self.prod_readable_dict = {}

        # Set up the file path the logs will be in
        self.csv_file_path = "/Volumes/resources/pipeline/logs/deadline/render_planner_exports/{}/{}".format(site,
                                                                                                             self.current_month)
        self.current_log_file_path = os.path.join(self.csv_file_path, "{}_render_export.csv".format(self.current_day))

        # get all active / pending CG jobs
        job_states = ["Active", "Pending"]
        cg_renderers = ["Mantra", "Arnold", "MayaCmd", "Houdini"]
        arnold_limit = "arnold license limit"
        all_active_pending_jobs = RepositoryUtils.GetJobsInState(job_states)

        # For every found job, gather, process and put the data into the dict_of_unique_jobs
        for job in all_active_pending_jobs:
            job_limits = u_DeadlineToolbox.get_job_limits_as_list(job)
            if "na_ne" in job_limits:
                job_site = "na_ne"
            elif "eu_w" in job_limits:
                job_site = "eu_w"
            else:
                job_site = "no_site_found"

            # We only want to process the job data for the needed site. Or if running manually, we want to process all.
            if job_site == self.cg_export_site or self.cg_export_site == "all":
                if job.JobPlugin in cg_renderers:
                    render_planner_job = self.gather_job_data(job)
                    render_planner_job.process_job_data()
                    self.update_dictionary(render_planner_job)
                # Gather u_render jobs too, these are command line jobs that are rendering arnold tasks
                elif job.JobPlugin == "CommandLine" and arnold_limit in job.JobLimitGroups:
                    render_planner_job = self.gather_job_data(job)
                    render_planner_job.process_job_data()
                    self.update_dictionary(render_planner_job)

        # Process the dict_of_unique_jobs into a "production readable dict" with the useful info
        self.convert_to_prod_readable_data()

    def gather_job_data(self, job):

        # Get the job stats
        job_task_collection = RepositoryUtils.GetJobTasks(job, True)
        job_task_collection_tasks = job_task_collection.TaskCollectionTasks

        # Get frame details
        no_of_frames = job.JobTaskCount
        completed_frames = job.JobCompletedTasks
        task_render_times_in_secs_list = []
        for task in job_task_collection_tasks:
            if task.TaskStatus == "Completed":
                task_render_time = task.TaskRenderTime
                task_render_time_in_secs = int(task_render_time.TotalSeconds)
                if task_render_time_in_secs != 0:
                    task_render_times_in_secs_list.append(task_render_time_in_secs)

        # put all the gathered data into a variable to pass into the dict updater
        render_planner_job = RenderPlannerJob(
            batch_name=job.JobBatchName,
            job_name=job.JobName,
            user=job.JobUserName,
            show=job.JobPool,
            job_plugin=job.JobPlugin,
            job_group=job.JobGroup,
            no_of_frames=no_of_frames,
            completed_frames=completed_frames,
            task_render_times_in_secs_list=task_render_times_in_secs_list,
            job_priority_number=job.JobPriority
        )
        return render_planner_job

    def update_dictionary(self, render_planner_job):
        # Check for the batch name in the dict
        # If it isn't, create a DEEPCOPY of the dict. this KEEPS data already in the dict instead of overwriting it
        # This is an issue as we are appending lists in this dict, without the DEEPCOPY this data does not collect
        # as intended.
        if render_planner_job.batch_name not in self.dict_of_unique_jobs:
            job_data = copy.deepcopy(self.template_job_dict)
        # If there isnt a job with the same batch name, create a new entry with the batch name as key
        else:
            job_data = self.dict_of_unique_jobs[render_planner_job.batch_name]

        if render_planner_job.batch_name:
            job_name = render_planner_job.batch_name
        # If the job doesnt have a batch name, use the job name as key
        else:
            job_name = render_planner_job.job_name

        # Update the job data with all the data we've collected
        job_data["job_name"] = job_name
        job_data["job_priority_number"] = render_planner_job.job_priority_number
        job_data["show"] = render_planner_job.show
        job_data["artist"] = render_planner_job.user

        job_data["frame_count"] += render_planner_job.no_of_frames
        job_data["completed_frames"] += render_planner_job.completed_frames
        job_data["frames_remaining"] += render_planner_job.frames_remaining

        job_data["percentage_complete_list"].append(render_planner_job.percentage_complete_int)
        list_of_percent_complete = job_data["percentage_complete_list"]
        # Get the average % complete for jobs with multiple passes / rendering maya / houdini parts
        avg_percentage_complete = sum(list_of_percent_complete) / len(list_of_percent_complete)
        job_data["avg_percentage_complete"] = avg_percentage_complete

        # Here we set up the same variable to use later, but the data changes if we are using the actual data or the
        # estimated data.
        if not render_planner_job.completed_frames:
            average_job_task_time_list = render_planner_job.avg_est_frame_render_time
            est_total_job_render_mins = render_planner_job.total_est_job_render_mins
            est_remaining_render_mins = render_planner_job.total_est_job_render_mins
        else:
            average_job_task_time_list = render_planner_job.average_job_task_time_in_mins
            est_total_job_render_mins = render_planner_job.total_job_render_mins
            est_remaining_render_mins = render_planner_job.remaining_render_mins

        # If there are no completed frames on ANY one of the jobs in a batch, we need to flag that we are using
        # estimated values and to not rely on them alone.
        if 0 in list_of_percent_complete:
            self.frame_estimates_used = True

        job_data["average_job_task_time_list"].append(average_job_task_time_list)
        list_of_task_times = job_data["average_job_task_time_list"]
        average_batch_task_time_in_mins = sum(list_of_task_times) / len(list_of_task_times)
        job_data["average_batch_task_time"] = int(average_batch_task_time_in_mins)
        job_data["est_total_job_render_mins"] += est_total_job_render_mins
        job_data["est_remaining_render_mins"] += est_remaining_render_mins
        job_data["frame_estimates_used"] = self.frame_estimates_used

        # Here we put job_data into the dict
        self.dict_of_unique_jobs[job_name] = job_data

    def convert_to_prod_readable_data(self):
        # Once we've gotten all of the job data's in the dict_of_unique_jobs, we can summarise this into a "production
        # readable dict", this contains less info than the larger dict, but can instead be used to output to csv.
        for dict_job_name in self.dict_of_unique_jobs.keys():
            prod_job_data = {
                "show": self.dict_of_unique_jobs[dict_job_name]["show"],
                "job_name": dict_job_name,
                "job_priority_number": self.dict_of_unique_jobs[dict_job_name]['job_priority_number'],
                "artist": self.dict_of_unique_jobs[dict_job_name]["artist"],
                "frame_count": self.dict_of_unique_jobs[dict_job_name]["frame_count"],
                "average_task_time": self.dict_of_unique_jobs[dict_job_name]["average_batch_task_time"],
                "est_total_job_render_mins": self.dict_of_unique_jobs[dict_job_name]["est_total_job_render_mins"],
                "est_remaining_render_mins": self.dict_of_unique_jobs[dict_job_name]["est_remaining_render_mins"],
                "percentage_complete": self.dict_of_unique_jobs[dict_job_name]["avg_percentage_complete"],
                "frame_estimates_used": self.dict_of_unique_jobs[dict_job_name]["frame_estimates_used"]
            }
            self.prod_readable_dict[dict_job_name] = prod_job_data
            # Sum the total of the est_remaining_render_mins so we can flag if the threshold for render planning
            # has been reached
            self.sum_total_est_render_mins += int(prod_job_data["est_remaining_render_mins"])

    def create_log(self):

        # when we've finished gathering all of the data for jobs and collated it into the unique job ids
        # (ie batch data is collated), we can then write that data out to a csv (comma separated values) files

        # If the file path doesn't exist, create it. (i.e. first of the month)
        if not os.path.isdir(self.csv_file_path):
            os.makedirs(self.csv_file_path)

        # Create a variable for the current filepath to reuse.
        current_csv_path = os.path.join(self.csv_file_path, "{}_render_export.csv".format(self.current_day))

        # Write the log
        with open(current_csv_path, "w") as csv_file:
            column_names = ["show",
                            "job_name",
                            "job_priority_number",
                            "artist",
                            "frame_count",
                            "average_task_time",
                            "est_total_job_render_mins",
                            "est_remaining_render_mins",
                            "percentage_complete",
                            "frame_estimates_used"
                            ]
            writer = csv.DictWriter(csv_file,
                                    column_names
                                    )
            writer.writeheader()
            for unique_job in self.prod_readable_dict.keys():
                # write the data for that job line by line
                writer.writerow(self.prod_readable_dict[unique_job])

        print("# Created new report here: {}".format(current_csv_path))

    def send_email(self):
        if self.cg_export_site == "na_ne":
            email_site_name = "MTL"
        elif self.cg_export_site == "eu_w":
            email_site_name = "LDN"
        else:
            email_site_name = "Global"

        # Set up the email
        if self.sum_total_est_render_mins >= self.render_limit:
            subject = "URGENT! Render Planning Needed! {} Render Farm CG report: {}".format(email_site_name,
                                                                                            self.current_day)
            message = ["The total estimated render minutes of the CG jobs on the farm is '{}'. "
                       "\nThis is above our set limit of '{}' put in place to flag these heavy days."
                       "\nThis means there is a chance the renders on the farm will not complete by the next work day "
                       "and further planning is needed to avoid disappointment."
                       "\n\nHere is a report of the CG jobs on the farm today at {}"
                       "\n\nThe filepath to the spreadsheet containing this data is:"
                       "\n\n{}"
                       "\n\nPlease keep note of the 'est_remaining_render_mins', the higher this number, "
                       "the longer a job will take."
                       "\n\nOur 'budget' of render minutes for this evening / weekend is {}."
                           .format(self.sum_total_est_render_mins,
                                   self.render_limit,
                                   self.current_time,
                                   self.current_log_file_path,
                                   self.render_budget
                                   )
                       ]

        else:
            subject = "{} Render Farm CG report: {}".format(email_site_name, self.current_day)
            message = ["Here is a report of the CG jobs on the farm today at {}"
                       "\n\nThe filepath to the spreadsheet containing this data is:"
                       "\n\n{}"
                       "\n\nPlease keep note of the 'est_remaining_render_mins', the higher this number, "
                       "the longer a job will take."
                       "\n\nOur 'budget' of render minutes for this evening / weekend is {}."
                       "\n\nIf the 'frame_estimates_used' is True, do not fully rely on the "
                       "'est_remaining_render_mins'.".format(self.current_time,
                                                             self.current_log_file_path,
                                                             self.render_budget
                                                             )
                       ]

        email_list = ["operations@unionvfx.com",
                      "resource@unionvfx.com",
                      "wrangler@unionvfx.com",
                      "production@unionvfx.com"
                      ]
        sender_address = "wrangler@unionvfx.com"
        # Send the email
        emailutils.send_email(msg_from_addr=sender_address,
                              msg_subject=subject,
                              msg_body=message,
                              msg_to_addrs=email_list)

    def run(self):
        # Put that info into a CSV file
        self.create_log()
        # Email prod ONLY if the file is run on cron.
        # This means we can run it manually throughout the day but only email people once.
        hostname = socket.gethostname()
        if "pulse" in hostname:
            self.send_email()


def __main__():
    # Here we determine the machine that is running the file. Then set up the exporter for that site.
    hostname = socket.gethostname()
    eu_w_pulses = ["pulse1", "pulse2"]
    if "pulse-mtl-001" in hostname:
        render_planner_exporter_instance = RenderPlannerExporter(site="na_ne")
    elif hostname in eu_w_pulses:
        render_planner_exporter_instance = RenderPlannerExporter(site="eu_w")
    # If we are running this locally (i.e. tests) export all.
    else:
        render_planner_exporter_instance = RenderPlannerExporter(site="all")
    # Run the things that will create an output
    render_planner_exporter_instance.run()
