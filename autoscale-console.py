#!/usr/bin/python

## Requirements:
##  - Boto: http://boto.readthedocs.org/en/latest/getting_started.html
##  - AWS user credentials stored in ~/.boto
##  - User Data file
##  - IAM Role with permissions to access certain resources
##
## An Interactive AutoScale Console Script
##
## This script is an effort to make AutoScaling administration
## much easier. I fully expect Amazon to eventually add an
## interface for AutoScaling to their web console. Until such
## time, I hope that this script will suffice or even lead to
## better interfaces.
##
## Author: Jonathan Duncan
## Date: July 2013
##

import os
import sys
import datetime
import time
import ConfigParser
import boto.ec2.autoscale
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import AutoScaleConnection
from boto.ec2.autoscale import AutoScalingGroup
from boto.ec2.autoscale import ScalingPolicy
import boto.ec2.cloudwatch
from boto.ec2.cloudwatch import MetricAlarm
import boto.ec2.elb

##############################################
######### START SCRIPT CONFIGURATIONS ########
##############################################

CONFIG_FILENAME = 'config.cfg'
if os.path.isfile(CONFIG_FILENAME):
        config = ConfigParser.RawConfigParser()
        config.read(CONFIG_FILENAME)
else:
    sys.exit('Config file "%s" does not exist.' % CONFIG_FILENAME)

USER_DATA_SCRIPT_FILE = config.get('AutoScaling', 'user_data_script_file') 
INSTANCE_PROFILE_NAME = config.get('AutoScaling', 'instance_profile_name')
CURRENT_REGION = config.get('AutoScaling', 'default_region')

# Get list of regions:  ec2Connection.get_all_regions()
global REGIONS
REGIONS = {}
for region in config.items('Regions'):
    REGIONS[region[0]] = {'image': region[1], 'zones':[]}

DATE_FORMAT = '%Y.%m.%d-%H:%M:%S'

INSTANCE_TYPE_LIST = []
for instance_type in config.items('InstanceTypes'):
    INSTANCE_TYPE_LIST.append(instance_type[0])

##############################################
########## END SCRIPT CONFIGURATIONS #########
##############################################

def connect_to_autoscale():
    global asConnection
    asConnection = boto.ec2.autoscale.connect_to_region(CURRENT_REGION)

# Connect to CloudWatch
def connect_to_cloudwatch():
    global cwConnection
    cwConnection = boto.ec2.cloudwatch.connect_to_region(CURRENT_REGION)

def connect_to_ec2():
    global ec2Connection
    ec2Connection = boto.ec2.connect_to_region(CURRENT_REGION)
    # Get availability zones
    REGIONS[CURRENT_REGION]['zones'] = []
    for zone in ec2Connection.get_all_zones():
        REGIONS[CURRENT_REGION]['zones'].append(zone.name)
    # Get security groups
    # security group methods: ['add_rule', 'add_tag', 'authorize', 'connection', 'copy_to_region', 'delete', 'description', 'id', 'instances', 'item', 'name', 'owner_id', 'region', 'remove_rule', 'remove_tag', 'revoke', 'rules', 'rules_egress', 'tags', 'vpc_id']
    global SECURITY_GROUPS_LIST
    SECURITY_GROUPS_LIST = ec2Connection.get_all_security_groups()
    # Get key pairs
    # key pair methods: ['connection', 'copy_to_region', 'delete', 'fingerprint', 'item', 'material', 'name', 'region', 'save']
    global KEY_PAIR_LIST
    KEY_PAIR_LIST = ec2Connection.get_all_key_pairs()

def connect_to_elb():
    global elbConnection
    elbConnection = boto.ec2.elb.connect_to_region(CURRENT_REGION)

def select_security_groups():
    print('\nList of Security Groups:')
    count = 1
    groups = {}
    for group in SECURITY_GROUPS_LIST:
        print('%s) %s (%s)' % (count, group.name, group.id))
        groups[count] = group.name
        count += 1
    print('\nWhich security groups do you want to use?')
    print('(Separate multiple group numbers with a comma.)')
    selectedSecurityGroups = []
    while not selectedSecurityGroups:
        response = raw_input('#: ')
        responseList = response.split(',')
        for sg in responseList:
            sg = int(sg.strip())
            if sg in groups:
                selectedSecurityGroups.append(groups[sg])
            else:
                print('%s was not a valid option, discarding...' % sg)

    #print('sSG: %s, ' % selectedSecurityGroups)
    #print('SECURITY_GROUPS_LIST: %s' % SECURITY_GROUPS_LIST)
    #print('groups: %s' % groups)
    return selectedSecurityGroups

