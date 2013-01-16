import time
import datetime
#
from sfa.util.faults import MissingSfaInfo, UnknownSfaType, \
    RecordNotFound, SfaNotImplemented, SliverDoesNotExist

from sfa.util.sfalogging import logger
from sfa.util.defaultdict import defaultdict
from sfa.util.sfatime import utcparse, datetime_to_string, datetime_to_epoch
from sfa.util.xrn import Xrn, hrn_to_urn, get_leaf
from sfa.util.cache import Cache

# one would think the driver should not need to mess with the SFA db, but..
from sfa.storage.alchemy import dbsession
from sfa.storage.model import RegRecord

# used to be used in get_ticket
#from sfa.trust.sfaticket import SfaTicket

from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec

# the driver interface, mostly provides default behaviours
from sfa.managers.driver import Driver

from sfa.dummy.dummyshell import DummyShell
from sfa.dummy.dummyaggregate import DummyAggregate
from sfa.dummy.dummyslices import DummySlices
from sfa.dummy.dummyxrn import DummyXrn, slicename_to_hrn, hostname_to_hrn, hrn_to_dummy_slicename, xrn_to_hostname


def list_to_dict(recs, key):
    """
    convert a list of dictionaries into a dictionary keyed on the 
    specified dictionary key 
    """
    return dict ( [ (rec[key],rec) for rec in recs ] )

