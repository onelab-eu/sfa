import time
import datetime
#
from sfa.util.faults import MissingSfaInfo, UnknownSfaType, \
    RecordNotFound, SfaNotImplemented, SliverDoesNotExist
from sfa.util.sfalogging import logger
from sfa.util.defaultdict import defaultdict
from sfa.util.sfatime import utcparse, datetime_to_string, datetime_to_epoch
from sfa.util.xrn import Xrn, hrn_to_urn, get_leaf, urn_to_sliver_id
from sfa.util.cache import Cache
# one would think the driver should not need to mess with the SFA db, but..
from sfa.storage.table import SfaTable
# used to be used in get_ticket
#from sfa.trust.sfaticket import SfaTicket
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec
# the driver interface, mostly provides default behaviours
from sfa.managers.driver import Driver
from sfa.openstack.openstack_shell import OpenstackShell
import sfa.plc.peers as peers
from sfa.plc.plaggregate import PlAggregate
from sfa.plc.plslices import PlSlices
from sfa.util.plxrn import slicename_to_hrn, hostname_to_hrn, hrn_to_pl_slicename, hrn_to_pl_login_base


def list_to_dict(recs, key):
    """
    convert a list of dictionaries into a dictionary keyed on the 
    specified dictionary key 
    """
    return dict ( [ (rec[key],rec) for rec in recs ] )

