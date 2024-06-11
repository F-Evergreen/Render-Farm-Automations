#! /usr/bin/python
"""
To run this script use the following cmd in a linux terminal
/Volumes/software/deadline/10/client/current/bin/deadlinecommand -executeScriptNoGui /Volumes/software/deadline/10/repository/custom/scripts/General/Crons/u_RenderReset.py
"""

from scripts.General.Crons import u_CronLibrary
import socket


def __main__(*args):
	# Here we determine if the file is being run on the MTL pulse, or pulse1/2 (which are located in london)...
	# ...then run the associated location's cron.
	machine_name = socket.gethostname()
	eu_w_pulses = ["pulse1", "pulse2"]
	na_ne_pulse = "pulse-mtl-001"
	if machine_name in eu_w_pulses:
		eu_w_0830_cron()
	elif machine_name == na_ne_pulse:
		ne_ne_0730_cron()
	else:
		print("You are attempting to run cron this locally. This is designed to be run on a localised pulse server"
			  "due to the nature of the functions being run."
			  "Please ask systems to do this for you if you need to test on a pulse server.")


def eu_w_0830_cron():
	"""
	This is a cron that will run at 08:30am Mon-Fri in LDN.
	- Remove all Pools from LDN workstations, so they can no longer pick up jobs until added in a later cron.
	- Set any left over CG to the "251gb" group.
	- Reset the Houdini license limit for when we change it overnight
	- Reset the priority lists
	- Check for and restart any users who forgot to log out and went on holiday / on set.
	"""
	# Instantiate the cron library with the site location.
	cron_lib_instance = u_CronLibrary.CronLibrary(site="eu_w")

	# Run the needed functions.
	cron_lib_instance.clear_workstation_pools()
	cron_lib_instance.set_cg_to_group(group="251gb")
	cron_lib_instance.reset_houdini_engine_licence_limit(no_of_licenses=6)
	cron_lib_instance.reset_user_groups(groups=["u_PriorityUsers", "u_CT_Users"])
	cron_lib_instance.restart_holiday_onset_users()


def ne_ne_0730_cron():
	"""
	This is a cron that will run at 07:30am Mon-Fri in MTL.
	- Remove all Pools from MTL workstations, so they can no longer pick up jobs until added in a later cron.
	"""
	# Instantiate the cron library with the site location.
	cron_lib_instance = u_CronLibrary.CronLibrary(site="na_ne")

	# Run the needed functions.
	cron_lib_instance.clear_workstation_pools()
# todo when they get more machines add the "cg_to_251_group" to this func.
