Update an AutoScaling Group with a new AMI
==========================================

These scripts are used to take a currently running (or stopped) EC2 instance and do the following:
- create an AMI from it
- copy that AMI to all other regions
- create a new launch config in each region that has an AutoScaling Group
- assign the new launch config to the specified Group
- scale up the group using the new launch config and then scaling down to eliminate instances that are using the old launch config
