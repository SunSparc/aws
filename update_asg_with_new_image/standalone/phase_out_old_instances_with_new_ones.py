#!/usr/bin/python

import sys
import time
import boto.ec2.autoscale

if len(sys.argv) < 3:
    exit('Usage: {0} region auto_scaling_group_name'.format(sys.argv[0]))

REGION = sys.argv[1]
AUTOSCALING_GROUP_NAME = sys.argv[2]

asConnection = boto.ec2.autoscale.connect_to_region(REGION)
ec2Connection = boto.ec2.connect_to_region(REGION)

def get_group():
    return asConnection.get_all_groups(names=[AUTOSCALING_GROUP_NAME])[0]

group = get_group()
if group.desired_capacity == 0:
    exit('There are no instances to phase out.')
else:
    DESIRED_CAPACITY = group.desired_capacity
    NEW_DESIRED_CAPACITY = group.desired_capacity * 2

original_instances = []
def get_group_instances():
    instances = []
    for instance in asConnection.get_all_autoscaling_instances():
        if instance.instance_id in original_instances:
            continue
        if instance.group_name == AUTOSCALING_GROUP_NAME:
            instances.append(ec2Connection.get_only_instances([instance.instance_id])[0])
    return instances

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

def get_new_instances_status():
    instances = get_group_instances()
    instances_state = []
    for instance in instances:
        instances_state.append(instance.state)
    if 'running' in instances_state:
        return True
    else:
        return False

#monitor the new instances
print('\nWaiting for all new instances to be ready...')
while not get_new_instances_status():
    sys.stdout.write('.')
    sys.stdout.flush()
    time.sleep(10)
else:
    print('\nNew instances are live, old ones are terminating.')
    # When new instances are live, terminate same number of instances that we launched
    # This requires Termination Policies to be: OldestLaunchConfiguration, OldestInstance
    group.set_capacity(DESIRED_CAPACITY)
