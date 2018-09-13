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


#
# Import Configurations
#======================
requests.packages.urllib3.disable_warnings()


#
# Globals
#========
global args
global date
global utils
global connection


#
# Functions
#==========

#
#
#
def get_vm_id(vmname):
    """
    Return a VM UUID based on the VM name. If multiple VMs are found, the first
    match will be returned
    """
    vm_service = connection.service("vms")
    vms = vm_service.list()

    for vm in vms:
        if vm.name == vmname:
            return vm.id

#
#
#
def get_vm_tags(vmid):
    tag_service = connection.service("vms/" + vmid + "/tags")
    tags = tag_service.list()
    tags_list = []

    for tag in tags:
        tags_list.append(tag.name)

    return tags_list

#
#
#
def get_snap_id(vmid):
    """
    Using the VM identifier, return a list of snapshots
    """
    headers = {'Content-Type': 'application/xml', 'Accept': 'application/xml'}
    vmsnap_service = connection.service("vms/" + vmid + "/snapshots")
    snaps = vmsnap_service.list()

    for snap in snaps:
        if snap.description == snapname:
            return snap.id

#
#
#
def get_snap_status(vmid, snapid):
    """
    Using the VM ID and the Snapshot ID, check the VM Snapshot status using
    the snapshot service.
    """
    vmsnap_service = connection.service("vms/" + vmid + "/snapshots")
    snaps = vmsnap_service.list()

    for snap in snaps:
        if snap.id == snapid:
            return snap.snapshot_status

#
#
#
def create_snap(vmid, snapname):
    """
    Create a snapshot for the specified VM
    """
    vm_service = connection.service("vms")
    snapshots_service = vm_service.vm_service(vmid).snapshots_service()
    snapshots_service.add(types.Snapshot(description=snapname, persist_memorystate=False))
    snapid = get_snap_id(vmid)
    status = get_snap_status(vmid, snapid)

    printf.INFO(args.debug, "Trying to create snapshot of VM: " + vmid)

    while str(status) == "locked":
       time.sleep(10)
       status = get_snap_status(vmid, snapid)
       printf.INFO(args.debug, "Snapshot status (" + str(status) + ")")

    printf.OK(args.debug, "Snapshot " + snapid + " created")

#
#
#
def delete_snap(vmid, snapid):
    """
    Using the VM ID and the Snapshot ID, delete the specified VM Snapshot
    and be sure to check on its status (do not try to )
    """
    snap_service = connection.service("vms/" + vmid + "/snapshots/" + snapid)
    snap_service.remove()
    status = get_snap_status(vmid,snapid)

    while str(status) == "locked":
        time.sleep(10)
        printf.INFO(args.debug, "Waiting until snapshot deletion ends")
        status = get_snap_status(vmid,snapid)

    printf.OK(args.debug, "Snapshot " + snapid + " deleted.")

#
#
def snap_disk_id(vmid, snapid):
    """
    Get the disk IDs so we can attach the disks to the backup system for
    data retrieval.
    """
    printf.INFO(args.debug, "Retrieving disk snapshots")
    svc_path = "vms/" + vmid + "/snapshots/" + snapid + "/disks/"
    disksnap_service = connection.service(svc_path)
    disks = disksnap_service.list()
    vm_disks = ()

    for disk in disks:
        vm_disks = vm_disks + (disk.id,)

    return vm_disks

#
#
#
def attach_disk(bkpid, diskid, snapid):
    """
    Attach disks to the backup Virtual Machine
    """
    printf.INFO(args.debug, "Attaching Disk " + diskid + " from snapshot " + snapid + " to " + bkpid)
    xmlattach = "<disk id=\"" + diskid + "\"><snapshot id=\"" + snapid + "\"/> <active>true</active></disk>"
    urlattach = args.api_url + "/v3/vms/" + bkpid + "/disks/"
    headers = {'Content-Type': 'application/xml', 'Accept': 'application/xml'}
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    resp_attach = requests.post(urlattach, data=xmlattach, headers=headers, verify=False, auth=(args.username, args.password))

#
#
#
def deactivate_disk(bkpid, diskid):
    """
    Deactivate virtual disk
    """
    printf.INFO(args.debug, "Deactivating Disk " + diskid)
    xmldeactivate = "<action/>"
    urldeactivate = args.api_url + "/v3/vms/" + bkpid + "/disks/" + diskid + "/deactivate"
    headers = {'Content-Type': 'application/xml', 'Accept': 'application/xml'}
    resp_attach = requests.post(urldeactivate, data=xmldeactivate, headers=headers, verify=False, auth=(args.username, args.password))

#
#
#
def detach_disk(bkpid, diskid):
    """
    Detach the disk from the backup Virtual Machine
    """
    printf.INFO(args.debug, "Detaching Disk")
    urldelete = args.api_url + "/vms/" + bkpid + "/diskattachments/" + diskid
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    requests.delete(urldelete, verify=False, auth=(args.username, args.password))

