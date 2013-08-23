aws
===

Amazon Web Services python/boto scripts

No license, no copyright, no warranty, no support. Use, re-use, distribute as you see fit.

- README.md: This file.
- autoscale-console.py: The console script.
- user-data: A vanilla file that the console script requires. Add your own server provisioning.
- iam-permissions: A list of permissions used by the console script to be able to access AWS functionality.

Install
=======

Download the script. Edit the config section. Make the script executable (chmod) or run it with the "python" command on the command line.


Notes
=====

Do I really need to say that this is still a work in progress and that if you use it you should do so at your own risk?

It works for me. :) At least the parts of it that I have finished. And by finished, I mean made to work at an acceptable level.

The permissions listed in the iam-permissions file should work for anyone. There are some ARN's that need to be changed for your own specific account. Keep in mind that these permissions may be overly permissive for your security model. Or perhaps they are not permissive enough. I am including them as an example to help you have a reference in setting up your own permissions.