def select_key_pair():
    # *****************
    print('\nList of Key Pairs:')
    count = 1
    listDict = {}
    for keypair in KEY_PAIR_LIST:
        print('%s) %s' % (count, keypair.name))
        listDict[count] = keypair.name
        count += 1
    print('\nWhich key pair do you want to use?')
    #choice = get_int()
    choice = get_choice(range(1, len(listDict)+1))
    #print('choice: %s, ' % choice)
    #print('KEY_PAIR_LIST: %s' % KEY_PAIR_LIST)
    #print('listDict: %s' % listDict)
    #print('listDict[choice]: %s' % listDict[choice])
    return listDict[choice]

def select_instance_type():
    print('\nList of Instance Types')
    count = 1
    listDict = {}
    for itype in INSTANCE_TYPE_LIST:
        print('%s) %s' % (count, itype))
        listDict[count] = itype
        count += 1
    print('\nWhich instance type do you want to use?')
    print('(Instance Type details: http://aws.amazon.com/ec2/instance-types/#instance-details )')
    #choice = get_int()
    choice = get_choice(range(1, len(listDict)+1))
    #print('choice: %s' % choice)
    #print('listDict[choice]: %s' % listDict[choice])
    return listDict[choice]

def select_availability_zones():
    print('\nAvailability Zones')
    count = 1
    listDict = {}
    for az in REGIONS[CURRENT_REGION]['zones']:
        print('%s) %s' % (count, az))
        listDict[count] = az
        count += 1
    print('\nWhich availability zones do you want to use?')
    print('\n(Type the AZ number. Enter the same number to remove the selection. When done enter 0.)')
    choice = False
    choices = []
    while choice is not 0:
        print('(Selected Zones: %s)' % choices)
        choice = get_choice(range(0, len(listDict)+1))
        if choice is 0:
            break
        if choice in choices:
            choices.remove(choice)
        else:
            choices.append(choice)
    azList = []
    for az in choices:
        azList.append(listDict[az])
    return azList



#############################################
######## START LAUNCH CONFIGURATIONS ########
#############################################

## Create a Launch Configuration
def create_launch_config():
    # Load the User Data file
    with open(USER_DATA_SCRIPT_FILE) as userDataScriptFile:
        userDataScript = userDataScriptFile.read()

    print('\nEnter a name for the Launch Configuration')
    lcName = raw_input(': ')
    # Make the Launch Configuration name unique with a timestamp
    lcName = lcName + '-' + datetime.datetime.utcnow().strftime('%Y.%m.%d-%H%M%S')

    # Use Monitoring?
    # Use User Data?
    # Use load balancers?
    # Use ami from config or specify?
    # Use IAM role?
    global INSTANCE_PROFILE_NAME
    if INSTANCE_PROFILE_NAME == 'AWS IAM Role Name':
        print('Warning: You have not configured your INSTANCE_PROFILE_NAME. Disabling use of IAM role.')
        INSTANCE_PROFILE_NAME = None

    launchconfig = LaunchConfiguration(
        name=lcName,
        image_id=REGIONS[CURRENT_REGION]['image'],
        instance_type=select_instance_type(),
        key_name=select_key_pair(),
        security_groups=select_security_groups(),
        instance_profile_name=INSTANCE_PROFILE_NAME,
        user_data=userDataScript
        )
    # create returns a request id
    if asConnection.create_launch_configuration(launchconfig):
        print('Successfully created a new launch configuration.')
        return lcName
    else:
        print('Failed to create a new launch configuration.')
        return False

## Show specific launch configs
# asConnection.get_all_launch_configurations(names=['liveaddress-listprocessing-2013.06.28-1825'])
def read_launch_configs(get=False):
    count = 1
    listDict = {}
    #asConnection.get_all_launch_configurations(names=[LAUNCH_CONFIG_NAME])
    for lc in asConnection.get_all_launch_configurations():
        details = ('created: %s, image id: %s, instance type: %s, attached: %s'
            % (lc.created_time.strftime('%Y.%b.%d %H:%M:%S'), lc.image_id, lc.instance_type, get_asg_attachment(lc.name,True))
        )
        if get:
            print('%s) %s (%s)' % (count, lc.name, details))
            listDict[count] = lc
        else:
            print('- %s (%s)' % (lc.name, details))
        count += 1
    return listDict