#
#
#
def get_logical_disk(bkpid, diskid):
    """
    Return the logical disk
    """
    dev="None"
    serial=diskid[0:20]
    printf.DEBUG(args.debug, "Disk Serial: " + serial)
    cmd="grep -Rlw '" + serial + "' /sys/block/*/serial|awk -F '/' '{print $4}'"

    while str(dev) == "None":
        try:
            path = subprocess.check_output(cmd, shell=True).replace("\n","")
            if path.startswith("vd") or path.startswith("sd") :
                dev = "/dev/" + path
                time.sleep(1)
        except Exception as ex:
            continue

    return dev

#
#
#
def run_qemu_convert(cmd):
    """
    Convert the image to a qcow2 image file
    """
    out = subprocess.call(cmd, shell=True)
    if int(out) == 0:
        print
        printf.OK(args.debug, "qcow2 file creation success")
    else:
        print
        printf.ERROR(args.debug, "qcow2 file creation failed")

#
#
#
def create_image_bkp(dev, diskname):
    """
    Create a backup image
    """
    bckfiledir = args.backup_dir + "/" + args.hostname + "/" + date
    mkdir = "mkdir -p " + bckfiledir
    subprocess.call(mkdir, shell=True)
    bckfile = bckfiledir + "/" + diskname + ".qcow2"
    printf.INFO(args.debug, "Creating qcow2 file: " + bckfile)
    cmd = "qemu-img convert -O qcow2 " + dev + " " + bckfile
    thread.start_new_thread(run_qemu_convert,(cmd,))
    #utils.progress_bar_qcow(bckfile)

#
#
#
def get_disk_name(vmid, snapid, diskid):
    """
    Get the alias of the disk
    """
    svc_path = "vms/" + vmid + "/snapshots/" + snapid + "/disks/"
    disksnap_service = connection.service(svc_path)
    disks = disksnap_service.list()

    for disk in disks:
        if diskid == str(disk.id):
            return disk.alias

#
#
#
def backup(vmid, snapid, disk_id, bkpid):
    """
    Perform the actual backup of the virtual machine, including:
        - Attaching the snapshot disk to the Backup VM
        - Creating an image backup of the disk
        - Deactivating the snapshot disk
        - Removing the snapshot disk from the Backup VM
    """
    printf.INFO(args.debug, "Attach snapshot disk to Backup VM {" + snapid + " | " + disk_id + "}")
    attach_disk(bkpid, disk_id, snapid)

    printf.INFO(args.debug, "Identifying disk device (this might take a while)")
    dev = get_logical_disk(bkpid, disk_id)
    diskname = get_disk_name(vmid, snapid, disk_id)
    printf.DEBUG(args.debug, "Dev: " + dev)

    printf.INFO(args.debug, "Creating an image backup of the disk")
    create_image_bkp(dev, diskname)

    printf.INFO(args.debug, "Deactivating the disk")
    deactivate_disk(bkpid, disk_id)
    time.sleep(10)

    printf.INFO(args.debug, "Detaching snapshot disk from " + args.backup_vm)
    detach_disk(bkpid, disk_id)
    time.sleep(10)

#
# Main
#=====
if __name__ == "__main__":

    ###
    ### Initial Variable creation and setup
    ###
    utils = Utils()

    vmid = None
    bkpid = None
    snapname = None
    snapid = None
    vm_disks = None
 
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
    vmid = get_vm_id(args.hostname)
    if vmid is None:
        printf.ERROR(args.debug, "Error retrieving " + args.hostname)
        sys.exit(1)
    else:
        printf.DEBUG(args.debug, "VM ID: " + vmid)

    ###
    ### Retrieve Backup system
    ###
    printf.INFO(args.debug, "Backup System --> " + args.backup_vm)
    bkpid = get_vm_id(args.backup_vm)
    if bkpid is None:
        printf.ERROR(args.debug, "Error retrieving " + args.backup_vm)
        sys.exit(2)
    else:
        printf.DEBUG(args.debug, "Backup VM ID: " + bkpid)

    ###
    ### Create the snapshot
    ###
    snapname = "BACKUP_" + args.hostname + "_" + date
    printf.INFO(args.debug, "Snapshot Name --> " + snapname)
    create_snap(vmid, snapname)
    snapid = get_snap_id(vmid)
    printf.DEBUG(args.debug, "Snapshot ID: " + snapid)

    ###
    ### Backup the Virtual Machine
    ###
    printf.INFO(args.debug, "Backing up the virtual machine")
    vm_disks = snap_disk_id(vmid, snapid)
    if vm_disks is None:
        printf.ERROR(args.debug, "Error retrieving disks for " + args.hostname)
        sys.exit(1)

    for disk_id in vm_disks:
        printf.INFO(args.debug, "Trying to create a qcow2 file of disk " + disk_id)
        backup(vmid, snapid, disk_id, bkpid)

    ###
    ### Delete the Snapshot
    ###
    printf.INFO(args.debug, "Trying to delete snapshot " + snapid + " of " + args.hostname)
    delete_snap(vmid, snapid)
