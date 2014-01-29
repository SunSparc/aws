#!/usr/bin/python

import sys
import time
import boto.ec2

#if len(sys.argv) < 3:
#    exit('Usage: {0} region instance_id'.format(sys.argv[0]))

#REGION = sys.argv[1]
#INSTANCE_ID = sys.argv[2]

def get_image_creation_status(ec2Connection, new_image_id):
    # if we are checking status and AWS is slow, the image may not yet exist and this call may fail
    # in that case, we may need to try/except
    new_image = ec2Connection.get_all_images(image_ids=[new_image_id], owners=['self'])[0]
    return new_image.state

def main(REGION, INSTANCE_ID, SERVICE_NAME):
    ec2Connection = boto.ec2.connect_to_region(REGION)
    new_image_id = ec2Connection.create_image(
        instance_id=INSTANCE_ID, # The ID of the instance to image
        name='{0}-{1}'.format(SERVICE_NAME, time.time()), # The name of the new image, must be unique
        description='', # An optional human-readable string describing the contents and purpose of the AMI
        )
    print('New image ID: {0}'.format(new_image_id))

    new_image_status = None
    while new_image_status != 'available':
        new_image_status = get_image_creation_status(ec2Connection, new_image_id)
        if new_image_status == 'failed':
            exit('Image creation failed!')
        print('state: {0}'.format(new_image_status))
        time.sleep(15)

    #return the new ami id
    print('New image is ready, ID: {0}'.format(new_image_id))
    return new_image_id
