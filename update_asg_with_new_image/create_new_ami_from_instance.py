#!/usr/bin/python

import sys
import time
import boto.ec2

def get_image_creation_status(ec2Connection, new_image_id):
    # if we are checking status and AWS is slow, the image may not yet exist and this call may fail
	try:
		new_image = ec2Connection.get_all_images(image_ids=[new_image_id], owners=['self'])[0]
		return new_image.state
	except EC2ResponseError:
		return 'does not yet exist'

def main(REGION, INSTANCE_ID, SERVICE_NAME):
    ec2Connection = boto.ec2.connect_to_region(REGION)

    block_device_type = boto.ec2.blockdevicemapping.BlockDeviceType()
    block_device_type.volume_type='gp2'
    block_device_mapping = boto.ec2.blockdevicemapping.BlockDeviceMapping()
    block_device_mapping['/dev/sda1'] = block_device_type

    new_image_id = ec2Connection.create_image(
        instance_id=INSTANCE_ID, # The ID of the instance to image
        #name='{0}-{1}'.format(SERVICE_NAME, time.time()), # The name of the new image, must be unique
        name='{0}'.format(SERVICE_NAME),
        description='', # An optional human-readable string describing the contents and purpose of the AMI
        block_device_mapping=block_device_mapping,
        )
    print('New image ID: {0}'.format(new_image_id))

    new_image_status = None
    while new_image_status != 'available':
        time.sleep(15)
        new_image_status = get_image_creation_status(ec2Connection, new_image_id)
        if new_image_status == 'failed':
            exit('Image creation failed!')
        print('state: {0}'.format(new_image_status))

    #return the new ami id
    print('New image is ready, ID: {0}'.format(new_image_id))
    ec2Connection.terminate_instances([INSTANCE_ID])
    return new_image_id

if __name__ == "__main__":
    REGION='us-east-1'
    INSTANCE_ID='i-0a1b2c4d'
    SERVICE_NAME='Manual Test of create_new_ami_from_instance.py'
    IMAGE_ID = main(REGION, INSTANCE_ID, SERVICE_NAME)
