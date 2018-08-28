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
global vmid
global vmname
global bkpvm
global connection


#
# Functions
#==========
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

    printf.INFO("Trying to create snapshot of VM: " + vmid)

    while str(status) == "locked":
       time.sleep(10)
       status = get_snap_status(vmid, snapid)
       printf.INFO("Snapshot status (" + str(status) + ")")

    printf.OK("Snapshot " + snapid + " created")

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
        printf.INFO("Waiting until snapshot deletion ends")
        status = get_snap_status(vmid,snapid)

    printf.OK("Snapshot " + snapid + " deleted.")

#
#
#
def snap_disk_id(vmid, snapid):
    """
    Get the disk IDs so we can attach the disks to the backup system for
    data retrieval.
    """
    printf.INFO("Retrieving disk snapshots")
    svc_path = "vms/" + vmid + "/snapshots/" + snapid + "/disks/"
    disksnap_service = connection.service(svc_path)
    disks = disksnap_service.list()
    vm_disks = ()

    for disk in disks:
        vm_disks = vm_disks + (disk.id,)

    printf.DEBUG("VM Disks" + vm_disks)
    return vm_disks

#
#
#
def attach_disk(bkpid, diskid, snapid):
    """
    Attach disks to the backup Virtual Machine
    """
    printf.INFO("Attaching Disk " + diskid + " from snapshot " + snapid + " to " + bkpid)
    xmlattach = "<disk id=\"" + diskid + "\"><snapshot id=\"" + snapid + "\"/> <active>true</active></disk>"
    urlattach = args.api_url + "/v3/vms/" + bkpid + "/disks/"
    headers = {'Content-Type': 'application/xml', 'Accept': 'application/xml'}
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    resp_attach = requests.post(urlattach, data=xmlattach, headers=headers, verify=False, auth=(args.username, args.password))
    printf.DEBUG("Attach Request: ")
    print resp_attach

#
#
#
def deactivate_disk(bkpid, diskid):
    """
    Deactivate virtual disk
    """
    urldeactivate = args.api_url + "/v3/vms/" + bkpid + "/disks/" + diskid + "/deactivate"
    headers = {'Content-Type': 'application/xml', 'Accept': 'application/xml'}
    resp_attach = requests.post(urldeactivate, data=xmldeactivate, headers=headers, verify=False, auth=(args.username, args.password))
    printf.DEBUG("Deactivate Request: ")
    print resp_attach
#
#
#
def detach_disk(bkpid, diskid):
    """
    Detach the disk from the backup Virtual Machine
    """
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
    printf.DEBUG("Disk Serial: " + serial)
    cmd="grep -Rlw '" + serial + "' /sys/block/*/serial|awk -F '/' '{print $4}'"

    while str(dev) == "None":
        try:
            path = subprocess.check_output(cmd, shell=True).replace("\n","")
            if path.startswith("vd") or path.startswith("sd") :
                dev = "/dev/" + path
                time.sleep(1)
        except Exception as ex:
            print ex
            sys.exit(1)

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
        printf.OK("qcow2 file creation success")
    else:
        print
        printf.ERROR("qcow2 file creation failed")

#
#
#
def create_image_bkp(dev, diskname):
    """
    Create a backup image
    """
    bckfiledir = args.backup_dir + "/" + vmname + "/" + date
    mkdir = "mkdir -p " + bckfiledir
    subprocess.call(mkdir, shell=True)
    bckfile = bckfiledir + "/" + diskname + ".qcow2"
    printf.INFO("Creating qcow2 file: " + bckfile)
    cmd = "qemu-img convert -O qcow2 " + dev + " " +bckfile
    u = utilities.utils()
    thread.start_new_thread(run_qemu_convert,(cmd,))
    u.progress_bar_qcow(bckfile)

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
def backup(vmid, snapid, disk_id, bkpvm):
    """
    Perform the actual backup of the virtual machine, including:
        - Attaching the snapshot disk to the Backup VM
        - Creating an image backup of the disk
        - Deactivating the snapshot disk
        - Removing the snapshot disk from the Backup VM
    """
    printf.INFO("Attach snapshot disk to Backup VM {" + snapid + " | " + disk_id + "}")
    attach_disk(bkpvm, disk_id, snapid)
    printf.INFO("Disk attached to Backup VM")

    printf.INFO("Identifying disk device (this might take a while)")
    dev = get_logical_disk(bkpvm, disk_id)
    diskname = get_disk_name(vmid, snapid, disk_id)

    printf.INFO("Creating an image backup of the disk")
    create_image_bkp(dev, diskname)

    printf.INFO("Deactivating the disk")
    deactivate_disk(bkpvm, disk_id)
    time.sleep(10)

    printf.INFO("Detaching snapshot disk from bkpvm")
    detach_disk(bkpvm, disk_id)
    time.sleep(10)

#
# Main
#=====
if __name__ == "__main__":

    # Utils
    utils = Utils()

    # Argument Parser
    parser = argparse.ArgumentParser(description="Process command line arguments")

    config = utils.configure_vars("etc", "rhvbackup.conf")
    parser.set_defaults(**config)

    parser.add_argument('--debug', action="store", help="Debugging information")
    parser.add_argument('--config', action="store", help="System Backup Configuration File")
    parser.add_argument('--hostname', action="store", help="Virtual Machine Hostname to backup")
    parser.add_argument('--api_url', action="store", help="RHV URL (including api path)")
    parser.add_argument('--username', action="store", help="RHV Username")
    parser.add_argument('--password', action="store", help="RHV Password")
    parser.add_argument('--ca_file', action="store", help="CA File Location")
    parser.add_argument('--backup_vm', action="store", help="Backup VM Name")
    parser.add_argument('--backup_dir', action="store", help="Backup Directory")

    args = parser.parse_args()

    # Connection
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
        printf.ERROR("Connection to oVirt API has failed")
        sys.exit(0)
        
    # Retrieve VM
    printf.INFO("Retrieving VM --> " + args.hostname)
    vmid = get_vm_id(args.hostname)
    printf.DEBUG("VM ID: " + vmid)

    # Retrieve Backup system
    printf.INFO("Backup System --> " + args.backup_vm)
    bkpid = get_vm_id(args.backup_vm)
    printf.DEBUG("Backup VM ID: " + bkpid)

    # Create the snapshot
    now = datetime.datetime.now()
    date = now.strftime("%y%m%d-%H%M")
    snapname = "BACKUP_" + args.hostname + "_" + date
    printf.INFO("Snapshot Name --> " + snapname)
    create_snap(vmid, snapname)
    snapid = get_snap_id(vmid)
    printf.DEBUG("Snapshot ID: " + snapid)

    # Backup the Virtual Machine
    vm_disks = snap_disk_id(vmid, snapid)
    for disk_id in vm_disks:
        printf.INFO("Trying to create a qcow2 file of disk " + disk_id)
        backup(vmid, snapid, disk_id, bkpid)

    # Delete the Snapshot
    printf.INFO("Trying to delete snapshot " + snapid + " of " + args.hostname)
    delete_snap(vmid, snapid)

    # Finish
    printf.OK("Backup successful")

