#!/usr/bin/python

import sys
import create_new_ami_from_instance
import copy_image_to_all_regions
import create_new_launch_config
import phase_out_old_instances_with_new_ones

if len(sys.argv) < 5:
    print('The service_name should include version: eg liveaddress-listprocessing-1.2.3_04')
    exit('Usage: {0} region instance_id auto_scaling_group_name service_name'.format(sys.argv[0]))

REGION = sys.argv[1]
INSTANCE_ID = sys.argv[2]
ASG_NAME = sys.argv[3]
SERVICE_NAME = sys.argv[4]

# requires: REGION, INSTANCE_ID
IMAGE_ID = create_new_ami_from_instance.main(REGION, INSTANCE_ID, SERVICE_NAME)

# requires: REGION, IMAGE_ID
images = copy_image_to_all_regions.main(REGION, IMAGE_ID, SERVICE_NAME)
images[REGION] = IMAGE_ID
print('images: {0}'.format(images))

regions = []
for image in images:
    # requires: REGION, NEW_AMI_ID, OLD_LAUNCH_CONFIGURATION_NAME, NEW_LAUNCH_CONFIGURATION_NAME
    if create_new_launch_config.main(image, images[image], ASG_NAME, SERVICE_NAME):
        regions.append(image) 

for region in regions:
    # requires region auto_scaling_group_name
    phase_out_old_instances_with_new_ones.main(region, ASG_NAME)
