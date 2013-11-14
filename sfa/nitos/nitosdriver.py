import time
import datetime
#
from sfa.util.faults import MissingSfaInfo, UnknownSfaType, \
    RecordNotFound, SfaNotImplemented, SliverDoesNotExist

from sfa.util.sfalogging import logger
from sfa.util.defaultdict import defaultdict
from sfa.util.sfatime import utcparse, datetime_to_string, datetime_to_epoch
from sfa.util.xrn import Xrn, hrn_to_urn, get_leaf, urn_to_hrn
from sfa.util.cache import Cache

# one would think the driver should not need to mess with the SFA db, but..
from sfa.storage.model import RegRecord

# used to be used in get_ticket
#from sfa.trust.sfaticket import SfaTicket

from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec

# the driver interface, mostly provides default behaviours
from sfa.managers.driver import Driver

from sfa.nitos.nitosshell import NitosShell
from sfa.nitos.nitosaggregate import NitosAggregate
from sfa.nitos.nitosslices import NitosSlices

from sfa.nitos.nitosxrn import NitosXrn, slicename_to_hrn, hostname_to_hrn, hrn_to_nitos_slicename, xrn_to_hostname

def list_to_dict(recs, key):
    """
    convert a list of dictionaries into a dictionary keyed on the 
    specified dictionary key 
    """
    return dict ( [ (rec[key],rec) for rec in recs ] )

#
# NitosShell is just an xmlrpc serverproxy where methods
# can be sent as-is; it takes care of authentication
# from the global config
# 
class NitosDriver (Driver):

    # the cache instance is a class member so it survives across incoming requests
    cache = None

    def __init__ (self, api):
        Driver.__init__ (self, api)
        config = api.config
        self.shell = NitosShell (config)
        self.cache=None
        self.testbedInfo = self.shell.getTestbedInfo()