## If we already have a LC and want to update it, we have to create a new one, point the ASG to the new one, then delete the old LC
def update_launch_config(launchConfigs):
    print('\nIt is not possible to update a Launch Configuration.')
    print('However, we can do the following:')
    print(' - create a new Launch Configuration')
    print(' - assign it to the same AutoScaling Group')
    print(' - delete the old Launch Configuration\n')
    print('Enter the Launch Configuration number to "update"')
    lc_number = get_int()
    oldLCName = launchConfigs[lc_number].name

    # Get the group object
    group = get_asg_attachment(oldLCName)
    if not group:
        print('Cannot update a Launch Configuration that is not attached to a group.')
        print('Try deleting the Launch Configuration and creating a new one.')
        return False

    # Create a new launch config
    newLCName = create_launch_config()

    # Assign the new Launch Configuration name to the ASG
    group.launch_config_name = newLCName
    # Update the group
    group.update()
    # Kill the launch configuration
    #connection[CURRENT_REGION].delete_launch_configuration(oldLaunchConfigName)
    if raw_input('Do you want to delete the old Launch Config? (y/n) ').lower() == 'y':
        delete_launch_config(oldLCName)
    print('New Launch Configuration successfully attached to the AutoScaling Group in place of the old one.')
    return True

def delete_launch_config(lcName=None):
    if not lcName:
        return False
    group = get_asg_attachment(lcName)
    if group:
        print('Cannot delete Launch Configuration "%s", it is attached to the AutoScaling Group "%s".' % (lcName, group.name))
        return False
    if raw_input('Are you sure you want to delete: "%s"? (y/n) ' % lcName).lower() == 'y':
        # Make sure that this Launch Configuration is not attached to an Auto Scaling Group
        try:
            delete_result = asConnection.delete_launch_configuration(lcName) # delete returns request id
            print('\nDelete Successful (%s)' % delete_result)
        except:
            print "\nError trying to delete:", sys.exc_info()[0]
    else:
        return False
    print('\n')

def get_asg_attachment(lc,name=False):
    for asg in asConnection.get_all_groups():
        if asg.launch_config_name == lc:
            if name:
                return asg.name
            else:
                return asg
    return None

'''
lc object members: ['EbsOptimized', 'block_device_mappings', 'connection', 'created_time', 'delete', 'endElement', 'image_id', 'instance_monitoring', 'instance_profile_name', 'instance_type', 'kernel_id', 'key_name', 'launch_configuration_arn', 'member', 'name', 'ramdisk_id', 'security_groups', 'spot_price', 'startElement', 'user_data']
'''
def manage_launch_configs():
    clear()
    print('\n')
    print('--------------------------------')
    print('  Manage Launch Configurations')
    print('--------------------------------')
    print('\r')
    print('Launch Config List:')
    launchconfigs = read_launch_configs(True)
    print('\r')
    print('Actions:')
    print('0) Return to Main')
    print('1) Create new Launch Configuration')
    print('2) Update existing Launch Configuration')
    print('3) Delete a Launch Configuration')
    choice = int(raw_input('#: '))

    if choice == 0:
        return True
    elif choice == 1:
        create_launch_config()
    elif choice == 2:
        update_launch_config(launchconfigs)
    elif choice == 3:
        lc_number = int(raw_input('Enter Launch Config # to delete: '))
        delete_launch_config(launchconfigs[lc_number].name)

    print('\r')
    raw_input('(Press Enter to continue.)')
    manage_launch_configs()

#############################################
######### END LAUNCH CONFIGURATIONS #########
#############################################

#############################################
######### START AUTOSCALING GROUPS ##########
#############################################