#
# PlShell is just an xmlrpc serverproxy where methods
# can be sent as-is; it takes care of authentication
# from the global config
# 
class OpenstackDriver (Driver):

    # the cache instance is a class member so it survives across incoming requests
    cache = None

    def __init__ (self, config):
        Driver.__init__ (self, config)
        self.shell = OpenstackShell (config)
        self.cache=None
        if config.SFA_AGGREGATE_CACHING:
            if OpenstackDriver.cache is None:
                OpenstackDriver.cache = Cache()
            self.cache = OpenstackDriver.cache
 
    ########################################
    ########## registry oriented
    ########################################

    ########## disabled users 
    def is_enabled (self, record):
        # all records are enabled
        return True

    def augment_records_with_testbed_info (self, sfa_records):
        return self.fill_record_info (sfa_records)

    ########## 
    def register (self, sfa_record, hrn, pub_key):
        type = sfa_record['type']
        pl_record = self.sfa_fields_to_pl_fields(type, hrn, sfa_record)

        if type == 'slice':
            acceptable_fields=['url', 'instantiation', 'name', 'description']
            # add slice description, name, researchers, PI 
            pass

        elif type == 'user':
            # add person roles, projects and keys
            pass
        return pointer
        
    ##########
    # xxx actually old_sfa_record comes filled with plc stuff as well in the original code
    def update (self, old_sfa_record, new_sfa_record, hrn, new_key):
        pointer = old_sfa_record['pointer']
        type = old_sfa_record['type']

        # new_key implemented for users only
        if new_key and type not in [ 'user' ]:
            raise UnknownSfaType(type)

        elif type == "slice":
            # can update description, researchers and PI
            pass 
        elif type == "user":
            # can update  slices, keys and roles
            pass
        return True
        

    ##########
    def remove (self, sfa_record):
        type=sfa_record['type']
        name = Xrn(sfa_record['hrn']).get_leaf()     
        if type == 'user':
            if self.shell.user_get(name):
                self.shell.user_delete(name)
        elif type == 'slice':
            if self.shell.project_get(name):
                self.shell.project_delete(name)
        return True


    ####################
    def fill_record_info(self, records):
        """
        Given a (list of) SFA record, fill in the PLC specific 
        and SFA specific fields in the record. 
        """
        if not isinstance(records, list):
            records = [records]

        for record in records:
            name = Xrn(record['hrn']).get_leaf()
            os_record = None
            if record['type'] == 'user':
                os_record = self.shell.user_get(name)
                record['slices'] = [self.hrn + "." + proj.name for \
                                    proj in os_record.projects]
                record['roles'] = [role for role in os_record.roles]
                keys = self.shell.key_pair_get_all_by_user(name)
                record['keys'] = [key.public_key for key in keys]     
            elif record['type'] == 'slice': 
                os_record = self.shell.project_get(name)
                record['description'] = os_record.description
                record['PI'] = self.hrn + "." + os_record.project_manager
                record['geni_creator'] = record['PI'] 
                record['researcher'] = [self.hrn + "." + user.name for \
                                         user in os_record.members]
            else:
                continue
            record['geni_urn'] = hrn_to_urn(record['hrn'], record['type'])
            record['geni_certificate'] = record['gid'] 
            record['name'] = os_record.name
            if os_record.created_at is not None:    
                record['date_created'] = datetime_to_string(utcparse(os_record.created_at))
            if os_record.updated_at is not None:
                record['last_updated'] = datetime_to_string(utcparse(os_record.updated_at))
 
        return records


    ####################
    # plcapi works by changes, compute what needs to be added/deleted
    def update_relation (self, subject_type, target_type, subject_id, target_ids):
        # hard-wire the code for slice/user for now, could be smarter if needed
        if subject_type =='slice' and target_type == 'user':
            subject=self.shell.project_get(subject_id)[0]
            current_target_ids = [user.name for user in subject.members]
            add_target_ids = list ( set (target_ids).difference(current_target_ids))
            del_target_ids = list ( set (current_target_ids).difference(target_ids))
            logger.debug ("subject_id = %s (type=%s)"%(subject_id,type(subject_id)))
            for target_id in add_target_ids:
                self.shell.project_add_member(target_id,subject_id)
                logger.debug ("add_target_id = %s (type=%s)"%(target_id,type(target_id)))
            for target_id in del_target_ids:
                logger.debug ("del_target_id = %s (type=%s)"%(target_id,type(target_id)))
                self.shell.project_remove_member(target_id, subject_id)
        else:
            logger.info('unexpected relation to maintain, %s -> %s'%(subject_type,target_type))

        
    ########################################
    ########## aggregate oriented
    ########################################

    def testbed_name (self): return "openstack"

    # 'geni_request_rspec_versions' and 'geni_ad_rspec_versions' are mandatory
    def aggregate_version (self):
        version_manager = VersionManager()
        ad_rspec_versions = []
        request_rspec_versions = []
        for rspec_version in version_manager.versions:
            if rspec_version.content_type in ['*', 'ad']:
                ad_rspec_versions.append(rspec_version.to_dict())
            if rspec_version.content_type in ['*', 'request']:
                request_rspec_versions.append(rspec_version.to_dict()) 
        return {
            'testbed':self.testbed_name(),
            'geni_request_rspec_versions': request_rspec_versions,
            'geni_ad_rspec_versions': ad_rspec_versions,
            }

    def list_slices (self, creds, options):
        # look in cache first
        if self.cache:
            slices = self.cache.get('slices')
            if slices:
                logger.debug("PlDriver.list_slices returns from cache")
                return slices
    
        # get data from db 
        slices = self.shell.GetSlices({'peer_id': None}, ['name'])
        slice_hrns = [slicename_to_hrn(self.hrn, slice['name']) for slice in slices]
        slice_urns = [hrn_to_urn(slice_hrn, 'slice') for slice_hrn in slice_hrns]
    
        # cache the result
        if self.cache:
            logger.debug ("PlDriver.list_slices stores value in cache")
            self.cache.add('slices', slice_urns) 
    
        return slice_urns
        
    # first 2 args are None in case of resource discovery
    def list_resources (self, slice_urn, slice_hrn, creds, options):
        cached_requested = options.get('cached', True) 
    
        version_manager = VersionManager()
        # get the rspec's return format from options
        rspec_version = version_manager.get_version(options.get('geni_rspec_version'))
        version_string = "rspec_%s" % (rspec_version)
    
        #panos adding the info option to the caching key (can be improved)
        if options.get('info'):
            version_string = version_string + "_"+options.get('info', 'default')
    
        # look in cache first
        if cached_requested and self.cache and not slice_hrn:
            rspec = self.cache.get(version_string)
            if rspec:
                logger.debug("PlDriver.ListResources: returning cached advertisement")
                return rspec 
    
        #panos: passing user-defined options
        #print "manager options = ",options
        aggregate = PlAggregate(self)
        rspec =  aggregate.get_rspec(slice_xrn=slice_urn, version=rspec_version, 
                                     options=options)
    
        # cache the result
        if self.cache and not slice_hrn:
            logger.debug("PlDriver.ListResources: stores advertisement in cache")
            self.cache.add(version_string, rspec)
    
        return rspec
    
    def sliver_status (self, slice_urn, slice_hrn):
        # find out where this slice is currently running
        slicename = hrn_to_pl_slicename(slice_hrn)
        
        slices = self.shell.GetSlices([slicename], ['slice_id', 'node_ids','person_ids','name','expires'])
        if len(slices) == 0:        
            raise SliverDoesNotExist("%s (used %s as slicename internally)" % (slice_hrn, slicename))
        slice = slices[0]
        
        # report about the local nodes only
        nodes = self.shell.GetNodes({'node_id':slice['node_ids'],'peer_id':None},
                              ['node_id', 'hostname', 'site_id', 'boot_state', 'last_contact'])

        if len(nodes) == 0:
            raise SliverDoesNotExist("You have not allocated any slivers here") 

        site_ids = [node['site_id'] for node in nodes]
    
        result = {}
        top_level_status = 'unknown'
        if nodes:
            top_level_status = 'ready'
        result['geni_urn'] = slice_urn
        result['pl_login'] = slice['name']
        result['pl_expires'] = datetime_to_string(utcparse(slice['expires']))
        
        resources = []
        for node in nodes:
            res = {}
            res['pl_hostname'] = node['hostname']
            res['pl_boot_state'] = node['boot_state']
            res['pl_last_contact'] = node['last_contact']
            if node['last_contact'] is not None:
                
                res['pl_last_contact'] = datetime_to_string(utcparse(node['last_contact']))
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

    def create_sliver (self, slice_urn, slice_hrn, creds, rspec_string, users, options):

        aggregate = PlAggregate(self)
        slices = PlSlices(self)
        peer = slices.get_peer(slice_hrn)
        sfa_peer = slices.get_sfa_peer(slice_hrn)
        slice_record=None    
        if users:
            slice_record = users[0].get('slice_record', {})
    
        # parse rspec
        rspec = RSpec(rspec_string)
        requested_attributes = rspec.version.get_slice_attributes()
        
        # ensure site record exists
        site = slices.verify_site(slice_hrn, slice_record, peer, sfa_peer, options=options)
        # ensure slice record exists
        slice = slices.verify_slice(slice_hrn, slice_record, peer, sfa_peer, options=options)
        # ensure person records exists
        persons = slices.verify_persons(slice_hrn, slice, users, peer, sfa_peer, options=options)
        # ensure slice attributes exists
        slices.verify_slice_attributes(slice, requested_attributes, options=options)
        
        # add/remove slice from nodes
        requested_slivers = [node.get('component_name') for node in rspec.version.get_nodes_with_slivers()]
        nodes = slices.verify_slice_nodes(slice, requested_slivers, peer) 
   
        # add/remove links links 
        slices.verify_slice_links(slice, rspec.version.get_link_requests(), nodes)
    
        # handle MyPLC peer association.
        # only used by plc and ple.
        slices.handle_peer(site, slice, persons, peer)
        
        return aggregate.get_rspec(slice_xrn=slice_urn, version=rspec.version)

    def delete_sliver (self, slice_urn, slice_hrn, creds, options):
        slicename = hrn_to_pl_slicename(slice_hrn)
        slices = self.shell.GetSlices({'name': slicename})
        if not slices:
            return 1
        slice = slices[0]
    
        # determine if this is a peer slice
        # xxx I wonder if this would not need to use PlSlices.get_peer instead 
        # in which case plc.peers could be deprecated as this here
        # is the only/last call to this last method in plc.peers
        peer = peers.get_peer(self, slice_hrn)
        try:
            if peer:
                self.shell.UnBindObjectFromPeer('slice', slice['slice_id'], peer)
            self.shell.DeleteSliceFromNodes(slicename, slice['node_ids'])
        finally:
            if peer:
                self.shell.BindObjectToPeer('slice', slice['slice_id'], peer, slice['peer_slice_id'])
        return 1
    
    def renew_sliver (self, slice_urn, slice_hrn, creds, expiration_time, options):
        slicename = hrn_to_pl_slicename(slice_hrn)
        slices = self.shell.GetSlices({'name': slicename}, ['slice_id'])
        if not slices:
            raise RecordNotFound(slice_hrn)
        slice = slices[0]
        requested_time = utcparse(expiration_time)
        record = {'expires': int(datetime_to_epoch(requested_time))}
        try:
            self.shell.UpdateSlice(slice['slice_id'], record)
            return True
        except:
            return False

    # remove the 'enabled' tag 
    def start_slice (self, slice_urn, slice_hrn, creds):
        slicename = hrn_to_pl_slicename(slice_hrn)
        slices = self.shell.GetSlices({'name': slicename}, ['slice_id'])
        if not slices:
            raise RecordNotFound(slice_hrn)
        slice_id = slices[0]['slice_id']
        slice_tags = self.shell.GetSliceTags({'slice_id': slice_id, 'tagname': 'enabled'}, ['slice_tag_id'])
        # just remove the tag if it exists
        if slice_tags:
            self.shell.DeleteSliceTag(slice_tags[0]['slice_tag_id'])
        return 1

    # set the 'enabled' tag to 0
    def stop_slice (self, slice_urn, slice_hrn, creds):
        slicename = hrn_to_pl_slicename(slice_hrn)
        slices = self.shell.GetSlices({'name': slicename}, ['slice_id'])
        if not slices:
            raise RecordNotFound(slice_hrn)
        slice_id = slices[0]['slice_id']
        slice_tags = self.shell.GetSliceTags({'slice_id': slice_id, 'tagname': 'enabled'})
        if not slice_tags:
            self.shell.AddSliceTag(slice_id, 'enabled', '0')
        elif slice_tags[0]['value'] != "0":
            tag_id = slice_tags[0]['slice_tag_id']
            self.shell.UpdateSliceTag(tag_id, '0')
        return 1
    
    def reset_slice (self, slice_urn, slice_hrn, creds):
        raise SfaNotImplemented ("reset_slice not available at this interface")
    
    # xxx this code is quite old and has not run for ages
    # it is obviously totally broken and needs a rewrite
    def get_ticket (self, slice_urn, slice_hrn, creds, rspec_string, options):
        raise SfaNotImplemented,"PlDriver.get_ticket needs a rewrite"
