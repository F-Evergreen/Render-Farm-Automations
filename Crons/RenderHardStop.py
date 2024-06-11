#! /usr/bin/python

"""
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
		eu_w_0915_cron()
	elif machine_name == na_ne_pulse:
		ne_ne_0815_cron()
	else:
		print("You are attempting to run cron this locally. This is designed to be run on a localised pulse server"
			  "due to the nature of the functions being run."
			  "Please ask systems to do this for you if you need to test on a pulse server.")


def eu_w_0915_cron():
	"""
	This is a cron that will run at 09:15am Mon-Fri in LDN.
	- Requeues all jobs on LDN workstations. This in combination with the 08:30 Cron allows
	 artists to log on without something rendering on their machine.
	 """
	# Instantiate the cron library with the site location.
	cron_lib_instance = u_CronLibrary.CronLibrary(site="eu_w")

	# Run the needed functions.
	cron_lib_instance.requeue_tasks_on_workstations()
	cron_lib_instance.requeue_tasks_on_non_251_machines()


def ne_ne_0815_cron():
	"""
	This is a cron that will run at 08:15am Mon-Fri in MTL.
	- Requeues all jobs on MTL workstations. This in combination with the 07:30 Cron allows
	 artists to log on without something rendering on their machine.
	 """
	# Instantiate the cron library with the site location.
	cron_lib_instance = u_CronLibrary.CronLibrary(site="na_ne")

	# Run the needed functions.
	cron_lib_instance.requeue_tasks_on_workstations()
