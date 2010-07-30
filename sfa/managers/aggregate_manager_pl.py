### $Id: slices.py 15842 2009-11-22 09:56:13Z anil $
### $URL: https://svn.planet-lab.org/svn/sfa/trunk/sfa/plc/slices.py $

import datetime
import time
import traceback
import sys

from types import StringTypes
from sfa.util.namespace import *
from sfa.util.rspec import *
from sfa.util.specdict import *
from sfa.util.faults import *
from sfa.util.record import SfaRecord
from sfa.util.policy import Policy
from sfa.util.record import *
from sfa.util.sfaticket import SfaTicket
from sfa.util.debug import log
from sfa.plc.slices import Slices
import sfa.plc.peers as peers
from sfa.plc.network import *
from sfa.plc.api import SfaAPI
from sfa.plc.slices import *

def delete_slice(api, xrn):
    hrn, type = urn_to_hrn(xrn)
    slicename = hrn_to_pl_slicename(hrn)
    slices = api.plshell.GetSlices(api.plauth, {'name': slicename})
    if not slices:
        return 1
    slice = slices[0]

    # determine if this is a peer slice
    peer = peers.get_peer(api, hrn)
    if peer:
        api.plshell.UnBindObjectFromPeer(api.plauth, 'slice', slice['slice_id'], peer)
    api.plshell.DeleteSliceFromNodes(api.plauth, slicename, slice['node_ids'])
    if peer:
        api.plshell.BindObjectToPeer(api.plauth, 'slice', slice['slice_id'], peer, slice['peer_slice_id'])
    return 1

def __get_hostnames(nodes):
    hostnames = []
    for node in nodes:
        hostnames.append(node.hostname)
    return hostnames
    
def create_slice(api, xrn, xml, reg_objects=None):
    """
    Verify HRN and initialize the slice record in PLC if necessary.
    """

    hrn, type = urn_to_hrn(xrn)
    peer = None
    slices = Slices(api)
    peer = slices.get_peer(hrn)
    sfa_peer = slices.get_sfa_peer(hrn)
    registry = api.registries[api.hrn]
    credential = api.getCredential()
    site_id, remote_site_id = slices.verify_site(registry, credential, hrn, 
                                                 peer, sfa_peer, reg_objects)

    slice = slices.verify_slice(registry, credential, hrn, site_id, 
                                remote_site_id, peer, sfa_peer, reg_objects)

    network = Network(api)

    slice = network.get_slice(api, hrn)
    current = __get_hostnames(slice.get_nodes())
    
    network.addRSpec(xml, api.config.SFA_AGGREGATE_RSPEC_SCHEMA)
    request = __get_hostnames(network.nodesWithSlivers())
    
    # remove nodes not in rspec
    deleted_nodes = list(set(current).difference(request))

    # add nodes from rspec
    added_nodes = list(set(request).difference(current))
    


    if peer:
        api.plshell.UnBindObjectFromPeer(api.plauth, 'slice', slice.id, peer)

    api.plshell.AddSliceToNodes(api.plauth, slice.name, added_nodes) 
    api.plshell.DeleteSliceFromNodes(api.plauth, slice.name, deleted_nodes)

    network.updateSliceTags()

    if peer:
        api.plshell.BindObjectToPeer(api.plauth, 'slice', slice.id, peer, 
                                     slice.peer_id)

    # print network.toxml()

    return True


def get_ticket(api, xrn, rspec, origin_hrn=None, reg_objects=None):

    slice_hrn, type = urn_to_hrn(xrn)
    slices = Slices(api)
    peer = slices.get_peer(slice_hrn)
    sfa_peer = slices.get_sfa_peer(slice_hrn)
    
    # get the slice record
    registry = api.registries[api.hrn]
    credential = api.getCredential()
    records = registry.resolve(credential, xrn)

    # similar to create_slice, we must verify that the required records exist
    # at this aggregate before we can issue a ticket   
    site_id, remote_site_id = slices.verify_site(registry, credential, slice_hrn,
                                                 peer, sfa_peer, reg_objects)
    slice = slices.verify_slice(registry, credential, slice_hrn, site_id,
                                remote_site_id, peer, sfa_peer, reg_objects)

    # make sure we get a local slice record
    record = None  
    for tmp_record in records:
        if tmp_record['type'] == 'slice' and \
           not tmp_record['peer_authority']:
            record = SliceRecord(dict=tmp_record)
    if not record:
        raise RecordNotFound(slice_hrn)

    # get sliver info
    slivers = Slices(api).get_slivers(slice_hrn)
    if not slivers:
        raise SliverDoesNotExist(slice_hrn)
    
    # get initscripts
    initscripts = []
    data = {
        'timestamp': int(time.time()),
        'initscripts': initscripts,
        'slivers': slivers
    }

    # create the ticket
    object_gid = record.get_gid_object()
    new_ticket = SfaTicket(subject = object_gid.get_subject())
    new_ticket.set_gid_caller(api.auth.client_gid)
    new_ticket.set_gid_object(object_gid)
    new_ticket.set_issuer(key=api.key, subject=api.hrn)
    new_ticket.set_pubkey(object_gid.get_pubkey())
    new_ticket.set_attributes(data)
    new_ticket.set_rspec(rspec)
    #new_ticket.set_parent(api.auth.hierarchy.get_auth_ticket(auth_hrn))
    new_ticket.encode()
    new_ticket.sign()
    
    return new_ticket.save_to_string(save_parents=True)