# please keep this code for future reference
#        slices = PlSlices(self)
#        peer = slices.get_peer(slice_hrn)
#        sfa_peer = slices.get_sfa_peer(slice_hrn)
#    
#        # get the slice record
#        credential = api.getCredential()
#        interface = api.registries[api.hrn]
#        registry = api.server_proxy(interface, credential)
#        records = registry.Resolve(xrn, credential)
#    
#        # make sure we get a local slice record
#        record = None
#        for tmp_record in records:
#            if tmp_record['type'] == 'slice' and \
#               not tmp_record['peer_authority']:
#    #Error (E0602, GetTicket): Undefined variable 'SliceRecord'
#                slice_record = SliceRecord(dict=tmp_record)
#        if not record:
#            raise RecordNotFound(slice_hrn)
#        
#        # similar to CreateSliver, we must verify that the required records exist
#        # at this aggregate before we can issue a ticket
#        # parse rspec
#        rspec = RSpec(rspec_string)
#        requested_attributes = rspec.version.get_slice_attributes()
#    
#        # ensure site record exists
#        site = slices.verify_site(slice_hrn, slice_record, peer, sfa_peer)
#        # ensure slice record exists
#        slice = slices.verify_slice(slice_hrn, slice_record, peer, sfa_peer)
#        # ensure person records exists
#    # xxx users is undefined in this context
#        persons = slices.verify_persons(slice_hrn, slice, users, peer, sfa_peer)
#        # ensure slice attributes exists
#        slices.verify_slice_attributes(slice, requested_attributes)
#        
#        # get sliver info
#        slivers = slices.get_slivers(slice_hrn)
#    
#        if not slivers:
#            raise SliverDoesNotExist(slice_hrn)
#    
#        # get initscripts
#        initscripts = []
#        data = {
#            'timestamp': int(time.time()),
#            'initscripts': initscripts,
#            'slivers': slivers
#        }
#    
#        # create the ticket
#        object_gid = record.get_gid_object()
#        new_ticket = SfaTicket(subject = object_gid.get_subject())
#        new_ticket.set_gid_caller(api.auth.client_gid)
#        new_ticket.set_gid_object(object_gid)
#        new_ticket.set_issuer(key=api.key, subject=self.hrn)
#        new_ticket.set_pubkey(object_gid.get_pubkey())
#        new_ticket.set_attributes(data)
#        new_ticket.set_rspec(rspec)
#        #new_ticket.set_parent(api.auth.hierarchy.get_auth_ticket(auth_hrn))
#        new_ticket.encode()
#        new_ticket.sign()
#    
#        return new_ticket.save_to_string(save_parents=True)