# un-comment below lines to enable caching
#        if config.SFA_AGGREGATE_CACHING:
#            if NitosDriver.cache is None:
#                NitosDriver.cache = Cache()
#            self.cache = NitosDriver.cache
 
    ###########################################
    ########## utility methods for NITOS driver
    ###########################################


    def filter_nitos_results (self, listo, filters_dict):
        """
        the Nitos scheduler API does not provide a get result filtring so we do it here
        """
        mylist = []
        mylist.extend(listo)
        for dicto in mylist:
             for filter in filters_dict:
                  if filter not in dicto or dicto[filter] != filters_dict[filter]:
                      listo.remove(dicto)
                      break
        return listo

    def convert_id (self, list_of_dict):
        """
        convert object id retrived in string format to int format
        """
        for dicto in list_of_dict:
             for key in dicto:
                  if key in ['node_id', 'slice_id', 'user_id', 'channel_id', 'reservation_id'] and isinstance(dicto[key], str):
                      dicto[key] = int(dicto[key])
                  elif key in ['user_ids']:
                      user_ids2 = []
                      for user_id in dicto['user_ids']:
                           user_ids2.append(int(user_id))
                      dicto['user_ids'] = user_ids2
        return list_of_dict



    ########################################
    ########## registry oriented
    ########################################

    def augment_records_with_testbed_info (self, sfa_records):
        return self.fill_record_info (sfa_records)

    ########## 
    def register (self, sfa_record, hrn, pub_key):
        type = sfa_record['type']
        nitos_record = self.sfa_fields_to_nitos_fields(type, hrn, sfa_record)

        if type == 'authority':
            pointer = -1

        elif type == 'slice':
            slices = self.shell.getSlices()
            # filter slices
            for slice in slices:
                 if slice['slice_name'] == nitos_record['name']:
                     slice_id = slice['slice_id']
                     break
 
            if not slice_id:
                 pointer = self.shell.addSlice({'slice_name' : nitos_record['name']})
            else:
                 pointer = slice_id

        elif type == 'user':
            users = self.shell.getUsers()
            # filter users
            for user in users:
                 if user['user_name'] == nitos_record['name']:
                     user_id = user['user_id']
                     break
            if not user_id:
                pointer = self.shell.addUser({'username' : nitos_record['name'], 'email' : nitos_record['email']})
            else:
                pointer = user_id
    

            # Add the user's key
            if pub_key:
                self.shell.addUserKey({'user_id' : pointer,'key' : pub_key})

        elif type == 'node':
            nodes = self.shell.GetNodes({}, [])
            # filter nodes
            for node in nodes:
                 if node['hostname'] == nitos_record['name']:
                     node_id = node['node_id']
                     break

            if not node_id:
                pointer = self.shell.addNode(nitos_record)
            else:
                pointer = node_id
    
        return pointer
        
    ##########
    def update (self, old_sfa_record, new_sfa_record, hrn, new_key):
        
        pointer = old_sfa_record['pointer']
        type = old_sfa_record['type']
        new_nitos_record = self.sfa_fields_to_nitos_fields(type, hrn, new_sfa_record)

        # new_key implemented for users only
        if new_key and type not in [ 'user' ]:
            raise UnknownSfaType(type)

        if type == "slice":
            if 'name' in new_sfa_record:
                self.shell.updateSlice({'slice_id': pointer, 'fields': {'slice_name': new_sfa_record['name']}})
    
        elif type == "user":
            update_fields = {}
            if 'name' in new_sfa_record:
                update_fields['username'] = new_sfa_record['name']
            if 'email' in new_sfa_record:
                update_fields['email'] = new_sfa_record['email']
 
            self.shell.updateUser({'user_id': pointer, 'fields': update_fields}) 
    
            if new_key:
                # needs to be improved 
                self.shell.addUserKey({'user_id': pointer, 'key': new_key}) 
    
        elif type == "node":
            self.shell.updateNode({'node_id': pointer, 'fields': new_sfa_record})

        return True
        

    ##########
    def remove (self, sfa_record):

        type=sfa_record['type']
        pointer=sfa_record['pointer']
        if type == 'user':
            self.shell.deleteUser({'user_id': pointer})
        elif type == 'slice':
            self.shell.deleteSlice({'slice_id': pointer})
        elif type == 'node':
            self.shell.deleteNode({'node_id': pointer})

        return True
        




    ##
    # Convert SFA fields to NITOS fields for use when registering or updating
    # registry record in the NITOS Scheduler database
    #

    def sfa_fields_to_nitos_fields(self, type, hrn, sfa_record):

        nitos_record = {}
 
        if type == "slice":
            nitos_record["slice_name"] = hrn_to_nitos_slicename(hrn)
        elif type == "node":
            if "hostname" not in sfa_record:
                raise MissingSfaInfo("hostname")
            nitos_record["node_name"] = sfa_record["hostname"]

        return nitos_record

    ####################
    def fill_record_info(self, records):
        """
        Given a (list of) SFA record, fill in the NITOS specific 
        and SFA specific fields in the record. 
        """
        if not isinstance(records, list):
            records = [records]

        self.fill_record_nitos_info(records)
        self.fill_record_hrns(records)
        self.fill_record_sfa_info(records)
        return records

    def fill_record_nitos_info(self, records):
        """
        Fill in the nitos specific fields of a SFA record. This
        involves calling the appropriate NITOS API method to retrieve the 
        database record for the object.
            
        @param record: record to fill in field (in/out param)     
        """
        
        # get ids by type
        node_ids, slice_ids = [], [] 
        user_ids, key_ids = [], []
        type_map = {'node': node_ids, 'slice': slice_ids, 'user': user_ids}
                  
        for record in records:
            for type in type_map:
                if type == record['type']:
                    type_map[type].append(record['pointer'])

        # get nitos records
        nodes, slices, users, keys = {}, {}, {}, {}
        if node_ids:
            all_nodes = self.convert_id(self.shell.getNodes({}, []))
            node_list =  [node for node in all_nodes if node['node_id'] in node_ids]
            nodes = list_to_dict(node_list, 'node_id')
        if slice_ids:
            all_slices = self.convert_id(self.shell.getSlices({}, []))
            slice_list =  [slice for slice in all_slices if slice['slice_id'] in slice_ids]
            slices = list_to_dict(slice_list, 'slice_id')
        if user_ids:
            all_users = self.convert_id(self.shell.getUsers())
            user_list = [user for user in all_users if user['user_id'] in user_ids] 
            users = list_to_dict(user_list, 'user_id')

        nitos_records = {'node': nodes, 'slice': slices, 'user': users}


        # fill record info
        for record in records:
            if record['pointer'] == -1:
                continue
           
            for type in nitos_records:
                if record['type'] == type:
                    if record['pointer'] in nitos_records[type]:
                        record.update(nitos_records[type][record['pointer']])
                        break
            # fill in key info
            if record['type'] == 'user':
                if record['pointer'] in nitos_records['user']:
                    record['keys'] = nitos_records['user'][record['pointer']]['keys']

        return records
        
 
    def fill_record_hrns(self, records):
        """
        convert nitos ids to hrns
        """


        # get ids
        slice_ids, user_ids, node_ids = [], [], []
        for record in records:
            if 'user_ids' in record:
                user_ids.extend(record['user_ids'])
            if 'slice_ids' in record:
                slice_ids.extend(record['slice_ids'])
            if 'node_ids' in record:
                node_ids.extend(record['node_ids'])

        # get nitos records
        slices, users, nodes = {}, {}, {}
        if node_ids:
            all_nodes = self.convert_id(self.shell.getNodes({}, []))
            node_list =  [node for node in all_nodes if node['node_id'] in node_ids]
            nodes = list_to_dict(node_list, 'node_id')
        if slice_ids:
            all_slices = self.convert_id(self.shell.getSlices({}, []))
            slice_list =  [slice for slice in all_slices if slice['slice_id'] in slice_ids]
            slices = list_to_dict(slice_list, 'slice_id')
        if user_ids:
            all_users = self.convert_id(self.shell.getUsers())
            user_list = [user for user in all_users if user['user_id'] in user_ids]
            users = list_to_dict(user_list, 'user_id')

       
        # convert ids to hrns
        for record in records:
            # get all relevant data
            type = record['type']
            pointer = record['pointer']
            auth_hrn = self.hrn
            testbed_name = self.testbedInfo['name']
            if pointer == -1:
                continue
            if 'user_ids' in record:
                usernames = [users[user_id]['username'] for user_id in record['user_ids'] \
                          if user_id in  users]
                user_hrns = [".".join([auth_hrn, testbed_name, username]) for username in usernames]
                record['users'] = user_hrns 
            if 'slice_ids' in record:
                slicenames = [slices[slice_id]['slice_name'] for slice_id in record['slice_ids'] \
                              if slice_id in slices]
                slice_hrns = [slicename_to_hrn(auth_hrn, slicename) for slicename in slicenames]
                record['slices'] = slice_hrns
            if 'node_ids' in record:
                hostnames = [nodes[node_id]['hostname'] for node_id in record['node_ids'] \
                             if node_id in nodes]
                node_hrns = [hostname_to_hrn(auth_hrn, login_base, hostname) for hostname in hostnames]
                record['nodes'] = node_hrns

            if 'expires' in record:
                date = utcparse(record['expires'])
                datestring = datetime_to_string(date)
                record['expires'] = datestring 
            
        return records   
 
    def fill_record_sfa_info(self, records):
        
        def startswith(prefix, values):
            return [value for value in values if value.startswith(prefix)]

        # get user ids
        user_ids = []
        for record in records:
            user_ids.extend(record.get("user_ids", []))
        
        # get the registry records
        user_list, users = [], {}
        user_list = self.api.dbsession().query(RegRecord).filter(RegRecord.pointer.in_(user_ids)).all()
        # create a hrns keyed on the sfa record's pointer.
        # Its possible for multiple records to have the same pointer so
        # the dict's value will be a list of hrns.
        users = defaultdict(list)
        for user in user_list:
            users[user.pointer].append(user)

        # get the nitos records
        nitos_user_list, nitos_users = [], {}
        nitos_all_users = self.convert_id(self.shell.getUsers())
        nitos_user_list = [user for user in nitos_all_users if user['user_id'] in user_ids]
        nitos_users = list_to_dict(nitos_user_list, 'user_id')


        # fill sfa info
        for record in records:
            if record['pointer'] == -1:
                continue 

            sfa_info = {}
            type = record['type']
            logger.info("fill_record_sfa_info - incoming record typed %s"%type)
            if (type == "slice"):
                # all slice users are researchers
                record['geni_urn'] = hrn_to_urn(record['hrn'], 'slice')
                record['researcher'] = []
                for user_id in record.get('user_ids', []):
                    hrns = [user.hrn for user in users[user_id]]
                    record['researcher'].extend(hrns)                
                
            elif (type == "node"):
                sfa_info['dns'] = record.get("hostname", "")
                # xxx TODO: URI, LatLong, IP, DNS
    
            elif (type == "user"):
                logger.info('setting user.email')
                sfa_info['email'] = record.get("email", "")
                sfa_info['geni_urn'] = hrn_to_urn(record['hrn'], 'user')
                sfa_info['geni_certificate'] = record['gid'] 
                # xxx TODO: PostalAddress, Phone
            record.update(sfa_info)

    ####################
    def update_relation (self, subject_type, target_type, relation_name, subject_id, target_ids):
        
        if subject_type =='slice' and target_type == 'user' and relation_name == 'researcher':
            subject=self.shell.getSlices ({'slice_id': subject_id}, [])[0]
            current_target_ids = subject['user_ids']
            add_target_ids = list ( set (target_ids).difference(current_target_ids))
            del_target_ids = list ( set (current_target_ids).difference(target_ids))
            logger.debug ("subject_id = %s (type=%s)"%(subject_id,type(subject_id)))
            for target_id in add_target_ids:
                self.shell.addUserToSlice ({'user_id': target_id, 'slice_id': subject_id})
                logger.debug ("add_target_id = %s (type=%s)"%(target_id,type(target_id)))
            for target_id in del_target_ids:
                logger.debug ("del_target_id = %s (type=%s)"%(target_id,type(target_id)))
                self.shell.deleteUserFromSlice ({'user_id': target_id, 'slice_id': subject_id})
        else:
            logger.info('unexpected relation %s to maintain, %s -> %s'%(relation_name,subject_type,target_type))


    ########################################
    ########## aggregate oriented
    ########################################

    def testbed_name (self): return "nitos"

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
                logger.debug("NitosDriver.list_slices returns from cache")
                return slices

        # get data from db 
        slices = self.shell.getSlices({}, [])
        testbed_name = self.testbedInfo['name']
        slice_hrns = [slicename_to_hrn(self.hrn, testbed_name, slice['slice_name']) for slice in slices]
        slice_urns = [hrn_to_urn(slice_hrn, 'slice') for slice_hrn in slice_hrns]

        # cache the result
        if self.cache:
            logger.debug ("NitosDriver.list_slices stores value in cache")
            self.cache.add('slices', slice_urns) 
    
        return slice_urns
        
    # first 2 args are None in case of resource discovery
    def list_resources (self, slice_urn, slice_hrn, creds, options):
        cached_requested = options.get('cached', True) 
        version_manager = VersionManager()
        # get the rspec's return format from options
        #rspec_version = version_manager.get_version(options.get('geni_rspec_version'))
        # rspec's return format for nitos aggregate is version  NITOS 1
        rspec_version = version_manager.get_version('NITOS 1')
        version_string = "rspec_%s" % (rspec_version)
 
        #panos adding the info option to the caching key (can be improved)
        if options.get('info'):
            version_string = version_string + "_"+options.get('info', 'default')

        # Adding the list_leases option to the caching key
        if options.get('list_leases'):
            version_string = version_string + "_"+options.get('list_leases', 'default')

        # Adding geni_available to caching key
        if options.get('geni_available'):
            version_string = version_string + "_" + str(options.get('geni_available'))
    
        # look in cache first
        if cached_requested and self.cache and not slice_hrn:
            rspec = self.cache.get(version_string)
            if rspec:
                logger.debug("NitosDriver.ListResources: returning cached advertisement")
                return rspec 
    
        #panos: passing user-defined options
        #print "manager options = ",options
        aggregate = NitosAggregate(self)
        rspec =  aggregate.get_rspec(slice_xrn=slice_urn, version=rspec_version, 
                                     options=options)
 
        # cache the result
        if self.cache and not slice_hrn:
            logger.debug("NitosDriver.ListResources: stores advertisement in cache")
            self.cache.add(version_string, rspec)
    
        return rspec
    
    def sliver_status (self, slice_urn, slice_hrn):
        # find out where this slice is currently running
        slicename = hrn_to_nitos_slicename(slice_hrn)
        
        slices = self.shell.getSlices({}, [])
        # filter slicename
        if len(slices) == 0:        
            raise SliverDoesNotExist("%s (used %s as slicename internally)" % (slice_hrn, slicename))
        
        for slice in slices:
             if slice['slice_name'] == slicename: 
                 user_slice = slice
                 break

        if not user_slice:
            raise SliverDoesNotExist("%s (used %s as slicename internally)" % (slice_hrn, slicename))

        # report about the reserved nodes only
        reserved_nodes = self.shell.getReservedNodes({}, [])
        nodes = self.shell.getNodes({}, [])

        slice_reserved_nodes = []
        for r_node in reserved_nodes:
             if r_node['slice_id'] == slice['slice_id']:
                 for node in nodes:
                     if node['node_id'] == r_node['node_id']:
                         slice_reserved_nodes.append(node)
        
        


        if len(slice_reserved_nodes) == 0:
            raise SliverDoesNotExist("You have not allocated any slivers here") 