## Create an AutoScaling group
def create_group():
    # Get the list of LC's
    print('\nLaunch Configuration List')
    launchconfigs = read_launch_configs(True)
    if len(launchconfigs) < 1:
        print('You have not yet created a Launch Configuration.')
        return

    print('\n')
    print('Enter the Launch Configuration number to use:')
    lc_number = get_choice(range(1, len(launchconfigs)+1))
    launchConfigName = launchconfigs[lc_number].name

    autoscalingGroupName = None
    while not autoscalingGroupName:
        autoscalingGroupName = raw_input('Enter a name for this new AutoScaling Group: ')

    print('Enter the Minimum Size')
    GROUP_MIN_SIZE = get_int()
    print('Enter the Maximum Size')
    GROUP_MAX_SIZE = 0
    while GROUP_MAX_SIZE is 0:
        GROUP_MAX_SIZE = get_int()
    print('Enter the default cooldown in seconds (default is 300 (5 minutes))')
    DEFAULT_COOLDOWN = get_int()
    print('Enter the desired capacity (number of instances to always have running)')
    DESIRED_CAPACITY = get_int()

    asgroup = AutoScalingGroup(
        group_name=autoscalingGroupName,
        availability_zones=REGIONS[CURRENT_REGION]['zones'],
        launch_config=launchConfigName,
        min_size = GROUP_MIN_SIZE,
        max_size = GROUP_MAX_SIZE,
        default_cooldown = DEFAULT_COOLDOWN,
        desired_capacity = DESIRED_CAPACITY,
        tag='k=Name, v=ASGMinion, p=true',
        #TODO: load_balancers = [elb, list] # health_check_type?? [ELB, EC2]
        connection=asConnection
        )
    asConnection.create_auto_scaling_group(asgroup) # returns request id
# end def create_group


## Show specific autoscaling groups
# asConnection.get_all_groups(names=['autoscale group name'])
def read_groups(get=False, details=True):
    count = 1
    listDict = {}
    for group in asConnection.get_all_groups():
        print '%s) name: %s' % (count, group.name)
        if details:
            print '  - created_time: %s' % group.created_time
            print '  - launch_config_name: %s' % group.launch_config_name
            print '  - min_size: %s' % group.min_size
            print '  - max_size: %s' % group.max_size
            print '  - cooldown: %s' % group.cooldown
            print '  - desired_capacity: %s' % group.desired_capacity
            print '  - enabled_metrics: %s' % group.enabled_metrics
            print '  - instances: %s' % group.instances
            # Other available details
            #print '  - autoscaling_group_arn: %s' % group.autoscaling_group_arn
            #print '  - availability_zones: %s' % group.availability_zones
            #print '  - connection: %s' % group.connection
            #print '  - default_cooldown: %s' % group.default_cooldown
            #print '  - health_check_period: %s' % group.health_check_period
            #print '  - health_check_type: %s' % group.health_check_type
            #TODO: check for load_balancers #print '  - load_balancers: %s' % group.load_balancers
            #print '  - placement_group: %s' % group.placement_group
            #print '  - suspended_processes: %s' % group.suspended_processes
            #print '  - tags: %s' % group.tags
            #print '  - termination_policies: %s' % group.termination_policies
        if get:
            listDict[count] = group
        count += 1
    return listDict

# get a specific group
#group = asConnection.get_all_groups(names=[AUTOSCALING_GROUP_NAME])[0] # AutoScaleGroup<AUTOSCALING_GROUP_NAME>
#asg object methods: ['_get_cooldown', '_set_cooldown', 'autoscaling_group_arn', 'availability_zones', 'connection', 'cooldown', 'created_time', 'default_cooldown', 'delete', 'desired_capacity', 'enabled_metrics', 'endElement', 'get_activities', 'health_check_period', 'health_check_type', 'instances', 'launch_config_name', 'load_balancers', 'max_size', 'member', 'min_size', 'name', 'placement_group', 'put_notification_configuration', 'resume_processes', 'set_capacity', 'shutdown_instances', 'startElement', 'suspend_processes', 'suspended_processes', 'tags', 'termination_policies', 'update', 'vpc_zone_identifier']

def update_group():
    # Get list of groups
    read_groups(get=True, details=True)
    # Choose which group to update
    print('Which Group would you like to update?')
    group
    #group = groupList[0]
    # Make some changes
    #get -> group.max_size
    #set -> group.max_size = 50
    # Sync these changes to the group
    #group.update()
    pass

def delete_group(groups=[]):
    if not groups:
        return false
    # Specify which Group to delete
    print('Enter the number of the Group to delete')
    groupToDelete = get_int()
    print('Are you sure you want to delete: %s (y/n)' % groups[groupToDelete].name)
    if get_choice(['y', 'n']) is 'y':
        asConnection.delete_auto_scaling_group(groups[groupToDelete].name) # OR asgroup.delete()
        print('Group was scheduled for deletion')
    else:
        print('Group will not be deleted')

## TODO: Add methods for managing instances of groups: list instances
def list_instances():
    pass

def show_activities(groups):
    # Get list of groups
    #groups = read_groups(get=True, details=True)
    # Choose which group to update
