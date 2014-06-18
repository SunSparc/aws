#!/usr/bin/python

import datetime, time
import boto, boto.ec2

def main(REGION, AMI_ID, USER_DATA, SECURITY_GROUPS):
    if not REGION or not USER_DATA or not AMI_ID:
        print("** CRITICAL - Missing required configuration settings. Aborting.")
        exit(1)

    ec2Connection = boto.ec2.connect_to_region(REGION)
    if ec2Connection is None:
        print("** CRITICAL - Problem connecting to EC2.")
        exit(1)

    reservation = ec2Connection.run_instances(
        image_id=AMI_ID,
        min_count=1,
        max_count=1,
        security_groups=SECURITY_GROUPS,
        user_data=USER_DATA,
        instance_type='c3.xlarge',
        instance_initiated_shutdown_behavior='stop');
    instance = reservation.instances[0]

    ec2Connection.create_tags([instance.id], {'Name': 'AMI UPDATING'})

    instanceStartTime = datetime.datetime.strptime(instance.launch_time, '%Y-%m-%dT%H:%M:%S.%fZ')
    instanceState = ''
    while instanceState != 'stopped':
        if (datetime.datetime.now() - instanceStartTime).seconds >= 3300:
            exit('Error: New instance has not updated in the time allotted.')
        time.sleep(15)
        instanceState = instance.update()

    print('New instance has finised updating.')
    return instance.id

if __name__ == '__main__':
    REGION='us-east-1'
    AMI_ID='ami-0123456'
    USER_DATA='#none'
    SECURITY_GROUPS=['group name']
    main(REGION, AMI_ID, USER_DATA, SECURITY_GROUPS)