##### continue from here
        # get login info
        user = {}
        keys = []
        if slice['user_ids']:
            users = self.shell.getUsers()
            # filter users on slice['user_ids']
            for usr in users:
                 if usr['user_id'] in slice['user_ids']:
                     keys.extend(usr['keys'])
                     

            user.update({'urn': slice_urn,
                         'login': slice['slice_name'],
                         'protocol': ['ssh'],
                         'port': ['22'],
                         'keys': keys})

    
        result = {}
        top_level_status = 'unknown'
        if slice_reserved_nodes:
            top_level_status = 'ready'
        result['geni_urn'] = slice_urn
        result['nitos_gateway_login'] = slice['slice_name']
        #result['pl_expires'] = datetime_to_string(utcparse(slice['expires']))
        #result['geni_expires'] = datetime_to_string(utcparse(slice['expires']))
        
        resources = []
        for node in slice_reserved_nodes:
            res = {}
            res['nitos_hostname'] = node['hostname']
            sliver_id = Xrn(slice_urn, type='slice', id=node['node_id']).urn
            res['geni_urn'] = sliver_id
            res['geni_status'] = 'ready'
            res['geni_error'] = ''
            res['users'] = [user]  
    
            resources.append(res)
            
        result['geni_status'] = top_level_status
        result['geni_resources'] = resources
        
        return result

    def create_sliver (self, slice_urn, slice_hrn, creds, rspec_string, users, options):

        aggregate = NitosAggregate(self)
        slices = NitosSlices(self)
        sfa_peer = slices.get_sfa_peer(slice_hrn)
        slice_record=None    
        if users:
            slice_record = users[0].get('slice_record', {})
    
        # parse rspec
        rspec = RSpec(rspec_string, version='NITOS 1')

        # ensure slice record exists
        slice = slices.verify_slice(slice_hrn, slice_record, sfa_peer, options=options)
        # ensure user records exists
        users = slices.verify_users(slice_hrn, slice, users, sfa_peer, options=options)
        
        # add/remove leases (nodes and channels)
        # a lease in Nitos RSpec case is a reservation of nodes and channels grouped by (slice,timeslot)
        rspec_requested_leases = rspec.version.get_leases()
        rspec_requested_nodes = []
        rspec_requested_channels = []
        for lease in rspec_requested_leases:
             if lease['type'] == 'node':
                 lease.pop('type', None)
                 rspec_requested_nodes.append(lease)
             else:
                 lease.pop('type', None)
                 rspec_requested_channels.append(lease)                 
        
        nodes = slices.verify_slice_leases_nodes(slice, rspec_requested_nodes)
        channels = slices.verify_slice_leases_channels(slice, rspec_requested_channels)

        return aggregate.get_rspec(slice_xrn=slice_urn, version=rspec.version)

    def delete_sliver (self, slice_urn, slice_hrn, creds, options):
        slicename = hrn_to_nitos_slicename(slice_hrn)
        slices = self.filter_nitos_results(self.shell.getSlices({}, []), {'slice_name': slicename})
        if not slices:
            return 1
        slice = slices[0]

        slice_reserved_nodes = self.filter_nitos_results(self.shell.getReservedNodes({}, []), {'slice_id': slice['slice_id'] })
        slice_reserved_channels = self.filter_nitos_results(self.shell.getReservedChannels(), {'slice_id': slice['slice_id'] })

        slice_reserved_nodes_ids = [node['reservation_id'] for node in slice_reserved_nodes]
        slice_reserved_channels_ids = [channel['reservation_id'] for channel in slice_reserved_channels]

        # release all reserved nodes and channels for that slice
        try:
            released_nodes = self.shell.releaseNodes({'reservation_ids': slice_reserved_nodes_ids})
            released_channels = self.shell.releaseChannels({'reservation_ids': slice_reserved_channels_ids})
        except:
            pass
        return 1

    def renew_sliver (self, slice_urn, slice_hrn, creds, expiration_time, options):
        slicename = hrn_to_nitos_slicename(slice_hrn)
        slices = self.shell.GetSlices({'slicename': slicename}, ['slice_id'])
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

    
    # xxx this code is quite old and has not run for ages
    # it is obviously totally broken and needs a rewrite
    def get_ticket (self, slice_urn, slice_hrn, creds, rspec_string, options):
        raise SfaNotImplemented,"NitosDriver.get_ticket needs a rewrite"
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
