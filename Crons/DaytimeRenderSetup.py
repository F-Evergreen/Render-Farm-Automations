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
        eu_w_1030_cron()
    elif machine_name == na_ne_pulse:
        ne_ne_0930_cron()
    else:
        print("You are attempting to run cron this locally. This is designed to be run on a localised pulse server"
              "due to the nature of the functions being run."
              "Please ask systems to do this for you if you need to test on a pulse server.")


def eu_w_1030_cron():
    """
    This is a cron that will run at 10:30am Mon-Fri in LDN.
    - Adds the render pools back to the LDN workstations.
    - Re-enables workstations disabled the previous night in the "u_OvernightDisableMachine" group.
    - Disables workstations of leads/HODs in the "u_DisableMachineDuringDay" group.
     """
    # Instantiate the cron library with the site location.
    cron_lib_instance = u_CronLibrary.CronLibrary(site="eu_w")

    # Run the needed functions.
    cron_lib_instance.add_render_pools_to_workstations()
    cron_lib_instance.modify_worker_state_for_user_group(user_group="u_OvernightDisableMachine",
                                                     worker_state=True
                                                     )
    cron_lib_instance.modify_worker_state_for_user_group(user_group="u_DisableMachineDuringDay",
                                                     worker_state=False
                                                     )
    cron_lib_instance.reset_user_groups(groups=["u_OvernightDisableMachine"])

def ne_ne_0930_cron():
    """
    This is a cron that will run at 09:30am Mon-Fri in MTL.
    - Adds the render pools back to the MTL workstations.
     """
    # Instantiate the cron library with the site location.
    cron_lib_instance = u_CronLibrary.CronLibrary(site="na_ne")

    # Run the needed functions.
    cron_lib_instance.add_render_pools_to_workstations()