#    print('\nWhich Group would you like to see activity for?')
#    group_number = get_choice(range(1, len(groups)+1))
    group_number = select_group(groups)
    activities = asConnection.get_all_activities(groups[group_number].name, max_records=10)
    for activity in reversed(activities):
        print("\n")
        print('START TIME: %s' % activity.start_time.strftime(DATE_FORMAT))
        if activity.end_time == None:
            print('End time: <none>')
        else:
            print('End time: %s' % activity.end_time.strftime(DATE_FORMAT))
        print('Description: %s' % activity.description)
        print('Cause: %s' % activity.cause)
        print('Progress: %s%%' % activity.progress)
        print('Status code: %s' % activity.status_code)
        print('Status message: %s' % activity.status_message)
        # TODO: if load_balancers, show them
    # TODO: Add option to follow (like tail -f) and have status continually update.
    # Follow mode:
    #   

def terminate_instances(groups):
    #print('\nWhich Group would you like to terminate instances in?')
    #group_number = get_choice(range(1, len(groups)+1))
    group_number = select_group(groups)
    count = 1
    instances = {}
    for instance in groups[group_number].instances:
        print("\n%s) Instance ID: %s" % (count, instance.instance_id))
        print("  - launch_config_name: (%s)" % instance.launch_config_name)
        print("  - availability_zone: (%s)" % instance.availability_zone)
        print("  - lifecycle_state: (%s)" % instance.lifecycle_state)
        print("  - health_status: (%s)" % instance.health_status)
        instances[count] = instance
        count += 1
    print('\nWhich instance do you want to terminate? (0 = terminate all)')
    instance_number = get_choice(range(0, len(groups[group_number].instances)+1))
    if instance_number == 0:
        # Kill all instances by setting group capacity to min_size
        print("Group capacity set to %s. Terminating excess instances." % groups[group_number].min_size)
        asConnection.set_desired_capacity(groups[group_number].name, groups[group_number].min_size)
    else:
        print("Terminating instance: %s" % instances[instance_number].instance_id)
        asConnection.terminate_instance(instances[instance_number].instance_id, decrement_capacity=True)


def select_group(groups):
    group_count = len(groups)
    if group_count == 0:
        print("There are no groups.")
        return False
    elif group_count == 1:
        return 1
    else:
        print('\nSelect a Group.')
        return get_choice(range(1, len(groups)+1))

def manage_groups():
    clear()
    print('\n')
    print('-----------------------------')
    print('  Manage AutoScaling Groups')
    print('-----------------------------')
    print('\n')
    print('AutoScaling Group Lists:')
    groups = read_groups(True)
    print('\n')
    print('Actions:')
    print('0) Return to Main')
    print('1) Create new Group')
    print('2) Update existing Group')
    print('3) Delete an Group')
    print('4) Show Group Activities (10 most recent)')
    print('5) Terminate instances')
    # Get group activities: group.get_activities(), for activity in group[0].get_activities():
    choice = get_choice([0, 1, 2, 3, 4, 5])

    if choice == 0:
        return True
    elif choice == 1:
        create_group()
    elif choice == 2:
        #group_number = int(raw_input('Enter Group # to update: '))
        #update_group(groups[group_number].name)
        print('(No yet implemented.)')
    elif choice == 3:
        delete_group(groups)
    elif choice == 4:
        show_activities(groups)
    elif choice == 5:
        terminate_instances(groups)

    print('\r')
    raw_input('(Press Enter to continue.)')
    manage_groups()
# end def manage_groups

#############################################
########## END AUTOSCALING GROUPS ###########
#############################################

#############################################
############## START POLICIES ###############
#############################################

