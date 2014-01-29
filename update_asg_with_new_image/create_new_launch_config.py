#!/usr/bin/python

import sys
#import argparse
import boto.ec2.autoscale
from boto.ec2.autoscale import LaunchConfiguration

def main(REGION, NEW_AMI_ID, ASG_NAME, SERVICE_NAME):
    print('Creating new launch config in the "{0}" region.'.format(REGION))
    asConnection = boto.ec2.autoscale.connect_to_region(REGION)
    try:
        group = asConnection.get_all_groups([ASG_NAME])[0]
    except IndexError as i:
        print('Apparently there is no group named "{0}" in the "{1}" region.'.format(ASG_NAME, REGION))
        return False # This region does not have the ASG we are looking for, moving on to next region.

    if group.launch_config_name == SERVICE_NAME:
        exit('Launch Config name must be unique: {0}'.format(SERVICE_NAME))

    oldLC = asConnection.get_all_launch_configurations(names=[group.launch_config_name])[0]
    if not oldLC:
        exit('Old launch configuration does not exist') 

    if oldLC.instance_monitoring.enabled == 'true':
        monitoring = True
    else:
        monitoring = False

    launchconfig = LaunchConfiguration(
        name = SERVICE_NAME,
        image_id = NEW_AMI_ID,
        instance_profile_name = oldLC.instance_profile_name,
        key_name = oldLC.key_name,
        ebs_optimized = oldLC.ebs_optimized,
        user_data = oldLC.user_data,
        instance_type = oldLC.instance_type,
        instance_monitoring = monitoring,
        security_groups = oldLC.security_groups,
        )
    # create returns a request id
    if asConnection.create_launch_configuration(launchconfig):
        if group:
            group.launch_config_name = SERVICE_NAME
            group.update()

        # The old launch configuration is no longer attached to a group, we can delete it
        #delete_result = asConnection.delete_launch_configuration(oldLC.name) # delete returns request id

        print('Created the launch config "{0}" in the "{1}" region.'.format(SERVICE_NAME, REGION))
        return True
    else:
        print('Failed to create a new launch configuration in "{0}" region.'.format(REGION))
        return False
