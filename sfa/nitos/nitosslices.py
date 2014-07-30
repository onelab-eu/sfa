from types import StringTypes
from collections import defaultdict

from sfa.util.sfatime import utcparse, datetime_to_epoch
from sfa.util.sfalogging import logger
from sfa.util.xrn import Xrn, get_leaf, get_authority, urn_to_hrn

from sfa.rspecs.rspec import RSpec

from sfa.nitos.nitosxrn import NitosXrn, hrn_to_nitos_slicename, xrn_to_hostname, xrn_to_channel

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
             channel_num = xrn_to_channel(channel['component_id'])
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

                        
        
    def verify_slice(self, slice_hrn, slice_record, sfa_peer, options=None):
        if options is None: options={}
        slicename = hrn_to_nitos_slicename(slice_hrn)
        slices = self.driver.shell.getSlices({}, []) 
        slices = self.driver.filter_nitos_results(slices, {'slice_name': slicename})
        if not slices:
            slice = {'slice_name': slicename}
            # add the slice                          
            slice['slice_id'] = self.driver.shell.addSlice(slice)
            slice['node_ids'] = []
            slice['user_ids'] = []
        else:
            slice = slices[0]
       
        return slice

    def verify_users(self, slice_hrn, slice_record, users, sfa_peer, options=None):
        if options is None: options={}
        # get slice info
        slicename = hrn_to_nitos_slicename(slice_hrn)
        slices = self.driver.shell.getSlices({}, [])
        slice = self.driver.filter_nitos_results(slices, {'slice_name': slicename})[0]
        added_users = []
        #get users info
        users_info = []
        for user in users:
             user_urn = user['urn']
             user_hrn, type = urn_to_hrn(user_urn)
             username = str(user_hrn).split('.')[-1]
             email = user['email']
             # look for the user according to his username, email...
             nitos_users = self.driver.filter_nitos_results(self.driver.shell.getUsers(), {'username': username})
             if not nitos_users:
                 nitos_users = self.driver.filter_nitos_results(self.driver.shell.getUsers(), {'email': email})

             if not nitos_users:
                 # create the user
                 user_id = self.driver.shell.addUser({'username': email.split('@')[0], 'email': email})
                 added_users.append(user_id)
                 # add user keys
                 for key in user['keys']:
                      self.driver.shell.addUserKey({'user_id': user_id, 'key': key, 'slice_id': slice['slice_id']})
                 # add the user to the slice
                 self.driver.shell.addUserToSlice({'slice_id': slice['slice_id'], 'user_id': user_id})
             else:
                 # check if the users are in the slice
                 for user in nitos_users:
                      if not user['user_id'] in slice['user_ids']:
                          self.driver.shell.addUserToSlice({'slice_id': slice['slice_id'], 'user_id': user['user_id']})

        return added_users


    def verify_keys(self, persons, users, options=None):
        if options is None: options={}
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