# Create a policy
def create_policies():
    # The rules for HOW to scale are defined by Scaling Policies, and the rules for WHEN to scale are defined by CloudWatch Metric Alarms.
    # http://docs.aws.amazon.com/AutoScaling/latest/DeveloperGuide/as-scale-based-on-demand.html

    # (str or int) - Name or ARN of the Auto Scaling Group
    POLICY_NAME = raw_input('\nEnter a name for this new Policy: ')

    # Get the list of groups
    print('\n\n')
    groups = read_groups(get=True, details=False)
    if len(groups) < 1:
        print('\nYou have not yet created an AutoScaling Group.')
        return
    # (str or int) - Name or ARN of the Auto Scaling Group
    print('\nEnter the AutoScaling Group number to use:')
    group_number = get_choice(range(1, len(groups)+1))
    POLICY_GROUP = groups[group_number].name

    # (str) - Specifies the type of adjustment. [ChangeInCapacity, ExactCapacity, PercentChangeInCapacity]
    AT_DICT = {1:'ChangeInCapacity', 2:'ExactCapacity', 3:'PercentChangeInCapacity'}
    print('\nEnter the type of adjustment to be made:')
    for at in AT_DICT:
        print('%s) %s' % (at, AT_DICT[at]))
    ADJUSTMENT_TYPE = AT_DICT[get_choice([1,2,3])]

    # (int) - Value of adjustment (type specified in adjustment_type).
    print('\nEnter the adjustment value (e.g. scale up: 1, scale down: -1):')
    SCALING_ADJUSTMENT = get_int()

    # (int) - Time (in seconds) before Alarm related Scaling Activities can start after the previous Scaling Activity ends
    print('\nEnter the cooldown time (in seconds) before Alarm should start (e.g. 180 (3 minutes)):')
    COOLDOWN = get_int()

    create_policy = boto.ec2.autoscale.ScalingPolicy(
        name=POLICY_NAME,
        as_name=POLICY_GROUP,
        adjustment_type=ADJUSTMENT_TYPE,
        scaling_adjustment=SCALING_ADJUSTMENT,
        cooldown=COOLDOWN
        )
    scale_up_policy = asConnection.create_scaling_policy(create_policy)


## Show specific policies
# asConnection.get_all_policies(as_group='', policy_names=['policy name'])
# scale_down_policy = asConnection.get_all_policies(as_group=AUTOSCALING_GROUP_NAME, policy_names=['scale_down'])[0]
def read_policies(get=False):
    count = 1
    listDict = {}
    for policy in asConnection.get_all_policies(as_group=''):
        print '%s) name: %s' % (count, policy.name)
        print '  - group name: %s' % policy.as_name
        print '  - adjustment type: %s' % policy.adjustment_type
        print '  - scaling adjustment: %s' % policy.scaling_adjustment
        print '  - cooldown: %s' % policy.cooldown
        print '  - alarms: %s' % policy.alarms
        #print '  - policy arn: %s' % policy.policy_arn
        if get:
            listDict[count] = policy
        count += 1
    return listDict

def update_policies():
    pass

def delete_policies():
    pass

def manage_policies():
    clear()
    print('\n')
    print('-------------------')
    print('  Manage Policies')
    print('-------------------')
    print('\r')
    print('AutoScaling Policies:')
    policies = read_policies(True)
    print('\r')
    print('Actions:')
    print('0) Return to Main')
    print('1) Create new Policy')
    #print('2) Update existing Policy')
    #print('3) Delete a Policy')
    print('\nNote: An AutoScaling Group can have multiple policies.\n')
    choice = get_choice([0, 1, 2, 3])

    if choice == 0:
        return True
    elif choice == 1:
        create_policies()
    elif choice == 2:
        #policy_number = int(raw_input('Enter Policy # to update: '))
        #update_policies(policies[policy_number].name)
        print('(Not yet implemented.)')
    elif choice == 3:
        print('(Not yet implemented.)')
        #delete_policies()

    print('\r')
    choice = raw_input('(Press Enter to continue.)')
    manage_policies()
# end def manage_policies


#############################################
############### END POLICIES ################
#############################################

#############################################
############### START ALARMS ################
#############################################

##
## This section is not entirely necessary since Amazon has a
## web interface for Alarms in the CloudWatch section of
## their web console.
##

# Create an Alarm
def create_alarm():
    cwConnection = connect_to_cloudwatch()
    # scale_up_policy = find policy
    scale_up_alarm = MetricAlarm(
        name='scale_up_on_cpu',
        metric='Number Of Messages Ready', #'CPUUtilization',
        namespace='SSRMQ:List Processing', #'AWS/EC2',
        statistic='Sum', #'Average',
        comparison='>',
        threshold='0',
        period='60',
        evaluation_periods=0,
        alarm_actions=[scale_up_policy.policy_arn] #,
        #dimensions=alarm_dimensions
        )
    cwConnection.create_alarm(scale_up_alarm)
    # Returns True on success

#
#scale_down_alarm = MetricAlarm(
#       name='scale_down_on_cpu',
#       namespace='AWS/EC2',
#       metric='CPUUtilization',
#       statistic='Average',
#       comparison='<',
#       threshold='40',
#       period='60',
#       evaluation_periods=2,
#       alarm_actions=[scale_down_policy.policy_arn],
#       dimensions=alarm_dimensions
#       )
#cwConnection.create_alarm(scale_down_alarm)
# Returns True on success

