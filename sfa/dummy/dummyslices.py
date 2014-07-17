import time
from types import StringTypes
from collections import defaultdict

from sfa.util.sfatime import utcparse, datetime_to_epoch
from sfa.util.sfalogging import logger
from sfa.util.xrn import Xrn, get_leaf, get_authority, urn_to_hrn

from sfa.rspecs.rspec import RSpec
from sfa.storage.model import SliverAllocation

from sfa.dummy.dummyxrn import DummyXrn, hrn_to_dummy_slicename

MAXINT =  2L**31-1

class DummySlices:

    def __init__(self, driver):
        self.driver = driver

    def get_slivers(self, xrn, node=None):
        hrn, type = urn_to_hrn(xrn)
         
        slice_name = hrn_to_dummy_slicename(hrn)
        
        slices = self.driver.shell.GetSlices({'slice_name': slice_name})
        slice = slices[0]
        # Build up list of users and slice attributes
        user_ids = slice['user_ids']
        # Get user information
        all_users_list = self.driver.shell.GetUsers({'user_id':user_ids})
        all_users = {}
        for user in all_users_list:
            all_users[user['user_id']] = user        

        # Build up list of keys
        all_keys = set()
        for user in all_users_list:
            all_keys.extend(user['keys'])

        slivers = []
        for slice in slices:
            keys = all_keys
            # XXX Sanity check; though technically this should be a system invariant
            # checked with an assertion
            if slice['expires'] > MAXINT:  slice['expires']= MAXINT
            
            slivers.append({
                'hrn': hrn,
                'name': slice['name'],
                'slice_id': slice['slice_id'],
                'expires': slice['expires'],
                'keys': keys,
            })

        return slivers
 

    def verify_slice_nodes(self, slice_urn, slice, rspec_nodes):

        slivers = {}
        for node in rspec_nodes:
            hostname = node.get('component_name')
            client_id = node.get('client_id')
            component_id = node.get('component_id').strip()
            if hostname:
                hostname = hostname.strip()
            elif component_id:
                hostname = xrn_to_hostname(component_id)
            if hostname:
                slivers[hostname] = {'client_id': client_id, 'component_id': component_id}
        all_nodes = self.driver.shell.GetNodes()
        requested_slivers = []
        for node in all_nodes:
            if node['hostname'] in slivers.keys():
                requested_slivers.append(node['node_id'])

        if 'node_ids' not in slice.keys():
            slice['node_ids']=[] 
        nodes = self.driver.shell.GetNodes({'node_ids': slice['node_ids']})
        current_slivers = [node['node_id'] for node in nodes]

        # remove nodes not in rspec
        deleted_nodes = list(set(current_slivers).difference(requested_slivers))

        # add nodes from rspec
        added_nodes = list(set(requested_slivers).difference(current_slivers))        

        try:
            self.driver.shell.AddSliceToNodes({'slice_id': slice['slice_id'], 'node_ids': added_nodes})
            self.driver.shell.DeleteSliceFromNodes({'slice_id': slice['slice_id'], 'node_ids': deleted_nodes})

        except: 
            logger.log_exc('Failed to add/remove slice from nodes')

        slices = self.driver.shell.GetSlices({'slice_name': slice['slice_name']})
        resulting_nodes = self.driver.shell.GetNodes({'node_ids': slices[0]['node_ids']})

        # update sliver allocations
        for node in resulting_nodes:
            client_id = slivers[node['hostname']]['client_id']
            component_id = slivers[node['hostname']]['component_id']
            sliver_hrn = '%s.%s-%s' % (self.driver.hrn, slice['slice_id'], node['node_id'])
            sliver_id = Xrn(sliver_hrn, type='sliver').urn
            record = SliverAllocation(sliver_id=sliver_id, client_id=client_id,
                                      component_id=component_id,
                                      slice_urn = slice_urn,
                                      allocation_state='geni_allocated')
            record.sync(self.driver.api.dbsession())
        return resulting_nodes
        

    def verify_slice(self, slice_hrn, slice_record, expiration, options=None):
        if options is None: options={}
        slicename = hrn_to_dummy_slicename(slice_hrn)
        parts = slicename.split("_")
        login_base = parts[0]
        slices = self.driver.shell.GetSlices({'slice_name': slicename}) 
        if not slices:
            slice = {'slice_name': slicename}
            # add the slice                          
            slice['slice_id'] = self.driver.shell.AddSlice(slice)
            slice['node_ids'] = []
            slice['user_ids'] = []
        else:
            slice = slices[0]
            if slice_record and slice_record.get('expires'):
                requested_expires = int(datetime_to_epoch(utcparse(slice_record['expires'])))
                if requested_expires and slice['expires'] != requested_expires:
                    self.driver.shell.UpdateSlice( {'slice_id': slice['slice_id'], 'fields':{'expires' : expiration}})
       
        return slice

    def verify_users(self, slice_hrn, slice_record, users, options=None):
        if options is None: options={}
        slice_name = hrn_to_dummy_slicename(slice_hrn)
        users_by_email = {}
        for user in users:
            user['urn'] = user['urn'].lower()
            hrn, type = urn_to_hrn(user['urn'])
            username = get_leaf(hrn)
            user['username'] = username

            if 'email' in user:
                user['email'] = user['email'].lower() 
                users_by_email[user['email']] = user
        
        # start building a list of existing users
        existing_users_by_email = {}
        existing_slice_users_by_email = {}
        existing_users = self.driver.shell.GetUsers()
        existing_slice_users_ids = self.driver.shell.GetSlices({'slice_name': slice_name})[0]['user_ids']
        for user in existing_users:
            existing_users_by_email[user['email']] = user  
	    if user['user_id'] in existing_slice_users_ids:
                existing_slice_users_by_email[user['email']] = user
                
        add_users_by_email = set(users_by_email).difference(existing_slice_user_by_email)
        delete_users_by_email = set(existing_slice_user_by_email).difference(users_by_email)
        try:
            for user in add_users_by_email: 
                self.driver.shell.AddUser()
        except: 
            pass
            

    def verify_keys(self, old_users, new_users, options=None):
        if options is None: options={}
        # existing keys 
        existing_keys = []
        for user in old_users:
             existing_keys.append(user['keys'])
        userdict = {}
        for user in old_users:
            userdict[user['email']] = user    
    
        # add new keys
        requested_keys = []
        updated_users = []
        for user in new_users:
            user_keys = user.get('keys', [])
            updated_users.append(user)
            for key_string in user_keys:
                requested_keys.append(key_string)
                if key_string not in existing_keys:
                    key = key_string
                    try:
                        self.driver.shell.AddUserKey({'user_id': user['user_id'], 'key':key})
                            
                    except:
                        pass        
        # remove old keys (only if we are not appending)
        append = options.get('append', True)
        if append == False: 
            removed_keys = set(existing_keys).difference(requested_keys)
            for key in removed_keys:
                 try:
                     self.driver.shell.DeleteKey({'key': key})
                 except:
                     pass   

