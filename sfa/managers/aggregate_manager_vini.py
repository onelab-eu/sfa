import datetime
import time
import traceback
import sys

from types import StringTypes
from sfa.util.xrn import urn_to_hrn, Xrn
from sfa.util.plxrn import hrn_to_pl_slicename
from sfa.util.specdict import *
from sfa.util.faults import *
from sfa.util.record import SfaRecord
from sfa.util.policy import Policy
from sfa.util.record import *
from sfa.trust.sfaticket import SfaTicket
from sfa.server.registry import Registries
from sfa.plc.slices import Slices
import sfa.plc.peers as peers
from sfa.managers.vini.vini_network import *
from sfa.plc.vini_aggregate import ViniAggregate
from sfa.rspecs.version_manager import VersionManager
from sfa.plc.api import SfaAPI
from sfa.plc.slices import *
from sfa.managers.aggregate_manager_pl import __get_registry_objects, __get_hostnames
from sfa.util.version import version_core
from sfa.util.callids import Callids

# VINI aggregate is almost identical to PLC aggregate for many operations, 
# so lets just import the methods form the PLC manager
from sfa.managers.aggregate_manager_pl import (
start_slice, stop_slice, RenewSliver, reset_slice, ListSlices, get_ticket, SliverStatus)


def GetVersion(api):
    xrn=Xrn(api.hrn)
    return version_core({'interface':'aggregate',
                         'testbed':'myplc.vini',
                         'hrn':xrn.get_hrn(),
                         })

def DeleteSliver(api, xrn, creds, call_id):
    if Callids().already_handled(call_id): return ""
    (hrn, type) = urn_to_hrn(xrn)
    slicename = hrn_to_pl_slicename(hrn)
    slices = api.plshell.GetSlices(api.plauth, {'name': slicename})
    if not slices:
        return 1
    slice = slices[0]

    api.plshell.DeleteSliceFromNodes(api.plauth, slicename, slice['node_ids'])
    return 1

def CreateSliver(api, xrn, creds, xml, users, call_id):
    """
    Verify HRN and initialize the slice record in PLC if necessary.
    """

    if Callids().already_handled(call_id): return ""

    hrn, type = urn_to_hrn(xrn)
    peer = None
    reg_objects = __get_registry_objects(xrn, creds, users)
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

    api.plshell.AddSliceToNodes(api.plauth, slice.name, added_nodes) 
    api.plshell.DeleteSliceFromNodes(api.plauth, slice.name, deleted_nodes)
    network.updateSliceTags()

    # xxx - check this holds enough data for the client to understand what's happened
    return network.toxml()

def ListResources(api, creds, options,call_id):
    if Callids().already_handled(call_id): return ""
    # get slice's hrn from options
    xrn = options.get('geni_slice_urn', '')
    hrn, type = urn_to_hrn(xrn)

    version_manager = VersionManager()
    # get the rspec's return format from options
    rspec_version = version_manager.get_version(options.get('rspec_version'))
    version_string = "rspec_%s" % (rspec_version.to_string())
    
    # look in cache first
    if api.cache and not xrn:
        rspec = api.cache.get(version_string)
        if rspec:
            api.logger.info("aggregate.ListResources: returning cached value for hrn %s"%hrn)
            return rspec

    aggregate = ViniAggregate(api, options) 
    rspec =  aggregate.get_rspec(slice_xrn=xrn, version=rspec_version)
           
    # cache the result
    if api.cache and not xrn:
        api.cache.add('nodes', rspec)

    return rspec

def main():
    api = SfaAPI()
    """
    #rspec = ListResources(api, None, None,)
    rspec = ListResources(api, "plc.princeton.iias", None, 'vini_test')
    print rspec
    """
    f = open(sys.argv[1])
    xml = f.read()
    f.close()
    CreateSliver(api, "plc.princeton.iias", xml, 'call-id-iias')

if __name__ == "__main__":
    main()
