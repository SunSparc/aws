#!/usr/bin/python

import sys
import launch_new_instance
import create_new_ami_from_instance
import copy_image_to_all_regions
import create_new_launch_config
import phase_out_old_instances_with_new_ones

if len(sys.argv) < 7:
    print('The service_name should include version: eg liveaddress-listprocessing-1.2.3_04')
    exit('Usage: {0} region ami_id auto_scaling_group_name service_name user_data security_groups'.format(sys.argv[0]))

REGION = sys.argv[1]
AMI_ID = sys.argv[2]
ASG_NAME = sys.argv[3]
SERVICE_NAME = sys.argv[4]
USER_DATA = sys.argv[5]
SECURITY_GROUPS = []
for group in sys.argv[6].split(','):
    SECURITY_GROUPS.append(group.strip())

INSTANCE_ID = launch_new_instance.main(REGION, AMI_ID, USER_DATA, SECURITY_GROUPS)

IMAGE_ID = create_new_ami_from_instance.main(REGION, INSTANCE_ID, SERVICE_NAME)

images = copy_image_to_all_regions.main(REGION, IMAGE_ID, SERVICE_NAME)
images[REGION] = IMAGE_ID
print('images: {0}'.format(images))

regions = []
for image in images:
    # requires: REGION, NEW_AMI_ID, OLD_LAUNCH_CONFIGURATION_NAME, NEW_LAUNCH_CONFIGURATION_NAME
    if create_new_launch_config.main(image, images[image], ASG_NAME, SERVICE_NAME, SECURITY_GROUPS):
        regions.append(image) 

for region in regions:
    phase_out_old_instances_with_new_ones.main(region, ASG_NAME, SERVICE_NAME)
