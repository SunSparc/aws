#!/usr/bin/python

import sys
import time
import boto.ec2

if len(sys.argv) < 3:
    print('Given the region and id that an AMI images is currently in, this script will copy it to other regions.')
    exit('Usage: {0} region image_id'.format(sys.argv[0]))

REGION = sys.argv[1]
IMAGE_ID = sys.argv[2]

new_images = {}
regions = ('us-east-1', 'us-west-1', 'us-west-2')
for region in regions:
    if region == REGION:
        continue

    # Connect to the region the image will be copied to
    ec2Connection = boto.ec2.connect_to_region(region)
    # Copy the image from the source region to the current region
    new_images[region] = ec2Connection.copy_image(source_region=REGION,
                                                  source_image_id=IMAGE_ID,
                                                  name='copy-of-{0}-from-{1}'.format(IMAGE_ID, REGION),
                                                  description='This is a copy of an AMI from some other region.'
                                                  ).image_id

print('new images: {0}'.format(new_images))

def get_image_state(region):
    image = ec2Connection.get_all_images(image_ids=[new_images[region]], owners=['self'])[0]
    if image.state == 'failed':
        exit('Image ({0}) could not be copied.'.format(image.id))
    if image.state == 'pending':
        return False
    if image.state == 'available':
        return True

# Now we watch and wait for the new images to be available
for region in new_images:
    ec2Connection = boto.ec2.connect_to_region(region)
    while not get_image_state(region):
        time.sleep(5)

print('All new images are available.')
