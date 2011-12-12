import time
import sys

from sfa.util.sfalogging import logger
from sfa.util.faults import RecordNotFound, SliverDoesNotExist
from sfa.util.xrn import Xrn, get_authority, hrn_to_urn, urn_to_hrn, urn_to_sliver_id
from sfa.util.plxrn import slicename_to_hrn, hrn_to_pl_slicename
from sfa.util.version import version_core
from sfa.util.sfatime import utcparse
from sfa.util.callids import Callids

from sfa.trust.sfaticket import SfaTicket
from sfa.trust.credential import Credential

from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec

from sfa.server.sfaapi import SfaApi

import sfa.plc.peers as peers
from sfa.plc.plaggregate import PlAggregate
from sfa.plc.plslices import PlSlices

class AggregateManager:

    def __init__ (self):
        # xxx Thierry : caching at the aggregate level sounds wrong...
        self.caching=True
        #self.caching=False
    
    # essentially a union of the core version, the generic version (this code) and
    # whatever the driver needs to expose
    def GetVersion(self, api):
    
        xrn=Xrn(api.hrn)
        version = version_core()
        version_generic = {'interface':'aggregate',
                           'sfa': 2,
                           'geni_api': api.config.SFA_AGGREGATE_API_VERSION,
                           'hrn':xrn.get_hrn(),
                           'urn':xrn.get_urn(),
                           }
        version.update(version_generic)
        testbed_version = self.driver.aggregate_version()
        version.update(testbed_version)
        return version
    
    def SliverStatus (self, api, slice_xrn, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return {}
    
        xrn = Xrn(slice_xrn)
        slice_urn=xrn.get_urn()
        slice_hrn=xrn.get_hrn()

        return self.driver.sliver_status (slice_urn, slice_hrn)
    
    def CreateSliver(self, api, slice_xrn, creds, rspec_string, users, options):
        """
        Create the sliver[s] (slice) at this aggregate.    
        Verify HRN and initialize the slice record in PLC if necessary.
        """
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""
    
        xrn = Xrn(slice_xrn)
        slice_urn=xrn.get_urn()
        slice_hrn=xrn.get_hrn()

        return self.driver.create_sliver (slice_urn, slice_hrn, creds, rspec_string, users, options)
    
    def RenewSliver(self, api, xrn, creds, expiration_time, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return True
        
        xrn = Xrn(slice_xrn)
        slice_urn=xrn.get_urn()
        slice_hrn=xrn.get_hrn()

        return self.driver.renew_sliver (slice_urn, slice_hrn, creds, expiration_time, options)
    
    def start_slice(self, api, xrn, creds):
        (hrn, _) = urn_to_hrn(xrn)
        slicename = hrn_to_pl_slicename(hrn)
        slices = api.driver.GetSlices({'name': slicename}, ['slice_id'])
        if not slices:
            raise RecordNotFound(hrn)
        slice_id = slices[0]['slice_id']
        slice_tags = api.driver.GetSliceTags({'slice_id': slice_id, 'tagname': 'enabled'}, ['slice_tag_id'])
        # just remove the tag if it exists
        if slice_tags:
            api.driver.DeleteSliceTag(slice_tags[0]['slice_tag_id'])
    
        return 1
     
    def stop_slice(self, api, xrn, creds):
        hrn, _ = urn_to_hrn(xrn)
        slicename = hrn_to_pl_slicename(hrn)
        slices = api.driver.GetSlices({'name': slicename}, ['slice_id'])
        if not slices:
            raise RecordNotFound(hrn)
        slice_id = slices[0]['slice_id']
        slice_tags = api.driver.GetSliceTags({'slice_id': slice_id, 'tagname': 'enabled'})
        if not slice_tags:
            api.driver.AddSliceTag(slice_id, 'enabled', '0')
        elif slice_tags[0]['value'] != "0":
            tag_id = slice_tags[0]['slice_tag_id']
            api.driver.UpdateSliceTag(tag_id, '0')
        return 1
    
    def reset_slice(self, api, xrn):
        # XX not implemented at this interface
        return 1
    
    def DeleteSliver(self, api, xrn, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""
        (hrn, _) = urn_to_hrn(xrn)
        slicename = hrn_to_pl_slicename(hrn)
        slices = api.driver.GetSlices({'name': slicename})
        if not slices:
            return 1
        slice = slices[0]
    
        # determine if this is a peer slice
        peer = peers.get_peer(api, hrn)
        try:
            if peer:
                api.driver.UnBindObjectFromPeer('slice', slice['slice_id'], peer)
            api.driver.DeleteSliceFromNodes(slicename, slice['node_ids'])
        finally:
            if peer:
                api.driver.BindObjectToPeer('slice', slice['slice_id'], peer, slice['peer_slice_id'])
        return 1
    
    def ListSlices(self, api, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return []
        # look in cache first
        if self.caching and api.cache:
            slices = api.cache.get('slices')
            if slices:
                return slices
    
        # get data from db 
        slices = api.driver.GetSlices({'peer_id': None}, ['name'])
        slice_hrns = [slicename_to_hrn(api.hrn, slice['name']) for slice in slices]
        slice_urns = [hrn_to_urn(slice_hrn, 'slice') for slice_hrn in slice_hrns]
    
        # cache the result
        if self.caching and api.cache:
            api.cache.add('slices', slice_urns) 
    
        return slice_urns
        
    def ListResources(self, api, creds, options):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""
        # get slice's hrn from options
        xrn = options.get('geni_slice_urn', None)
        cached = options.get('cached', True) 
        (hrn, _) = urn_to_hrn(xrn)
    
        version_manager = VersionManager()
        # get the rspec's return format from options
        rspec_version = version_manager.get_version(options.get('geni_rspec_version'))
        version_string = "rspec_%s" % (rspec_version)
    
        #panos adding the info option to the caching key (can be improved)
        if options.get('info'):
            version_string = version_string + "_"+options.get('info', 'default')
    
        # look in cache first
        if self.caching and api.cache and not xrn and cached:
            rspec = api.cache.get(version_string)
            if rspec:
                api.logger.info("aggregate.ListResources: returning cached value for hrn %s"%hrn)
                return rspec 
    
        #panos: passing user-defined options
        #print "manager options = ",options
        aggregate = PlAggregate(self.driver)
        rspec =  aggregate.get_rspec(slice_xrn=xrn, version=rspec_version, options=options)
    
        # cache the result
        if self.caching and api.cache and not xrn:
            api.cache.add(version_string, rspec)
    
        return rspec
    
    
    def GetTicket(self, api, xrn, creds, rspec, users, options):
    
        (slice_hrn, _) = urn_to_hrn(xrn)
        slices = PlSlices(self.driver)
        peer = slices.get_peer(slice_hrn)
        sfa_peer = slices.get_sfa_peer(slice_hrn)
    
        # get the slice record
        credential = api.getCredential()
        interface = api.registries[api.hrn]
        registry = api.server_proxy(interface, credential)
        records = registry.Resolve(xrn, credential)
    
        # make sure we get a local slice record
        record = None
        for tmp_record in records:
            if tmp_record['type'] == 'slice' and \
               not tmp_record['peer_authority']:
    #Error (E0602, GetTicket): Undefined variable 'SliceRecord'
                record = SliceRecord(dict=tmp_record)
        if not record:
            raise RecordNotFound(slice_hrn)
        
        # similar to CreateSliver, we must verify that the required records exist
        # at this aggregate before we can issue a ticket
        # parse rspec
        rspec = RSpec(rspec_string)
        requested_attributes = rspec.version.get_slice_attributes()
    
        # ensure site record exists
        site = slices.verify_site(hrn, slice_record, peer, sfa_peer)
        # ensure slice record exists
        slice = slices.verify_slice(hrn, slice_record, peer, sfa_peer)
        # ensure person records exists
        persons = slices.verify_persons(hrn, slice, users, peer, sfa_peer)
        # ensure slice attributes exists
        slices.verify_slice_attributes(slice, requested_attributes)
        
        # get sliver info
        slivers = slices.get_slivers(slice_hrn)
    
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
