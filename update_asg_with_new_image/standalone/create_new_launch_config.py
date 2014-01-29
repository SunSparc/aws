#!/usr/bin/python

import sys
#import argparse
import boto.ec2.autoscale
from boto.ec2.autoscale import LaunchConfiguration

if len(sys.argv) < 5:
    exit('Usage: {0} region new_ami_id old_launch_configuration_name new_launch_configuration_name'.format(sys.argv[0]))

# Accept Region, new AMI ID, Old Launch Config Name
REGION = sys.argv[1]
NEW_AMI_ID = sys.argv[2]
OLD_LAUNCH_CONFIGURATION_NAME = sys.argv[3]
NEW_LAUNCH_CONFIGURATION_NAME = sys.argv[4]

asConnection = boto.ec2.autoscale.connect_to_region(REGION)

def create_launch_config():
    oldLC = asConnection.get_all_launch_configurations(names=[OLD_LAUNCH_CONFIGURATION_NAME])[0]
    if not oldLC:
        exit('Old launch configuration does not exist') 

    if oldLC.instance_monitoring.enabled == 'true':
        monitoring = True
    else:
        monitoring = False

    launchconfig = LaunchConfiguration(
        name = NEW_LAUNCH_CONFIGURATION_NAME,
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
        group = get_asg_attachment(oldLC.name)

        if group:
            # The old launch configuration is attached to a group
            group.launch_config_name = NEW_LAUNCH_CONFIGURATION_NAME
            group.update()

        # The old launch configuration is no longer attached to a group, we can delete it
        #delete_result = asConnection.delete_launch_configuration(oldLC.name) # delete returns request id
    else:
        print('Failed to create a new launch configuration.')
        return False


def get_asg_attachment(lc):
    for asg in asConnection.get_all_groups():
        if asg.launch_config_name == lc:
            return asg
    return None


# Create a new launch config
create_launch_config()
