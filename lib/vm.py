#!/usr/bin/env python

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

    while str(status) == "locked":
       time.sleep(10)
       status = get_snap_status(vmid, snapid)


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
        status = get_snap_status(vmid,snapid)
