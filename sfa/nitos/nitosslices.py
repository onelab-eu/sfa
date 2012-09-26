from types import StringTypes
from collections import defaultdict

from sfa.util.sfatime import utcparse, datetime_to_epoch
from sfa.util.sfalogging import logger
from sfa.util.xrn import Xrn, get_leaf, get_authority, urn_to_hrn

from sfa.rspecs.rspec import RSpec

from sfa.nitos.nitosxrn import NitosXrn, hrn_to_nitos_slicename, xrn_to_hostname

MAXINT =  2L**31-1

class NitosSlices:

    def __init__(self, driver):
        self.driver = driver


    def get_sfa_peer(self, xrn):
        hrn, type = urn_to_hrn(xrn)

        # return the authority for this hrn or None if we are the authority
        sfa_peer = None
        slice_authority = get_authority(hrn)
        site_authority = get_authority(slice_authority)

        if site_authority != self.driver.hrn:
            sfa_peer = site_authority

        return sfa_peer

    def verify_slice_leases_nodes(self, slice, rspec_requested_nodes):
        nodes = self.driver.shell.getNodes({}, [])
  
        requested_nodes = []
        for node in rspec_requested_nodes:
             requested_node = {}
             nitos_nodes = []
             nitos_nodes.extend(nodes)
             slice_name = hrn_to_nitos_slicename(node['slice_id'])
             if slice_name != slice['slice_name']:
                 continue
             hostname = xrn_to_hostname(node['component_id'])
             nitos_node = self.driver.filter_nitos_results(nitos_nodes, {'hostname': hostname})
             if not nitos_node:
                 continue
             nitos_node = nitos_node[0]
             # fill the requested node with nitos ids
             requested_node['slice_id'] = slice['slice_id']
             requested_node['node_id'] = nitos_node['node_id']
             requested_node['start_time'] = node['start_time']
             requested_node['end_time'] = str(int(node['duration']) * int(self.driver.testbedInfo['grain']) + int(node['start_time']))
             requested_nodes.append(requested_node)

        # get actual nodes reservation data for the slice
        reserved_nodes = self.driver.filter_nitos_results(self.driver.shell.getReservedNodes({}, []), {'slice_id': slice['slice_id']})
         
        reserved_nodes_by_id = {}
        for node in reserved_nodes:
             reserved_nodes_by_id[node['reservation_id']] = {'slice_id': node['slice_id'], \
                                      'node_id': node['node_id'], 'start_time': node['start_time'], \
                                      'end_time': node['end_time']}

        added_nodes = []
        kept_nodes_id = []
        deleted_nodes_id = []
        for reservation_id in reserved_nodes_by_id:
             if reserved_nodes_by_id[reservation_id] not in requested_nodes:
                 deleted_nodes_id.append(reservation_id)
             else:
                 kept_nodes_id.append(reservation_id)
                 requested_nodes.remove(reserved_nodes_by_id[reservation_id])
        added_nodes = requested_nodes

        print "NODES: \nAdded: %s \nDeleted: %s\nKept: %s" %(added_nodes,deleted_nodes_id,kept_nodes_id)

        try:
            deleted=self.driver.shell.releaseNodes({'reservation_ids': deleted_nodes_id})
            for node in added_nodes:
                added=self.driver.shell.reserveNodes({'slice_id': slice['slice_id'], 'start_time': node['start_time'], 'end_time': node['end_time'], 'nodes': [node['node_id']]})

        except:
            logger.log_exc('Failed to add/remove slice leases nodes')

        return added_nodes

        
    def verify_slice_leases_channels(self, slice, rspec_requested_channels):
        channels = self.driver.shell.getChannels({}, [])

        requested_channels = []
        for channel in rspec_requested_channels:
             requested_channel = {}
             nitos_channels = []
             nitos_channels.extend(channels)
             slice_name = hrn_to_nitos_slicename(channel['slice_id'])
             if slice_name != slice['slice_name']:
                 continue
             channel_num = channel['channel_num']
             nitos_channel = self.driver.filter_nitos_results(nitos_channels, {'channel': channel_num})[0]
             # fill the requested channel with nitos ids
             requested_channel['slice_id'] = slice['slice_id']
             requested_channel['channel_id'] = nitos_channel['channel_id']
             requested_channel['start_time'] = channel['start_time']
             requested_channel['end_time'] = str(int(channel['duration']) * int(self.driver.testbedInfo['grain']) + int(channel['start_time']))
             requested_channels.append(requested_channel)

        # get actual channel reservation data for the slice
        reserved_channels = self.driver.filter_nitos_results(self.driver.shell.getReservedChannels(), {'slice_id': slice['slice_id']})
        
        reserved_channels_by_id = {}
        for channel in reserved_channels:
             reserved_channels_by_id[channel['reservation_id']] = {'slice_id': channel['slice_id'], \
                                      'channel_id': channel['channel_id'], 'start_time': channel['start_time'], \
                                      'end_time': channel['end_time']}

        added_channels = []
        kept_channels_id = []
        deleted_channels_id = []
        for reservation_id in reserved_channels_by_id:
             if reserved_channels_by_id[reservation_id] not in requested_channels:
                 deleted_channels_id.append(reservation_id)
             else:
                 kept_channels_id.append(reservation_id)
                 requested_channels.remove(reserved_channels_by_id[reservation_id])
        added_channels = requested_channels

        print "CHANNELS: \nAdded: %s \nDeleted: %s\nKept: %s" %(added_channels,deleted_channels_id,kept_channels_id)
        
        try:
            deleted=self.driver.shell.releaseChannels({'reservation_ids': deleted_channels_id})
            for channel in added_channels:
                added=self.driver.shell.reserveChannels({'slice_id': slice['slice_id'], 'start_time': channel['start_time'], 'end_time': channel['end_time'], 'channels': [channel['channel_id']]})

        except:
            logger.log_exc('Failed to add/remove slice leases channels')
         
        return added_channels


    def free_egre_key(self):
        used = set()
        for tag in self.driver.shell.GetSliceTags({'tagname': 'egre_key'}):
                used.add(int(tag['value']))

        for i in range(1, 256):
            if i not in used:
                key = i
                break
        else:
            raise KeyError("No more EGRE keys available")

        return str(key)

                        
        
    def verify_slice(self, slice_hrn, slice_record, sfa_peer, options={}):
        slicename = hrn_to_nitos_slicename(slice_hrn)
        slices = self.driver.shell.getSlices({}, []) 
        slices = self.driver.filter_nitos_results(slices, {'slice_name': slicename})
        if not slices:
            slice = {'name': slicename}
            # add the slice                          
            slice['slice_id'] = self.driver.shell.addSlice(slice)
            slice['node_ids'] = []
            slice['user_ids'] = []
        else:
            slice = slices[0]
       
        return slice

    #def get_existing_persons(self, users):
    def verify_users(self, slice_hrn, slice_record, users, sfa_peer, options={}):
        
        slice_user_ids = slice_record['user_ids']
        all_users = self.driver.shell.getUsers()
        # filter slice users 
        slice_users = [user for user in all_users if user['user_id'] in slice_user_ids]

        slicename = hrn_to_nitos_slicename(slice_hrn)
        slices = self.driver.shell.getSlices({}, [])
        slices = self.driver.filter_nitos_results(slices, {'slice_name': slicename})
       
        slice_user 
        users_by_email = {}
        users_by_site = defaultdict(list)
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
            

    def verify_keys(self, persons, users, options={}):
        # existing keys 
        key_ids = []
        for person in persons:
            key_ids.extend(person['key_ids'])
        keylist = self.driver.shell.GetKeys(key_ids, ['key_id', 'key'])
        keydict = {}
        for key in keylist:
            keydict[key['key']] = key['key_id']     
        existing_keys = keydict.keys()
        persondict = {}
        for person in persons:
            persondict[person['email']] = person    
    
        # add new keys
        requested_keys = []
        updated_persons = []
        for user in users:
            user_keys = user.get('keys', [])
            updated_persons.append(user)
            for key_string in user_keys:
                requested_keys.append(key_string)
                if key_string not in existing_keys:
                    key = {'key': key_string, 'key_type': 'ssh'}
                    try:
                        if peer:
                            person = persondict[user['email']]
                            self.driver.shell.UnBindObjectFromPeer('person', person['person_id'], peer['shortname'])
                        key['key_id'] = self.driver.shell.AddPersonKey(user['email'], key)
                        if peer:
                            key_index = user_keys.index(key['key'])
                            remote_key_id = user['key_ids'][key_index]
                            self.driver.shell.BindObjectToPeer('key', key['key_id'], peer['shortname'], remote_key_id)
                            
                    finally:
                        if peer:
                            self.driver.shell.BindObjectToPeer('person', person['person_id'], peer['shortname'], user['person_id'])
        
        # remove old keys (only if we are not appending)
        append = options.get('append', True)
        if append == False: 
            removed_keys = set(existing_keys).difference(requested_keys)
            for existing_key_id in keydict:
                if keydict[existing_key_id] in removed_keys:
                    try:
                        if peer:
                            self.driver.shell.UnBindObjectFromPeer('key', existing_key_id, peer['shortname'])
                        self.driver.shell.DeleteKey(existing_key_id)
                    except:
                        pass   