def start_slice(api, xrn):
    hrn, type = urn_to_hrn(xrn)
    slicename = hrn_to_pl_slicename(hrn)
    slices = api.plshell.GetSlices(api.plauth, {'name': slicename}, ['slice_id'])
    if not slices:
        raise RecordNotFound(hrn)
    slice_id = slices[0]
    attributes = api.plshell.GetSliceTags(api.plauth, {'slice_id': slice_id, 'name': 'enabled'}, ['slice_attribute_id'])
    attribute_id = attributes[0]['slice_attribute_id']
    api.plshell.UpdateSliceTag(api.plauth, attribute_id, "1" )

    return 1
 
def stop_slice(api, xrn):
    hrn, type = urn_to_hrn(xrn)
    slicename = hrn_to_pl_slicename(hrn)
    slices = api.plshell.GetSlices(api.plauth, {'name': slicename}, ['slice_id'])
    if not slices:
        raise RecordNotFound(hrn)
    slice_id = slices[0]['slice_id']
    attributes = api.plshell.GetSliceTags(api.plauth, {'slice_id': slice_id, 'name': 'enabled'}, ['slice_attribute_id'])
    attribute_id = attributes[0]['slice_attribute_id']
    api.plshell.UpdateSliceTag(api.plauth, attribute_id, "0")
    return 1

def reset_slice(api, xrn):
    # XX not implemented at this interface
    return 1

def get_slices(api):
    # look in cache first
    if api.cache:
        slices = api.cache.get('slices')
        if slices:
            return slices

    # get data from db 
    slices = api.plshell.GetSlices(api.plauth, {'peer_id': None}, ['name'])
    slice_hrns = [slicename_to_hrn(api.hrn, slice['name']) for slice in slices]
    slice_urns = [hrn_to_urn(slice_hrn, 'slice') for slice_hrn in slice_hrns]

    # cache the result
    if api.cache:
        api.cache.add('slices', slice_urns) 

    return slice_urns
    
def get_rspec(api, xrn=None, origin_hrn=None):
    # look in cache first
    if api.cache and not xrn:
        rspec = api.cache.get('nodes')
        if rspec:
            return rspec 

    hrn, type = urn_to_hrn(xrn)
    network = Network(api)
    if (hrn):
        if network.get_slice(api, hrn):
            network.addSlice()

    rspec = network.toxml()

    # cache the result
    if api.cache and not xrn:
        api.cache.add('nodes', rspec)

    return rspec

"""
Returns the request context required by sfatables. At some point, this
mechanism should be changed to refer to "contexts", which is the
information that sfatables is requesting. But for now, we just return
the basic information needed in a dict.
"""
def fetch_context(slice_xrn, user_xrn, contexts):
    slice_hrn, type = urn_to_hrn(slice_xrn)
    user_hrn, type = urn_to_hrn(user_xrn)
    base_context = {'sfa':{'user':{'hrn':user_hrn}, 'slice':{'hrn':slice_hrn}}}
    return base_context

def main():
    api = SfaAPI()
    """
    rspec = get_rspec(api, "plc.princeton.sapan", None)
    #rspec = get_rspec(api, "plc.princeton.coblitz", None)
    #rspec = get_rspec(api, "plc.pl.sirius", None)
    print rspec
    """
    f = open(sys.argv[1])
    xml = f.read()
    f.close()
    create_slice(api, "plc.princeton.sapan", xml)

if __name__ == "__main__":
    main()