#
# DummyShell is just an xmlrpc serverproxy where methods can be sent as-is; 
# 
class DummyDriver (Driver):

    # the cache instance is a class member so it survives across incoming requests
    cache = None

    def __init__ (self, config):
        Driver.__init__ (self, config)
        self.config = config
        self.hrn = config.SFA_INTERFACE_HRN
        self.root_auth = config.SFA_REGISTRY_ROOT_AUTH
        self.shell = DummyShell (config)
        self.testbedInfo = self.shell.GetTestbedInfo()
 
    ########################################
    ########## registry oriented
    ########################################

    def augment_records_with_testbed_info (self, sfa_records):
        return self.fill_record_info (sfa_records)

    ########## 
    def register (self, sfa_record, hrn, pub_key):
        type = sfa_record['type']
        dummy_record = self.sfa_fields_to_dummy_fields(type, hrn, sfa_record)
        
        if type == 'authority':
            pointer = -1

        elif type == 'slice':
            slices = self.shell.GetSlices({'slice_name': dummy_record['slice_name']})
            if not slices:
                 pointer = self.shell.AddSlice(dummy_record)
            else:
                 pointer = slices[0]['slice_id']

        elif type == 'user':
            users = self.shell.GetUsers({'email':sfa_record['email']})
            if not users:
                pointer = self.shell.AddUser(dummy_record)
            else:
                pointer = users[0]['user_id']
    
            # Add the user's key
            if pub_key:
                self.shell.AddUserKey({'user_id' : pointer, 'key' : pub_key})

        elif type == 'node':
            nodes = self.shell.GetNodes(dummy_record['hostname'])
            if not nodes:
                pointer = self.shell.AddNode(dummy_record)
            else:
                pointer = users[0]['node_id']
    
        return pointer
        
    ##########
    def update (self, old_sfa_record, new_sfa_record, hrn, new_key):
        pointer = old_sfa_record['pointer']
        type = old_sfa_record['type']
        dummy_record=self.sfa_fields_to_dummy_fields(type, hrn, new_sfa_record)

        # new_key implemented for users only
        if new_key and type not in [ 'user' ]:
            raise UnknownSfaType(type)

    
        if type == "slice":
            self.shell.UpdateSlice({'slice_id': pointer, 'fields': dummy_record})
    
        elif type == "user":
            self.shell.UpdateUser({'user_id': pointer, 'fields': dummy_record})

            if new_key:
                self.shell.AddUserKey({'user_id' : pointer, 'key' : new_key})

        elif type == "node":
            self.shell.UpdateNode({'node_id': pointer, 'fields': dummy_record})


        return True
        

    ##########
    def remove (self, sfa_record):
        type=sfa_record['type']
        pointer=sfa_record['pointer']
        if type == 'user':
            self.shell.DeleteUser({'user_id': pointer})
        elif type == 'slice':
            self.shell.DeleteSlice({'slice_id': pointer})
        elif type == 'node':
            self.shell.DeleteNode({'node_id': pointer})

        return True





    ##
    # Convert SFA fields to Dummy testbed fields for use when registering or updating
    # registry record in the dummy testbed
    #

    def sfa_fields_to_dummy_fields(self, type, hrn, sfa_record):

        dummy_record = {}
 
        if type == "slice":
            dummy_record["slice_name"] = hrn_to_dummy_slicename(hrn)
        
        elif type == "node":
            if "hostname" not in sfa_record:
                raise MissingSfaInfo("hostname")
            dummy_record["hostname"] = sfa_record["hostname"]
            if "type" in sfa_record:
               dummy_record["type"] = sfa_record["type"]
            else:
               dummy_record["type"] = "dummy_type"
 
        elif type == "authority":
            dummy_record["name"] = hrn

        elif type == "user":
            dummy_record["user_name"] = sfa_record["email"].split('@')[0]
            dummy_record["email"] = sfa_record["email"]

        return dummy_record

    ####################
    def fill_record_info(self, records):
        """
        Given a (list of) SFA record, fill in the DUMMY TESTBED specific 
        and SFA specific fields in the record. 
        """
        if not isinstance(records, list):
            records = [records]

        self.fill_record_dummy_info(records)
        self.fill_record_hrns(records)
        self.fill_record_sfa_info(records)
        return records

    def fill_record_dummy_info(self, records):
        """
        Fill in the DUMMY specific fields of a SFA record. This
        involves calling the appropriate DUMMY method to retrieve the 
        database record for the object.
            
        @param record: record to fill in field (in/out param)     
        """
        # get ids by type
        node_ids, slice_ids, user_ids = [], [], [] 
        type_map = {'node': node_ids, 'slice': slice_ids, 'user': user_ids}
                  
        for record in records:
            for type in type_map:
                if type == record['type']:
                    type_map[type].append(record['pointer'])

        # get dummy records
        nodes, slices, users = {}, {}, {}
        if node_ids:
            node_list = self.shell.GetNodes({'node_ids':node_ids})
            nodes = list_to_dict(node_list, 'node_id')
        if slice_ids:
            slice_list = self.shell.GetSlices({'slice_ids':slice_ids})
            slices = list_to_dict(slice_list, 'slice_id')
        if user_ids:
            user_list = self.shell.GetUsers({'user_ids': user_ids})
            users = list_to_dict(user_list, 'user_id')

        dummy_records = {'node': nodes, 'slice': slices, 'user': users}


        # fill record info
        for record in records:
            # records with pointer==-1 do not have dummy info.
            if record['pointer'] == -1:
                continue
           
            for type in dummy_records:
                if record['type'] == type:
                    if record['pointer'] in dummy_records[type]:
                        record.update(dummy_records[type][record['pointer']])
                        break
            # fill in key info
            if record['type'] == 'user':
                record['key_ids'] = []
                recors['keys'] = []
                for key in dummy_records['user'][record['pointer']]['keys']:
                     record['key_ids'].append(-1)
                     recors['keys'].append(key)

        return records

    def fill_record_hrns(self, records):
        """
        convert dummy ids to hrns
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

        # get dummy records
        slices, users, nodes = {}, {}, {}
        if user_ids:
            user_list = self.shell.GetUsers({'user_ids': user_ids})
            users = list_to_dict(user_list, 'user_id')
        if slice_ids:
            slice_list = self.shell.GetSlices({'slice_ids': slice_ids})
            slices = list_to_dict(slice_list, 'slice_id')       
        if node_ids:
            node_list = self.shell.GetNodes({'node_ids': node_ids})
            nodes = list_to_dict(node_list, 'node_id')
       
        # convert ids to hrns
        for record in records:
            # get all relevant data
            type = record['type']
            pointer = record['pointer']
            testbed_name = self.testbed_name()
            auth_hrn = self.hrn
            if pointer == -1:
                continue

            if 'user_ids' in record:
                emails = [users[user_id]['email'] for user_id in record['user_ids'] \
                          if user_id in  users]
                usernames = [email.split('@')[0] for email in emails]
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

            
        return records   

    def fill_record_sfa_info(self, records):

        def startswith(prefix, values):
            return [value for value in values if value.startswith(prefix)]

        # get user ids
        user_ids = []
        for record in records:
            user_ids.extend(record.get("user_ids", []))
        
        # get sfa records for all records associated with these records.   
        # we'll replace pl ids (person_ids) with hrns from the sfa records
        # we obtain
        
        # get the registry records
        user_list, users = [], {}
        user_list = dbsession.query (RegRecord).filter(RegRecord.pointer.in_(user_ids))
        # create a hrns keyed on the sfa record's pointer.
        # Its possible for multiple records to have the same pointer so
        # the dict's value will be a list of hrns.
        users = defaultdict(list)
        for user in user_list:
            users[user.pointer].append(user)

        # get the dummy records
        dummy_user_list, dummy_users = [], {}
        dummy_user_list = self.shell.GetUsers({'user_ids': user_ids})
        dummy_users = list_to_dict(dummy_user_list, 'user_id')

        # fill sfa info
        for record in records:
            # skip records with no pl info (top level authorities)
            #if record['pointer'] == -1:
            #    continue 
            sfa_info = {}
            type = record['type']
            logger.info("fill_record_sfa_info - incoming record typed %s"%type)
            if (type == "slice"):
                # all slice users are researchers
                record['geni_urn'] = hrn_to_urn(record['hrn'], 'slice')
                record['PI'] = []
                record['researcher'] = []
                for user_id in record.get('user_ids', []):
                    hrns = [user.hrn for user in users[user_id]]
                    record['researcher'].extend(hrns)                

            elif (type.startswith("authority")):
                record['url'] = None
                logger.info("fill_record_sfa_info - authority xherex")

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
        # hard-wire the code for slice/user for now, could be smarter if needed
        if subject_type =='slice' and target_type == 'user' and relation_name == 'researcher':
            subject=self.shell.GetSlices ({'slice_id': subject_id})[0]
            if 'user_ids' not in subject.keys():
                 subject['user_ids'] = []
            current_target_ids = subject['user_ids']
            add_target_ids = list ( set (target_ids).difference(current_target_ids))
            del_target_ids = list ( set (current_target_ids).difference(target_ids))
            logger.debug ("subject_id = %s (type=%s)"%(subject_id,type(subject_id)))
            for target_id in add_target_ids:
                self.shell.AddUserToSlice ({'user_id': target_id, 'slice_id': subject_id})
                logger.debug ("add_target_id = %s (type=%s)"%(target_id,type(target_id)))
            for target_id in del_target_ids:
                logger.debug ("del_target_id = %s (type=%s)"%(target_id,type(target_id)))
                self.shell.DeleteUserFromSlice ({'user_id': target_id, 'slice_id': subject_id})
        else:
            logger.info('unexpected relation %s to maintain, %s -> %s'%(relation_name,subject_type,target_type))

        
    ########################################
    ########## aggregate oriented
    ########################################

    def testbed_name (self): return "dummy"

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
    
        slices = self.shell.GetSlices()
        slice_hrns = [slicename_to_hrn(self.hrn, slice['slice_name']) for slice in slices]
        slice_urns = [hrn_to_urn(slice_hrn, 'slice') for slice_hrn in slice_hrns]
    
        return slice_urns
        
    # first 2 args are None in case of resource discovery
    def list_resources (self, slice_urn, slice_hrn, creds, options):
    
        version_manager = VersionManager()
        # get the rspec's return format from options
        rspec_version = version_manager.get_version(options.get('geni_rspec_version'))
        version_string = "rspec_%s" % (rspec_version)
    
        aggregate = DummyAggregate(self)
        rspec =  aggregate.get_rspec(slice_xrn=slice_urn, version=rspec_version, 
                                     options=options)
    
        return rspec
    
    def sliver_status (self, slice_urn, slice_hrn):
        # find out where this slice is currently running
        slice_name = hrn_to_dummy_slicename(slice_hrn)
        
        slice = self.shell.GetSlices({'slice_name': slice_name})
        if len(slices) == 0:        
            raise SliverDoesNotExist("%s (used %s as slicename internally)" % (slice_hrn, slicename))
        
        # report about the local nodes only
        nodes = self.shell.GetNodes({'node_ids':slice['node_ids']})

        if len(nodes) == 0:
            raise SliverDoesNotExist("You have not allocated any slivers here") 

        # get login info
        user = {}
        keys = []
        if slice['user_ids']:
            users = self.shell.GetUsers({'user_ids': slice['user_ids']})
            for user in users:
                 keys.extend(user['keys'])

            user.update({'urn': slice_urn,
                         'login': slice['slice_name'],
                         'protocol': ['ssh'],
                         'port': ['22'],
                         'keys': keys})

    
        result = {}
        top_level_status = 'unknown'
        if nodes:
            top_level_status = 'ready'
        result['geni_urn'] = slice_urn
        result['dummy_login'] = slice['slice_name']
        result['dummy_expires'] = datetime_to_string(utcparse(slice['expires']))
        result['geni_expires'] = datetime_to_string(utcparse(slice['expires']))
        
        resources = []
        for node in nodes:
            res = {}
            res['dummy_hostname'] = node['hostname']
            res['geni_expires'] = datetime_to_string(utcparse(slice['expires']))
            sliver_id = Xrn(slice_urn, type='slice', id=node['node_id'], authority=self.hrn).urn
            res['geni_urn'] = sliver_id
            res['geni_status'] = 'ready'
            res['geni_error'] = ''
            res['users'] = [users]  
    
            resources.append(res)
            
        result['geni_status'] = top_level_status
        result['geni_resources'] = resources
        return result

    def create_sliver (self, slice_urn, slice_hrn, creds, rspec_string, users, options):

        aggregate = DummyAggregate(self)
        slices = DummySlices(self)
        sfa_peer = slices.get_sfa_peer(slice_hrn)
        slice_record=None    
        if users:
            slice_record = users[0].get('slice_record', {})
    
        # parse rspec
        rspec = RSpec(rspec_string)
        requested_attributes = rspec.version.get_slice_attributes()
        
        # ensure slice record exists
        slice = slices.verify_slice(slice_hrn, slice_record, peer, sfa_peer, options=options)
        # ensure user records exists
        users = slices.verify_users(slice_hrn, slice, users, peer, sfa_peer, options=options)
        
        # add/remove slice from nodes
        requested_slivers = []
        for node in rspec.version.get_nodes_with_slivers():
            hostname = None
            if node.get('component_name'):
                hostname = node.get('component_name').strip()
            elif node.get('component_id'):
                hostname = xrn_to_hostname(node.get('component_id').strip())
            if hostname:
                requested_slivers.append(hostname)
        nodes = slices.verify_slice_nodes(slice, requested_slivers, peer) 
    
        return aggregate.get_rspec(slice_xrn=slice_urn, version=rspec.version)

    def delete_sliver (self, slice_urn, slice_hrn, creds, options):
        slicename = hrn_to_dummy_slicename(slice_hrn)
        slices = self.shell.GetSlices({'slice_name': slicename})
        if not slices:
            return True
        slice = slices[0]
        
        try:
            self.shell.DeleteSliceFromNodes({'slice_id': slice['slice_id'], 'node_ids': slice['node_ids']})
            return True
        except:
            return False
    
    def renew_sliver (self, slice_urn, slice_hrn, creds, expiration_time, options):
        slicename = hrn_to_dummy_slicename(slice_hrn)
        slices = self.shell.GetSlices({'slice_name': slicename})
        if not slices:
            raise RecordNotFound(slice_hrn)
        slice = slices[0]
        requested_time = utcparse(expiration_time)
        record = {'expires': int(datetime_to_epoch(requested_time))}
        try:
            self.shell.UpdateSlice({'slice_id': slice['slice_id'], 'fields':record})
            return True
        except:
            return False

    # set the 'enabled' tag to True
    def start_slice (self, slice_urn, slice_hrn, creds):
        slicename = hrn_to_dummy_slicename(slice_hrn)
        slices = self.shell.GetSlices({'slice_name': slicename})
        if not slices:
            raise RecordNotFound(slice_hrn)
        slice_id = slices[0]['slice_id']
        slice_enabled = slices[0]['enabled'] 
        # just update the slice enabled tag
        if not slice_enabled:
            self.shell.UpdateSlice({'slice_id': slice_id, 'fields': {'enabled': True}})
        return 1

    # set the 'enabled' tag to False
    def stop_slice (self, slice_urn, slice_hrn, creds):
        slicename = hrn_to_pl_slicename(slice_hrn)
        slices = self.shell.GetSlices({'slice_name': slicename})
        if not slices:
            raise RecordNotFound(slice_hrn)
        slice_id = slices[0]['slice_id']
        slice_enabled = slices[0]['enabled']
        # just update the slice enabled tag
        if slice_enabled:
            self.shell.UpdateSlice({'slice_id': slice_id, 'fields': {'enabled': False}})
        return 1
    
    def reset_slice (self, slice_urn, slice_hrn, creds):
        raise SfaNotImplemented ("reset_slice not available at this interface")
    
    def get_ticket (self, slice_urn, slice_hrn, creds, rspec_string, options):
        raise SfaNotImplemented,"DummyDriver.get_ticket needs a rewrite"
