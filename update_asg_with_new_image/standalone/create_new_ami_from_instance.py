#!/usr/bin/python

import sys
import time
import boto.ec2

if len(sys.argv) < 3:
    exit('Usage: {0} region instance_id Z'.format(sys.argv[0]))

REGION = sys.argv[1]
INSTANCE_ID = sys.argv[2]

ec2Connection = boto.ec2.connect_to_region(REGION)
new_image_id = ec2Connection.create_image(
    instance_id=INSTANCE_ID, # The ID of the instance to image
    name='new_image-{0}'.format(time.time()), # The name of the new image, must be unique
    description='', # An optional human-readable string describing the contents and purpose of the AMI
    )
print('New image ID: {0}'.format(new_image_id))

def get_image_creation_status():
    new_image = ec2Connection.get_all_images(image_ids=[new_image_id], owners=['self'])[0]
    return new_image.state

new_image_status = None
while new_image_status != 'available':
    new_image_status = get_image_creation_status()
    if new_image_status == 'failed':
        exit('Image creation failed!')
    print('state: {0}'.format(new_image_status))
    time.sleep(15)

#return the new ami id
print('New image is ready, ID: {0}'.format(new_image_id))
