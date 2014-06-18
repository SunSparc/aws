#!/usr/bin/python

import sys
import time
import boto.ec2.autoscale
from boto.ec2.autoscale.tag import Tag

asConnection = None
ec2Connection = None
AUTOSCALING_GROUP_NAME = None
original_instances = []

def get_group():
    try:
        return asConnection.get_all_groups(names=[AUTOSCALING_GROUP_NAME])[0]
    except IndexError:
        print('Apparently there is no group named "{0}" in the "{1}" region.'.format(AUTOSCALING_GROUP_NAME, asConnection.region.name))

def get_group_instances():
    instances = []
    for instance in asConnection.get_all_autoscaling_instances():
        if instance.instance_id in original_instances:
            continue
        if instance.group_name == AUTOSCALING_GROUP_NAME:
            instances.append(ec2Connection.get_only_instances([instance.instance_id])[0])
    return instances

def get_new_instances_status():
    instances = get_group_instances()
    instances_state = []
    for instance in instances:
        instances_state.append(instance.state)
    if 'running' in instances_state:
        return True
    else:
        return False

def main(REGION, ASG_NAME, SERVICE_NAME):
    print('Current region: {0}'.format(REGION))
    global AUTOSCALING_GROUP_NAME
    AUTOSCALING_GROUP_NAME = ASG_NAME
    global asConnection
    asConnection = boto.ec2.autoscale.connect_to_region(REGION)
    global ec2Connection
    ec2Connection = boto.ec2.connect_to_region(REGION)

    print('Adding the tag "{0}" to the "{1}" group.'.format(SERVICE_NAME, ASG_NAME))
    tag = Tag(key='Name', value=SERVICE_NAME, propagate_at_launch=True, resource_id=ASG_NAME)
    asConnection.create_or_update_tags([tag])

    group = get_group()
    if group.desired_capacity == 0:
        exit('There are no instances to phase out.')
    else:
        DESIRED_CAPACITY = group.desired_capacity
        NEW_DESIRED_CAPACITY = group.desired_capacity * 2

    global original_instances
    if not original_instances:
        for instance in get_group_instances():
            original_instances.append(instance.id)
    # TODO: ?? check if group.max_size is smaller than what we intend to launch

    # Launch same number of instances that are now running
    group.set_capacity(NEW_DESIRED_CAPACITY)
    print('Waiting for group capacity to be updated from {0} to {1}..'.format(DESIRED_CAPACITY, NEW_DESIRED_CAPACITY))
    while get_group().desired_capacity != NEW_DESIRED_CAPACITY:
        sys.stdout.write('.')
        sys.stdout.flush()
        time.sleep(5)

    #monitor the new instances
    print('\nWaiting for all new instances to be ready...')
    while not get_new_instances_status():
        sys.stdout.write('.')
        sys.stdout.flush()
        time.sleep(10)
    else:
        # When new instances are live, terminate same number of instances that we launched
        # This requires Termination Policies to be: OldestLaunchConfiguration, OldestInstance
		# TODO?? Sometimes the instances that get terminated are the original ones.
		# To avoid this we could specify which instances to terminate and manually scale in the group.
        # Or we can just let scaling policies take capacity back down for us.
        #group.set_capacity(DESIRED_CAPACITY)
        print('\nNew instances are live.')