def read_alarms():
    for alarm in cwConnection.describe_alarms():
        print '- %s' % alarm
        print('- enabled: %s' % alarm.actions_enabled)
        if alarm.actions_enabled == 'false':
            print('(The actions on this alarm are disabled. Automatically enabling now.')
            alarm.actions_enabled = 'true'
            print('- update: enabled: %s' % alarm.actions_enabled)
            alarm.enable_actions()

#alarm: ['ALARM', 'INSUFFICIENT_DATA', 'OK', 'StateReasonData', 'StateUpdatedTimestamp', '__class__', '__delattr__', '__dict__', '__doc__', '__format__', '__getattribute__', '__hash__', '__init__', '__module__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__', '__weakref__', '_cmp_map', '_rev_cmp_map', 'actions_enabled', 'add_alarm_action', 'add_insufficient_data_action', 'add_ok_action', 'alarm_actions', 'alarm_arn', 'comparison', 'connection', 'delete', 'describe_history', 'description', 'dimensions', 'disable_actions', 'enable_actions', 'endElement', 'evaluation_periods', 'insufficient_data_actions', 'last_updated', 'member', 'metric', 'name', 'namespace', 'ok_actions', 'period', 'set_state', 'startElement', 'state_reason', 'state_value', 'statistic', 'threshold', 'unit', 'update']

def manage_alarms():
    read_alarms()
    choice = raw_input('(Press Enter to continue.)')


#############################################
################ END ALARMS #################
#############################################

#############################################
################ START ELBS #################
#############################################

#def create_elastic_load_balancer():

def read_elastic_load_balancers(get=False):
    count = 1
    listDict = {}
    for elb in elbConnection.get_all_load_balancers():
        print '%s) name: %s (%s)' % (count, elb.name, elb.dns_name)
        print '  - cross zone load balancing: %s' % elb.is_cross_zone_load_balancing()
        print '  - availability zones: %s' % elb.availability_zones
        print '  - instances: %s' % elb.instances
        if get:
            listDict[count] = elb
        count += 1
    return listDict

def update_elb_zones(elbs):
    elb_number = select_elastic_load_balancer(elbs)
    if not elb_number:
        return 1
    elb_zones = select_availability_zones()
    print('Setting %s to use zones: %s' % (elbs[elb_number].name, elb_zones))
    elbConnection.enable_availability_zones(elbs[elb_number].name, elb_zones)


def toggle_cross_zone_load_balancing(elbs):
    elb_number = select_elastic_load_balancer(elbs)
    if elbs[elb_number].is_cross_zone_load_balancing():
       elbs[elb_number].disable_cross_zone_load_balancing() 
    else:
       elbs[elb_number].enable_cross_zone_load_balancing() 

def select_elastic_load_balancer(elbs):
    elb_count = len(elbs)
    if elb_count == 0:
        print("There are no Elastic Load Balancers.")
        return False
    elif elb_count == 1:
        return 1
    else:
        print('\nSelect an Elastic Load Balancer:')
        return get_choice(range(1, len(elbs)+1))

def manage_elastic_load_balancers():
    clear()
    print('\n')
    print('---------------------------------')
    print('  Manage Elastic Load Balancers')
    print('---------------------------------')
    print('\r')
    print('Elastic Load Balancers:')
    elbs = read_elastic_load_balancers(True)
    print('\r')
    print('Actions:')
    print('0) Return to Main')
    print('1) Toggle Cross Zone Load Balancing')
    print('2) Update Availability Zones')
    choice = get_choice([0, 1, 2])

    if choice == 0:
        return True
    elif choice == 1:
        toggle_cross_zone_load_balancing(elbs)
    elif choice == 2:
        update_elb_zones(elbs)

    print('\r')
    choice = raw_input('(Press Enter to continue.)')
    manage_elastic_load_balancers()
# end def manage_elastic_load_balancers

#############################################
################# END ELBS ##################
#############################################



# This will show a listing of all launch configs, autoscaling groups, and policies for this account
def describe_auto_scaling():
    print('------------------------------------------')
    print('  Description of AutoScale for %s' % CURRENT_REGION)
    print('------------------------------------------')
    print('\r')
    print 'Launch Configurations:'
    read_launch_configs()
    print('\r')
    print 'AutoScaling Groups:'
    read_groups()
    print('\r')
    print 'Policies:'
    read_policies()
    print('\r')
    print 'Alarms:'
    read_alarms()
    print('\r')
    raw_input('Press enter when ready.')


