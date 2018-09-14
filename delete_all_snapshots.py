#!/usr/bin/env python

#
# System Imports
#===============
import argparse, requests, subprocess, sys, thread, datetime, time
import ovirtsdk4 as sdk
import ovirtsdk4.types as types
import xml.etree.ElementTree as ET
from requests.packages.urllib3.exceptions import InsecureRequestWarning

import lib.printf as printf
from lib.utils import Utils
import lib.vm as virt

#
# Globals
#========
global args
global date
global utils
global connection


###
### Initial Variable creation and setup
###
utils = Utils()

vmid = None

now = datetime.datetime.now()
date = now.strftime("%Y%m%d-%H%M")

###
### Argument Parsing
###
parser = argparse.ArgumentParser(description="Process command line arguments")

config = utils.configure_vars()
parser.set_defaults(**config)

parser.add_argument('--debug', '-d', action="count", help="Debugging information")
parser.add_argument('--config', '-c', action="store", help="System Backup Configuration File")
parser.add_argument('--hostname', '-H', action="store", help="Virtual Machine Hostname to backup")
parser.add_argument('--api_url', '-U',  action="store", help="RHV URL (including api path)")
parser.add_argument('--username', '-u', action="store", help="RHV Username")
parser.add_argument('--password', '-p', action="store", help="RHV Password")
parser.add_argument('--ca_file', '-C', action="store", help="CA File Location")
parser.add_argument('--backup_vm', '-B', action="store", help="Backup VM Name")
parser.add_argument('--backup_dir', '-b', action="store", help="Backup Directory")

args = parser.parse_args()

###
### Connection
###
try:
    connection = sdk.Connection(
        url=args.api_url,
        username=args.username,
        password=args.password,
        ca_file=args.ca_file,
        insecure=args.insecure,
        log=args.log,
    )
except Exception as ex:
    printf.ERROR(args.debug, "Connection to oVirt API has failed")
    printf.ERROR(args.debug, ex)
    sys.exit(0)
    
###
### Retrieve VM
###
printf.INFO(args.debug, "Retrieving VM --> " + args.hostname)
vmid = virt.get_vm_id(args.hostname)
if vmid is None:
    printf.ERROR(args.debug, "Error retrieving " + args.hostname)
    sys.exit(1)
else:
    printf.DEBUG(args.debug, "VM ID: " + vmid)

snaps = virt.get_snaps(vmid)

for snapid in snaps:
    virt.delete_snap(vmid, snapid)
