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
from sfa.server.registry import Registries
from sfa.util.debug import log
from sfa.plc.slices import Slices
import sfa.plc.peers as peers
from sfa.managers.vini.vini_network import *
from sfa.plc.api import SfaAPI
from sfa.plc.slices import *
from sfa.managers.aggregate_manager_pl import __get_registry_objects, __get_hostnames

# VINI aggregate is almost identical to PLC aggregate for many operations, 
# so lets just import the methods form the PLC manager

from sfa.managers.aggregate_manager_pl import (
start_slice, stop_slice, renew_slice, reset_slice, get_slices, get_ticket)


def get_version():
    version = {}
    version['geni_api'] = 1
    version['sfa'] = 1
    return version

def slice_status(api, slice_xrn, creds):
    result = {}
    result['geni_urn'] = slice_xrn
    result['geni_status'] = 'unknown'
    result['geni_resources'] = {}
    return result


def delete_slice(api, xrn, creds):
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

def create_slice(api, xrn, creds, xml, users):
    """
    Verify HRN and initialize the slice record in PLC if necessary.
    """

    hrn, type = urn_to_hrn(xrn)
    peer = None
    reg_objects = __get_registry_objects(slice_xrn, creds, users)
    slices = Slices(api)
    peer = slices.get_peer(hrn)
    sfa_peer = slices.get_sfa_peer(hrn)
    registries = Registries(api)
    registry = registries[api.hrn]
    credential = api.getCredential()
    site_id, remote_site_id = slices.verify_site(registry, credential, hrn, 
                                                 peer, sfa_peer, reg_objects)
    slice = slices.verify_slice(registry, credential, hrn, site_id, 
                                remote_site_id, peer, sfa_peer, reg_objects)

    network = ViniNetwork(api)

    slice = network.get_slice(api, hrn)
    current = __get_hostnames(slice.get_nodes())

    network.addRSpec(xml, "/var/www/html/schemas/vini.rng")
    #network.addRSpec(xml, "/root/SVN/sfa/trunk/sfa/managers/vini/vini.rng")
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

def get_rspec(api, xrn=None, origin_hrn=None):
    hrn, type = urn_to_hrn(xrn)
    network = ViniNetwork(api)
    if (hrn):
        if network.get_slice(api, hrn):
            network.addSlice()

    return network.toxml()

def main():
    api = SfaAPI()
    """
    #rspec = get_rspec(api, None, None)
    rspec = get_rspec(api, "plc.princeton.iias", None)
    print rspec
    """
    f = open(sys.argv[1])
    xml = f.read()
    f.close()
    create_slice(api, "plc.princeton.iias", xml)

if __name__ == "__main__":
    main()