# Delete everything
def delete_autoscale():
    return False
    # for policy in policies:
    #   delete_policy()
    # Kill the policy
    asConnection.delete_policy('scale_up', autoscale_group=AUTOSCALING_GROUP_NAME)
    # Kill the AutoScaling group
    asConnection.delete_auto_scaling_group(AUTOSCALING_GROUP_NAME) # OR asgroup.delete()
    # Kill the launch configuration
    asConnection.delete_launch_configuration(LAUNCH_CONFIG_NAME) # OR launchconfig.delete()


def change_region():
    print('All available regions: %s ' % ec2Connection.get_all_regions())
    global CURRENT_REGION
    print('\nCurrent Region: %s' % CURRENT_REGION)
    print('\nAvailable Regions:')
    count = 1
    regions = {}
    for region in REGIONS:
        if region == CURRENT_REGION:
            current = '*'
        else:
            current = ''
            new_region = region
        print('%s) %s%s' % (count, region, current))
        regions[count] = region
        count += 1

    if len(REGIONS) == 2:
        print('\nSwitching to region %s' % new_region)
        CURRENT_REGION = new_region
    else:
        print('\nSelect a region:')
        CURRENT_REGION = regions[get_choice(range(1, len(REGIONS)+1))]

    print('\nResetting connections for new region...\n')
    make_connections()
    raw_input('(Press enter to continue.)')

def clear():
    # OS agnostic method to clear the terminal screen (thanks StackOverflow)
    os.system( [ 'clear', 'cls' ][ os.name == 'nt' ] )

def make_connections():
    print("Connecting to AWS...")
    connect_to_autoscale()
    connect_to_cloudwatch()
    connect_to_ec2()
    connect_to_elb()

# @param choices, required, a list of choices
# @param choice_type, optional, defaults to int
def get_choice(choices=[], choice_type='int'):
    if not choices:
        return
    choice = None
    while choice not in choices:
        #choice = raw_input('# %s: ' % choices) # show choices
        choice = raw_input('#: ')
        try:
            choice = int(choice)
        except ValueError:
            pass
    return choice

def get_int():
    while True:
        user_input = raw_input('#: ')
        try:
            user_input = int(user_input)
            break
        except ValueError:
            print('Please enter an integer.')
    return user_input

INIT = False

# Control Method
def main():
    global INIT
    if INIT == False:
        make_connections()
        INIT = True
    # Print a menu of options
    clear()
    print('\n')
    print('---------------------------')
    print('  AWS AutoScaling Console')
    print('---------------------------')
    print('\n')
    print('Current Region: %s' % CURRENT_REGION)
    print('\n')
    print('Choose an option:')
    print('0) Quit')
    print('1) Switch Region')
    print('2) Status')
    print('3) Launch Configurations')
    print('4) Groups')
    print('5) Policies')
    print('6) Alarms')
    print('7) Elastic Load Balancers')
    print('...')
    print('10) Delete all Autoscaling elements in the current region')
    print('\n')

    choice = get_choice([0, 1, 2, 3, 4, 5, 6, 7, 10])

    if choice == 0:
        print('\nGood-bye\n')
        return 0
    elif choice == 1:
        change_region()
    elif choice == 2:
        describe_auto_scaling()
    elif choice == 3:
        manage_launch_configs()
    elif choice == 4:
        manage_groups()
    elif choice == 5:
        manage_policies()
    elif choice == 6:
        manage_alarms()
    elif choice == 7:
        manage_elastic_load_balancers()
    elif choice == 10:
        print 'Why would you choose such a path of utter destruction?'
        time.sleep(5)
        #delete_autoscale()
    main()
# end def main


if __name__ == '__main__':
    main()

'''
###########################################
## TODO: List of Extra todos
###########################################
'''
## List all instances
#instance_ids = [i.instance_id for i in group.instances] # []
#reservations = ec2.get_all_instances(instance_ids) # []
#instances = [i for r in reservations for i in r.instances]

# Execute a policy manually (bypassing CW alarms)
# Copy Launch Configs, Groups, Policies, Alarms, from one region to another
# Display user-data on existing Launch Config
# If the IAM role is incorrect, the script fails on LC creation. Perhaps there is way to handle this gracefully.
# Instead of having an IAM role name be a global config, perhaps we just ask for it when needed during LC creation.

'''
Add a "help" option or just add to documentation.
Education:
 - AutoScaling is created in this order:
   - 1) Launch Configuration
   - 2) AutoScaling Group
   - 3) Policies
 - AutoScaling is deleted in the reverse order.
'''

