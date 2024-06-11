#! /usr/bin/python

"""
This script checks for users who are on holiday who haven't logged out, then restarts their machine if they are still
logged in.
This runs on a cron at 0830.
"""

import os
os.environ["UDB_TYPE"]="Shotgrid"
import sys
sys.path.append('/Volumes/resources/release/python/current')
from upy.udbWrapper import udb_connection
sg = udb_connection.db
import datetime
from Deadline.Scripting import *
from System.Collections.Specialized import *
from scripts.General.u_DeadlineToolbox import u_DeadlineToolbox


def __main__(*args):
    # If we are running this from deadline it will run this function, and we want to run it as a test.
    # this is an optional argument that will print out a string rather than restarting peoples machines
    restart_holiday_users(test=True)


def restart_holiday_users(*args, test=False):
    # Get today's date.
    today = datetime.date.today()
    # Set up fields and filters to search shotgrid
    # Here im getting the human-readable name from the user item directly, as well as the computer info
    fields = ["user.HumanUser.name", "start_date", "end_date", "user.HumanUser.sg_computers_1", "user.HumanUser.tags"]
    # Set up a list of status' to check for (On Set, On Holiday)
    holiday_on_set_list = ["set", "offha"]
    # This looks for any "Bookings" entities which match the holiday_on_set_list, and if those fall on today.
    # the "filter_operator": "any" acts as an or, so were essentially making a <= and =>
    # Make sure they're not exempt from logging off, i.e. tech.
    filters = [
        ["sg_status_list", "in", holiday_on_set_list],
        {
            "filter_operator": "any",
            "filters": [
                ["start_date", "less_than", today],
                ["start_date", "is", today]
            ]
        },
        {
            "filter_operator": "any",
            "filters": [
                ["end_date", "greater_than", today],
                ["end_date", "is", today]
            ]
        }
    ]
    # Find em!
    bookings = sg.find("Booking",
                       filters,
                       fields)
    # Set up a dict of users who are on holiday AND didn't log out to print out.
    users_who_didnt_log_out = {}
    for user in bookings:
        name = user["user.HumanUser.name"]
        # we now use tags instead of another field on shotgrid.
        # This helps as when we're creating tools we don't want to use a new field every time.
        # We want to not restart user who are have the tag "AutomationExemption_Logoff"
        tags = user["user.HumanUser.tags"]
        if not any(tag["name"] == "AutomationExemption_Logoff" for tag in tags):
            computer_name = []
            for computer in user["user.HumanUser.sg_computers_1"]:
                # Ignore windows and kvm machines as they cant be used on the farm
                exclusion_list = ["kvm", "win"]
                # using an any instead of a big for loop to check for these exclusions
                if not any(excluded_string in computer["name"] for excluded_string in exclusion_list):
                    # Add the name of that user to the computer name list
                    computer_name.append(computer["name"])
                    for worker in computer_name:
                        # Check if that computer is enabled on the farm
                        slave_settings = RepositoryUtils.GetSlaveSettings(worker, True)
                        slave_enabled = slave_settings.SlaveEnabled
                        # We only want to get the machines that aren't disabled in deadline
                        if slave_enabled:
                            # Run "who" on it to determine if anyone is logged in.
                            logged_in = SlaveUtils.SendRemoteCommandWithResults(worker, "Execute who")
                            # Check if new line is in the output. This is because if there is no one logged in,
                            # the output is only one line stating that the script "ran with exit code 0"
                            if "\n" in logged_in:
                                # If there is someone logged in, restart their machine and add them to the dict to be printed.
                                users_who_didnt_log_out[name] = worker
                                if not test:
                                    u_DeadlineToolbox.restart_after_task_completion(worker=worker)
                                else:
                                    print("This is a test, not restarting the machine.")

    if users_who_didnt_log_out:
        print("Restarted these artist's machines: "
              "\n{}".format(users_who_didnt_log_out)
              )
    else:
        print("No users to restart.")
