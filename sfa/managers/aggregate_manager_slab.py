import datetime
import time
import sys

from sfa.util.sfalogging import logger
from sfa.util.faults import RecordNotFound, SliverDoesNotExist
from sfa.util.xrn import get_authority, hrn_to_urn, urn_to_hrn, Xrn, urn_to_sliver_id
from sfa.util.plxrn import slicename_to_hrn, hrn_to_pl_slicename
from sfa.util.version import version_core
from sfa.util.sfatime import utcparse
from sfa.util.callids import Callids

from sfa.trust.sfaticket import SfaTicket
from sfa.trust.credential import Credential
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec

from sfa.server.sfaapi import SfaApi
from sfa.senslab.slabaggregate import SlabAggregate
import sfa.plc.peers as peers

from sfa.senslab.slabslices import SlabSlices

class AggregateManager:
    def __init__ (self, config): pass
    # essentially a union of the core version, the generic version (this code) and
    # whatever the driver needs to expose
    
    
    def GetVersion(self, api, options):

        xrn=Xrn(api.hrn)
        version = version_core()
        version_generic = {'interface':'aggregate',
                            'sfa': 2,
                            'geni_api': 2,
                            'hrn':xrn.get_hrn(),
                            'urn':xrn.get_urn(),
                            }
        version.update(version_generic)
        testbed_version = self.driver.aggregate_version()
        version.update(testbed_version)
        return version
     
    #def GetVersion(self, api, options={}):
    
        #version_manager = VersionManager()
        #ad_rspec_versions = []
        #request_rspec_versions = []
        #for rspec_version in version_manager.versions:
            #if rspec_version.content_type in ['*', 'ad']:
                #ad_rspec_versions.append(rspec_version.to_dict())
            #if rspec_version.content_type in ['*', 'request']:
                #request_rspec_versions.append(rspec_version.to_dict()) 
        #xrn=Xrn(api.hrn)
        #version_more = {'interface':'aggregate',
                        #'sfa': 2,
                        #'geni_api': api.config.SFA_AGGREGATE_API_VERSION,
                        #'testbed':'myplc',
                        #'hrn':xrn.get_hrn(),
                        #'geni_request_rspec_versions': request_rspec_versions,
                        #'geni_ad_rspec_versions': ad_rspec_versions,
                        #}
        #return version_core(version_more)
    
    def _get_registry_objects(self, slice_xrn, creds, users):
        """
    
        """
        hrn, _ = urn_to_hrn(slice_xrn)
    
        hrn_auth = get_authority(hrn)
    
        # Build up objects that an SFA registry would return if SFA
        # could contact the slice's registry directly
        reg_objects = None
    
        if users:
            # dont allow special characters in the site login base
            #only_alphanumeric = re.compile('[^a-zA-Z0-9]+')
            #login_base = only_alphanumeric.sub('', hrn_auth[:20]).lower()
            slicename = hrn_to_pl_slicename(hrn)
            login_base = slicename.split('_')[0]
            reg_objects = {}
            site = {}
            site['site_id'] = 0
            site['name'] = 'geni.%s' % login_base 
            site['enabled'] = True
            site['max_slices'] = 100
    
            # Note:
            # Is it okay if this login base is the same as one already at this myplc site?
            # Do we need uniqueness?  Should use hrn_auth instead of just the leaf perhaps?
            site['login_base'] = login_base
            site['abbreviated_name'] = login_base
            site['max_slivers'] = 1000
            reg_objects['site'] = site
    
            slice = {}
            
            # get_expiration always returns a normalized datetime - no need to utcparse
            extime = Credential(string=creds[0]).get_expiration()
            # If the expiration time is > 60 days from now, set the expiration time to 60 days from now
            if extime > datetime.datetime.utcnow() + datetime.timedelta(days=60):
                extime = datetime.datetime.utcnow() + datetime.timedelta(days=60)
            slice['expires'] = int(time.mktime(extime.timetuple()))
            slice['hrn'] = hrn
            slice['name'] = hrn_to_pl_slicename(hrn)
            slice['url'] = hrn
            slice['description'] = hrn
            slice['pointer'] = 0
            reg_objects['slice_record'] = slice
    
            reg_objects['users'] = {}
            for user in users:
                user['key_ids'] = []
                hrn, _ = urn_to_hrn(user['urn'])
                user['email'] = hrn_to_pl_slicename(hrn) + "@geni.net"
                user['first_name'] = hrn
                user['last_name'] = hrn
                reg_objects['users'][user['email']] = user
    
            return reg_objects
    
    def SliverStatus(self, api, slice_xrn, creds, options={}):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return {}
    
        (hrn, _) = urn_to_hrn(slice_xrn)
        # find out where this slice is currently running
        slicename = hrn_to_pl_slicename(hrn)
        
        slices = api.driver.GetSlices([slicename], ['slice_id', 'node_ids','person_ids','name','expires'])
        if len(slices) == 0:        
            raise Exception("Slice %s not found (used %s as slicename internally)" % (slice_xrn, slicename))
        slice = slices[0]
        
        # report about the local nodes only
        nodes = api.driver.GetNodes({'node_id':slice['node_ids'],'peer_id':None},
                                     ['node_id', 'hostname', 'site_id', 'boot_state', 'last_contact'])
        site_ids = [node['site_id'] for node in nodes]
    
        result = {}
        top_level_status = 'unknown'
        if nodes:
            top_level_status = 'ready'
        slice_urn = Xrn(slice_xrn, 'slice').get_urn()
        result['geni_urn'] = slice_urn
        result['pl_login'] = slice['name']
        result['pl_expires'] = datetime.datetime.fromtimestamp(slice['expires']).ctime()
        
        resources = []
        for node in nodes:
            res = {}
            res['pl_hostname'] = node['hostname']
            res['pl_boot_state'] = node['boot_state']
            res['pl_last_contact'] = node['last_contact']
            if node['last_contact'] is not None:
                res['pl_last_contact'] = datetime.datetime.fromtimestamp(node['last_contact']).ctime()
            sliver_id = urn_to_sliver_id(slice_urn, slice['slice_id'], node['node_id']) 
            res['geni_urn'] = sliver_id
            if node['boot_state'] == 'boot':
                res['geni_status'] = 'ready'
            else:
                res['geni_status'] = 'failed'
                top_level_status = 'failed' 
                
            res['geni_error'] = ''
    
            resources.append(res)
            
        result['geni_status'] = top_level_status
        result['geni_resources'] = resources
        return result
    
    def CreateSliver(self, api, slice_xrn, creds, rspec_string, users, options={}):
        """
        Create the sliver[s] (slice) at this aggregate.    
        Verify HRN and initialize the slice record in PLC if necessary.
        """
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return ""
        aggregate = SlabAggregate(api)
        #aggregate = Aggregate(api)
        slices = SlabSlices(api)
        (hrn, _) = urn_to_hrn(slice_xrn)
        peer = slices.get_peer(hrn)
        sfa_peer = slices.get_sfa_peer(hrn)
        slice_record=None    
        if users:
            slice_record = users[0].get('slice_record', {})
            print >>sys.stderr, " \r\n \t AGGREGATESLAB.PY Slice slice_record : ", slice_record
    
        # parse rspec
        rspec = RSpec(rspec_string)
        requested_attributes = rspec.version.get_slice_attributes()
        
        # ensure site record exists
        site = slices.verify_site(hrn, slice_record, peer, sfa_peer)
        # ensure slice record exists
        print>>sys.stderr, " \r\n \t AGGREGATESLAB.PY Slice users : ", users
        slice = slices.verify_slice(hrn, slice_record, peer, sfa_peer)
        print >>sys.stderr, " \r\n \t AGGREGATESLAB.PY Slice slice : ", slice
        # ensure person records exists
        persons = slices.verify_persons(hrn, slice, users)
        #persons = slices.verify_persons(hrn, slice, users, peer, sfa_peer)
        # ensure slice attributes exists
        #slices.verify_slice_attributes(slice, requested_attributes)
        
        # add/remove slice from nodes
        requested_slivers = [node.get('component_name') for node in rspec.version.get_nodes_with_slivers()]
        print >>sys.stderr, " \r\n \t AGGREGATESLAB.PY Slice requested_slivers : ", requested_slivers
        slices.verify_slice_nodes(slice, requested_slivers, peer) 
   
        # add/remove links links 
        #slices.verify_slice_links(slice, rspec.version.get_link_requests(), aggregate)
    
        # handle MyPLC peer association.
        # only used by plc and ple.
        slices.handle_peer(site, slice, persons, peer)
        
        return aggregate.get_rspec(slice_xrn=slice_xrn, version=rspec.version)
    
    
    def RenewSliver(self, api, xrn, creds, expiration_time, options={}):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return True
        (hrn, _) = urn_to_hrn(xrn)
        slicename = hrn_to_pl_slicename(hrn)
        slices = api.driver.GetSlices({'name': slicename}, ['slice_id'])
        if not slices:
            raise RecordNotFound(hrn)
        slice = slices[0]
        requested_time = utcparse(expiration_time)
        record = {'expires': int(time.mktime(requested_time.timetuple()))}
        try:
            api.driver.UpdateSlice(slice['slice_id'], record)
            return True
        except:
            return False
    
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
    
    def DeleteSliver(self, api, xrn, creds, options={}):
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
    
    def ListSlices(self, api, creds, options={}):
        call_id = options.get('call_id')
        if Callids().already_handled(call_id): return []
        # look in cache first
        #if self.caching and api.cache:
            #slices = api.cache.get('slices')
            #if slices:
                #return slices
    
        # get data from db 
        slices = api.driver.GetSlices({'peer_id': None}, ['name'])
        slice_hrns = [slicename_to_hrn(api.hrn, slice['name']) for slice in slices]
        slice_urns = [hrn_to_urn(slice_hrn, 'slice') for slice_hrn in slice_hrns]
    
        # cache the result
        #if self.caching and api.cache:
            #api.cache.add('slices', slice_urns) 
    
        return slice_urns
        
    def ListResources(self, api, creds, options={}):
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
        #if self.cache and api.cache and not xrn and cached:
            #rspec = api.cache.get(version_string)
            #if rspec:
                #api.logger.info("aggregate.ListResources: returning cached value for hrn %s"%hrn)
                #return rspec 
    
        #panos: passing user-defined options
        #print "manager options = ",options
        aggregate = SlabAggregate(api)
        #aggregate = Aggregate(api)
        rspec =  aggregate.get_rspec(slice_xrn=xrn, version=rspec_version, options=options)
    
        # cache the result
        #if self.caching and api.cache and not xrn:
            #api.cache.add(version_string, rspec)
    
        return rspec
    
    
    def GetTicket(self, api, xrn, creds, rspec, users, options={}):
    
        (slice_hrn, _) = urn_to_hrn(xrn)
        slices = SlabSlices(api)
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
