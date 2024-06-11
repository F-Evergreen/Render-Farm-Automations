#! /usr/bin/python

"""

This script finds and identifies any user who hasn't logged out by 21:00, then emails that list to operations,
resource, supervisors, systems and the wrangler.
It also creates a csv of they days offenders in this location:
    /Volumes/resources/pipeline/logs/deadline/logged_in_user_logs

"""

import os
from scripts.General import u_environment_utils
u_environment_utils.setup_environment()
u_environment_utils.setup_python_site_packages()
from Deadline.Scripting import *
from System.Collections.Specialized import *
from utilities import emailutils
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox
import csv

# setup the union environment so we have access to our repositories, env vars are set, etc.
from scripts.General import u_environment_utils
u_environment_utils.setup_environment()

from upy.udbWrapper import udb_connection
# Set up Shotgrid connection
sg = udb_connection.db


def __main__(*args):

    # Set up the fields and filters to search for on shotgrid
    fields = ["login", "name", "sg_computers_1"]
    filters = [["sg_status_list", "is", "act"],
               ["sg_computers_1", "is_not", None],
               ["tags", "not_in", [{"type": "Tag", "id": 12545}]] # This is Using shotgun tags instead of another field.
               # This helps as when we're creating tools we don't want to use a new field every time.
               # The tag associated with this ID is "AutomationExemption_Logoff"
               ]
    # find users using this filter
    found_users = sg.find("HumanUser", filters, fields)
    # set up a dict to put these users and their machines into
    user_machine_dict = {}
    # find the user info and put it in the dict
    for user in found_users:
        login = user["login"]
        name = user["name"]
        computer_names = []
        for computer in user["sg_computers_1"]:
            # Ignore windows machines as they cant be used on the farm
            # We arent able to check if the kvm machines are logged in using their non "ip address" name
            if "win" and "kvm" not in computer["name"]:
                computer_names.append(computer["name"])

        user_machine_dict[name] = {"Login": login, "Machines": computer_names}

    # Create a human readable list to send to prod etc.
    human_readable_machine_list = ""
    # Set up a list to put machines that are still logged in, in
    user_machines_logged_in = []

    for name, info in user_machine_dict.items():
        machines = info["Machines"]
        for machine in machines:
            slave_settings = RepositoryUtils.GetSlaveSettings(machine, True)
            slave_enabled = slave_settings.SlaveEnabled
            # We only want to get the machines that aren't disabled for some reason in deadline
            if slave_enabled:
                logged_in = SlaveUtils.SendRemoteCommandWithResults(machine, "Execute who")
                # Check if new line is in the output. This is because if there is no one logged in, the output is only
                # one line stating that the script ran with exit code 0
                if "\n" in logged_in:
                    # Add that machine and user to the list of dictionaries
                    user_machines_logged_in.append({'User': name, 'Machine Name': machine})
                    # Format this as human readable for prod etc.
                    human_readable_machine_list += "{} : {}\n".format(name, machine)

    # --------------------------------Set up a log to keep track of these users over time.-----------------------------
    # Get London time as we set all of our automation using that at the moment
    london_time = u_DeadlineToolbox.LondonDatetime()
    # Get the current month to set a folder for that month
    current_month = london_time.localised_london_datetime.strftime("%Y-%B")
    # Get current day to use as the file name
    current_day = london_time.localised_london_datetime.strftime("%d-%m-%Y")
    # Get the current time
    current_time = london_time.localised_london_datetime.strftime("%H:%M")
    # Define the file path for the log to go in
    filepath = "/Volumes/resources/pipeline/logs/deadline/logged_in_user_logs/{}".format(current_month)
    # If the file path doesn't exist, create it. (i.e. first of the month)
    if not os.path.isdir(filepath):
        os.makedirs(filepath)
    # Write the log.
    with open(os.path.join(filepath, "{}_log.csv".format(current_day)), 'w') as csv_file:
        column_names = ['User', 'Machine Name']
        writer = csv.DictWriter(csv_file, column_names)
        writer.writeheader()
        for index in user_machines_logged_in:
            writer.writerow(index)

    # ------------------------------------------ E-mail people to let them know----------------------------------------
    # Set up the email
    subject = "Logged in user report: {}".format(current_day)
    message = ["There were {} users still logged in last night at {}"
               "\n\nPlease remind these users to log out in the evening so we can have the maximum amount of machines "
               "available on the farm."
               "\n\nHere are the logged in users and their machines:"
               "\n{}".format(len(user_machines_logged_in), current_time, human_readable_machine_list)]
    email_list = ["operations@unionvfx.com", "resource@unionvfx.com", "wrangler@unionvfx.com"]
    sender_address = "wrangler@unionvfx.com"
    # Send the email
    emailutils.send_email(msg_from_addr=sender_address,
                          msg_subject=subject,
                          msg_body=message,
                          msg_to_addrs=email_list)
