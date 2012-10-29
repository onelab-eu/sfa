from types import StringTypes
from collections import defaultdict

from sfa.util.sfatime import utcparse, datetime_to_epoch
from sfa.util.sfalogging import logger
from sfa.util.xrn import Xrn, get_leaf, get_authority, urn_to_hrn

from sfa.rspecs.rspec import RSpec

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
 
    def get_sfa_peer(self, xrn):
        hrn, type = urn_to_hrn(xrn)

        # return the authority for this hrn or None if we are the authority
        sfa_peer = None
        slice_authority = get_authority(hrn)
        site_authority = get_authority(slice_authority)

        if site_authority != self.driver.hrn:
            sfa_peer = site_authority

        return sfa_peer


    def verify_slice_nodes(self, slice, requested_slivers, peer):
        
        nodes = self.driver.shell.GetNodes({'node_ids': slice['node_ids']})
        current_slivers = [node['hostname'] for node in nodes]

        # remove nodes not in rspec
        deleted_nodes = list(set(current_slivers).difference(requested_slivers))

        # add nodes from rspec
        added_nodes = list(set(requested_slivers).difference(current_slivers))        

        try:
            self.driver.shell.AddSliceToNodes({'slice_id': slice['slice_id'], 'node_ids': added_nodes})
            self.driver.shell.DeleteSliceFromNodes({'slice_id': slice['slice_id'], 'node_ids': deleted_nodes})

        except: 
            logger.log_exc('Failed to add/remove slice from nodes')
        return nodes

        

    def verify_slice(self, slice_hrn, slice_record, peer, sfa_peer, options={}):
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
            if slice_record.get('expires'):
                requested_expires = int(datetime_to_epoch(utcparse(slice_record['expires'])))
                if requested_expires and slice['expires'] != requested_expires:
                    self.driver.shell.UpdateSlice( {'slice_id': slice['slice_id'], 'fields':{'expires' : requested_expires}})
       
        return slice

    def verify_users(self, slice_hrn, slice_record, users, peer, sfa_peer, options={}):
        users_by_email = {}
        users_dict = {} 
        for user in users:
            user['urn'] = user['urn'].lower()
            hrn, type = urn_to_hrn(user['urn'])
            username = get_leaf(hrn)
            login_base = PlXrn(xrn=user['urn']).pl_login_base()
            user['username'] = username
            user['site'] = login_base

            if 'email' in user:
                user['email'] = user['email'].lower() 
                users_by_email[user['email']] = user
                users_dict[user['email']] = user
            else:
                users_by_site[user['site']].append(user)

        # start building a list of existing users
        existing_user_ids = []
        existing_user_ids_filter = []
        if users_by_email:
            existing_user_ids_filter.extend(users_by_email.keys())
        if users_by_site:
            for login_base in users_by_site:
                users = users_by_site[login_base]
                for user in users:	
                    existing_user_ids_filter.append(user['username']+'@geni.net')		
        if existing_user_ids_filter:			
            # get existing users by email 
            existing_users = self.driver.shell.GetPersons({'email': existing_user_ids_filter}, 
                                                        ['person_id', 'key_ids', 'email'])
            existing_user_ids.extend([user['email'] for user in existing_users])
	
        if users_by_site:
            # get a list of user sites (based on requeste user urns
            site_list = self.driver.shell.GetSites(users_by_site.keys(), \
                ['site_id', 'login_base', 'person_ids'])
            # get all existing users at these sites
            sites = {}
            site_user_ids = []
            for site in site_list:
                sites[site['site_id']] = site
                site_user_ids.extend(site['person_ids'])

            existing_site_persons_list = self.driver.shell.GetPersons(site_user_ids,  
                                                                    ['person_id', 'key_ids', 'email', 'site_ids'])

            # all requested users are either existing users or new (added) users      
            for login_base in users_by_site:
                requested_site_users = users_by_site[login_base]
                for requested_user in requested_site_users:
                    user_found = False
                    for existing_user in existing_site_persons_list:
                        for site_id in existing_user['site_ids']:
                            if site_id in sites:
                                site = sites[site_id]
                                if login_base == site['login_base'] and \
                                   existing_user['email'].startswith(requested_user['username']+'@'):
                                    existing_user_ids.append(existing_user['email'])
                                    requested_user['email'] = existing_user['email']
                                    users_dict[existing_user['email']] = requested_user
                                    user_found = True
                                    break
                        if user_found:
                            break
      
                    if user_found == False:
                        fake_email = requested_user['username'] + '@geni.net'
                        requested_user['email'] = fake_email
                        users_dict[fake_email] = requested_user
                
        # requested slice users        
        requested_user_ids = users_dict.keys()
        # existing slice users
        existing_slice_users_filter = {'person_id': slice_record.get('person_ids', [])}
        existing_slice_users = self.driver.shell.GetPersons(existing_slice_users_filter,
                                                          ['person_id', 'key_ids', 'email'])
        existing_slice_user_ids = [user['email'] for user in existing_slice_users]
        
        # users to be added, removed or updated
        added_user_ids = set(requested_user_ids).difference(existing_user_ids)
        added_slice_user_ids = set(requested_user_ids).difference(existing_slice_user_ids)
        removed_user_ids = set(existing_slice_user_ids).difference(requested_user_ids)
        updated_user_ids = set(existing_slice_user_ids).intersection(requested_user_ids)

        # Remove stale users (only if we are not appending).
        # Append by default.
        append = options.get('append', True)
        if append == False:
            for removed_user_id in removed_user_ids:
                self.driver.shell.DeletePersonFromSlice(removed_user_id, slice_record['name'])
        # update_existing users
        updated_users_list = [user for user in users_dict.values() if user['email'] in \
          updated_user_ids]
        self.verify_keys(existing_slice_users, updated_users_list, peer, options)

        added_persons = []
        # add new users
        for added_user_id in added_user_ids:
            added_user = users_dict[added_user_id]
            hrn, type = urn_to_hrn(added_user['urn'])  
            person = {
                'first_name': added_user.get('first_name', hrn),
                'last_name': added_user.get('last_name', hrn),
                'email': added_user_id,
                'peer_person_id': None,
                'keys': [],
                'key_ids': added_user.get('key_ids', []),
            }
            person['person_id'] = self.driver.shell.AddPerson(person)
            if peer:
                person['peer_person_id'] = added_user['person_id']
            added_persons.append(person)
           
            # enable the account 
            self.driver.shell.UpdatePerson(person['person_id'], {'enabled': True})
            
            # add person to site
            self.driver.shell.AddPersonToSite(added_user_id, added_user['site'])

            for key_string in added_user.get('keys', []):
                key = {'key':key_string, 'key_type':'ssh'}
                key['key_id'] = self.driver.shell.AddPersonKey(person['person_id'], key)
                person['keys'].append(key)

            # add the registry record
#            if sfa_peer:
#                peer_dict = {'type': 'user', 'hrn': hrn, 'peer_authority': sfa_peer, \
#                    'pointer': person['person_id']}
#                self.registry.register_peer_object(self.credential, peer_dict)
    
        for added_slice_user_id in added_slice_user_ids.union(added_user_ids):
            # add person to the slice 
            self.driver.shell.AddPersonToSlice(added_slice_user_id, slice_record['name'])
            # if this is a peer record then it should already be bound to a peer.
            # no need to return worry about it getting bound later 

        return added_persons
            

    def verify_keys(self, old_users, new_users, peer, options={}):
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


