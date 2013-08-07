#!/usr/bin/python

## Requirements:
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
import boto.ec2.autoscale
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import AutoScaleConnection
from boto.ec2.autoscale import AutoScalingGroup
from boto.ec2.autoscale import ScalingPolicy
import boto.ec2.cloudwatch
from boto.ec2.cloudwatch import MetricAlarm

##############################################
######### START SCRIPT CONFIGURATIONS ########
##############################################

# The location of the User Data script file
USER_DATA_SCRIPT_FILE = 'user-data' # the file "user-data" in the current directory

# IAM Role Name 
INSTANCE_PROFILE_NAME = 'AWS IAM Role Name'

# A dictionary of regions that you want to work with
# Other than the region name, the only thing you need to specify is the AMI image id.
global REGIONS
REGIONS = {
    'us-east-1':{
        'image':'ami-9597e1fc',
        'zones':[]
        }, # Virginia
    'us-west-2':{
        'image':'ami-e78212d7',
        'zones':[]
        }, # Oregon
}

# Default region
CURRENT_REGION = 'us-east-1'

##############################################
########## END SCRIPT CONFIGURATIONS #########
##############################################

INSTANCE_TYPE_LIST = [
    't1.micro',
    'm1.small',
    'm1.medium',
    'm1.large',
    'm1.xlarge',
    'm3.xlarge',
    'm3.2xlarge',
    'c1.medium',
    'c1.xlarge',
    'm2.xlarge',
    'm2.2xlarge',
    'm2.4xlarge',
    'cr1.8xlarge',
    'hi1.4xlarge',
    'hs1.8xlarge',
    'cc1.4xlarge',
    'cg1.4xlarge',
    'cc2.8xlarge',
]

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
    REGIONS[CURRENT_REGION]['zones']
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

def select_security_groups():
    print('\nList of Security Groups:')
    count = 1
    groups = {}
    for group in SECURITY_GROUPS_LIST:
        print('%s) %s' % (count, group.name))
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
    choice = raw_input('Are you sure you want to delete: "%s"? (y/n) ' % lcName).lower()
    if choice == 'y':
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
    raw_input('(Press Enter to continue)')
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
        connection=asConnection
        )
    asConnection.create_auto_scaling_group(asgroup) # returns request id
    # asgroup.get_activities() OR asConnection.get_all_activities(asgroup)
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
            #print '  - load_balancers: %s' % group.load_balancers
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

## TODO: Add methods for managing instances of groups: list instances, delete instances

def manage_groups():
    clear()
    print('\n')
    print('-----------------------------')
    print('  Manage AutoScaling Groups')
    print('-----------------------------')
    print('\r')
    print('AutoScaling Group Lists:')
    groups = read_groups(True)
    print('\r')
    print('Actions:')
    print('0) Return to Main')
    print('1) Create new Group')
    print('2) Update existing Group')
    print('3) Delete an Group')
    # Get group activities: group.get_activities(), for activity in group[0].get_activities():
    choice = get_choice([0, 1, 2, 3])

    if choice == 0:
        return True
    elif choice == 1:
        create_group()
    elif choice == 2:
        #group_number = int(raw_input('Enter Group # to update: '))
        #update_group(groups[group_number].name)
        pass
    elif choice == 3:
        delete_group(groups)

    print('\r')
    raw_input('(Press Enter to continue)')
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
    print('2) Update existing Policy')
    print('3) Delete a Policy')
    print('\nNote: An AutoScaling Group can have multiple policies.\n')
    choice = get_choice([0, 1, 2, 3])

    if choice == 0:
        return True
    elif choice == 1:
        create_policies()
    elif choice == 2:
        policy_number = int(raw_input('Enter Policy # to update: '))
        update_policies(policies[policy_number].name)
    elif choice == 3:
        delete_policies()
        pass

    print('\r')
    choice = raw_input('(Press Enter to continue)')
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

def manage_alarms():
    pass


#############################################
################ END ALARMS #################
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
    # If there are only two regions, just toggle to the next one
    if len(REGIONS) == 2:
        print('only 2')
    else:
        print('len: %s' % len(REGIONS))
    print('\n')
    global CURRENT_REGION
    print('Current Region: %s' % CURRENT_REGION)
    print('Available Regions:')
    for region in REGIONS:
        print('%s) %s' % (region,REGIONS[region]))
    print('\n')

    choice = None
    while choice not in REGIONS:
        choice = int(raw_input('#: ')) # TODO: Handle bad input (strings)
        #print('That was not one of the choices.')
    else:
        CURRENT_REGION = REGIONS[choice]
        #make reconnections
        make_connections()
    raw_input('enter to continue')
#while not AUTOSCALING_GROUP_NAME:
#               AUTOSCALING_GROUP_NAME = raw_input('Enter a name for this new group: ')
#       if choice in REGIONS:
#               CURRENT_REGION = REGIONS[choice]
#       else:
#               print('That was not one of the choices.')
#               time.sleep(2)
#               change_region()


def clear():
    # OS agnostic method to clear the terminal screen (thanks StackOverflow)
    os.system( [ 'clear', 'cls' ][ os.name == 'nt' ] )

def make_connections():
    connect_to_autoscale()
    connect_to_cloudwatch()
    connect_to_ec2()

# @param choices, required, a list of choices
# @param choice_type, optional, defaults to int
def get_choice(choices=[], choice_type='int'):
    if not choices:
        return
    choice = None
    while choice not in choices:
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


# Control Method
def main():
    make_connections()
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
    print('1) Change current region')
    print('2) Get AutoScaling status')
    print('3) Manage Launch Configurations')
    print('4) Manage AutoScaling Groups') ##### WORKING HERE #####
    print('5) Manage Policies')
    print('6) Manage Alarms')
    # TODO: Add an option to quickly setup everything (LC, ASG, P, A) just using the defaults.
    print('...')
    print('10) Delete all Autoscaling elements in the current region')
    print('\n')

    choice = get_choice([0, 1, 2, 3, 4, 5, 6, 10])

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

'''
Add a "help" option or just add to documentation.
Education:
 - AutoScaling is created in this order:
   - 1) Launch Configuration
   - 2) AutoScaling Group
   - 3) Policies
 - AutoScaling is deleted in the reverse order.
'''

