from types import StringTypes
from collections import defaultdict

from sfa.util.sfatime import utcparse, datetime_to_epoch
from sfa.util.sfalogging import logger
from sfa.util.xrn import Xrn, get_leaf, get_authority, urn_to_hrn

from sfa.rspecs.rspec import RSpec

from sfa.planetlab.vlink import VLink
from sfa.planetlab.plxrn import PlXrn, hrn_to_pl_slicename

MAXINT =  2L**31-1

class PlSlices:

    rspec_to_slice_tag = {'max_rate':'net_max_rate'}

    def __init__(self, driver):
        self.driver = driver

    def get_slivers(self, xrn, node=None):
        hrn, type = urn_to_hrn(xrn)
         
        slice_name = hrn_to_pl_slicename(hrn)
        # XX Should we just call PLCAPI.GetSliceTicket(slice_name) instead
        # of doing all of this?
        #return self.driver.shell.GetSliceTicket(self.auth, slice_name) 
        
        # from PLCAPI.GetSlivers.get_slivers()
        slice_fields = ['slice_id', 'name', 'instantiation', 'expires', 'person_ids', 'slice_tag_ids']
        slices = self.driver.shell.GetSlices(slice_name, slice_fields)
        # Build up list of users and slice attributes
        person_ids = set()
        all_slice_tag_ids = set()
        for slice in slices:
            person_ids.update(slice['person_ids'])
            all_slice_tag_ids.update(slice['slice_tag_ids'])
        person_ids = list(person_ids)
        all_slice_tag_ids = list(all_slice_tag_ids)
        # Get user information
        all_persons_list = self.driver.shell.GetPersons({'person_id':person_ids,'enabled':True}, ['person_id', 'enabled', 'key_ids'])
        all_persons = {}
        for person in all_persons_list:
            all_persons[person['person_id']] = person        

        # Build up list of keys
        key_ids = set()
        for person in all_persons.values():
            key_ids.update(person['key_ids'])
        key_ids = list(key_ids)
        # Get user account keys
        all_keys_list = self.driver.shell.GetKeys(key_ids, ['key_id', 'key', 'key_type'])
        all_keys = {}
        for key in all_keys_list:
            all_keys[key['key_id']] = key
        # Get slice attributes
        all_slice_tags_list = self.driver.shell.GetSliceTags(all_slice_tag_ids)
        all_slice_tags = {}
        for slice_tag in all_slice_tags_list:
            all_slice_tags[slice_tag['slice_tag_id']] = slice_tag
           
        slivers = []
        for slice in slices:
            keys = []
            for person_id in slice['person_ids']:
                if person_id in all_persons:
                    person = all_persons[person_id]
                    if not person['enabled']:
                        continue
                    for key_id in person['key_ids']:
                        if key_id in all_keys:
                            key = all_keys[key_id]
                            keys += [{'key_type': key['key_type'],
                                    'key': key['key']}]
            attributes = []
            # All (per-node and global) attributes for this slice
            slice_tags = []
            for slice_tag_id in slice['slice_tag_ids']:
                if slice_tag_id in all_slice_tags:
                    slice_tags.append(all_slice_tags[slice_tag_id]) 
            # Per-node sliver attributes take precedence over global
            # slice attributes, so set them first.
            # Then comes nodegroup slice attributes
            # Followed by global slice attributes
            sliver_attributes = []

            if node is not None:
                for sliver_attribute in filter(lambda a: a['node_id'] == node['node_id'], slice_tags):
                    sliver_attributes.append(sliver_attribute['tagname'])
                    attributes.append({'tagname': sliver_attribute['tagname'],
                                    'value': sliver_attribute['value']})

            # set nodegroup slice attributes
            for slice_tag in filter(lambda a: a['nodegroup_id'] in node['nodegroup_ids'], slice_tags):
                # Do not set any nodegroup slice attributes for
                # which there is at least one sliver attribute
                # already set.
                if slice_tag not in slice_tags:
                    attributes.append({'tagname': slice_tag['tagname'],
                        'value': slice_tag['value']})

            for slice_tag in filter(lambda a: a['node_id'] is None, slice_tags):
                # Do not set any global slice attributes for
                # which there is at least one sliver attribute
                # already set.
                if slice_tag['tagname'] not in sliver_attributes:
                    attributes.append({'tagname': slice_tag['tagname'],
                                   'value': slice_tag['value']})

            # XXX Sanity check; though technically this should be a system invariant
            # checked with an assertion
            if slice['expires'] > MAXINT:  slice['expires']= MAXINT
            
            slivers.append({
                'hrn': hrn,
                'name': slice['name'],
                'slice_id': slice['slice_id'],
                'instantiation': slice['instantiation'],
                'expires': slice['expires'],
                'keys': keys,
                'attributes': attributes
            })

        return slivers
 
    def get_peer(self, xrn):
        hrn, type = urn_to_hrn(xrn)
        # Becaues of myplc federation,  we first need to determine if this
        # slice belongs to out local plc or a myplc peer. We will assume it 
        # is a local site, unless we find out otherwise  
        peer = None

        # get this slice's authority (site)
        slice_authority = get_authority(hrn)

        # get this site's authority (sfa root authority or sub authority)
        site_authority = get_authority(slice_authority).lower()

        # check if we are already peered with this site_authority, if so
        peers = self.driver.shell.GetPeers({}, ['peer_id', 'peername', 'shortname', 'hrn_root'])
        for peer_record in peers:
            names = [name.lower() for name in peer_record.values() if isinstance(name, StringTypes)]
            if site_authority in names:
                peer = peer_record

        return peer

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
        
        nodes = self.driver.shell.GetNodes(slice['node_ids'], ['node_id', 'hostname', 'interface_ids'])
        current_slivers = [node['hostname'] for node in nodes]

        # remove nodes not in rspec
        deleted_nodes = list(set(current_slivers).difference(requested_slivers))

        # add nodes from rspec
        added_nodes = list(set(requested_slivers).difference(current_slivers))        

        try:
            if peer:
                self.driver.shell.UnBindObjectFromPeer('slice', slice['slice_id'], peer['shortname'])
            self.driver.shell.AddSliceToNodes(slice['name'], added_nodes)
            self.driver.shell.DeleteSliceFromNodes(slice['name'], deleted_nodes)

        except: 
            logger.log_exc('Failed to add/remove slice from nodes')
        return nodes

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

    def verify_slice_links(self, slice, requested_links, nodes):
        # nodes is undefined here
        if not requested_links:
            return
   
        # build dict of nodes 
        nodes_dict = {}
        interface_ids = []
        for node in nodes:
            nodes_dict[node['node_id']] = node
            interface_ids.extend(node['interface_ids'])
        # build dict of interfaces
        interfaces = self.driver.shell.GetInterfaces(interface_ids)
        interfaces_dict = {}
        for interface in interfaces:
            interfaces_dict[interface['interface_id']] = interface 

        slice_tags = []
        
        # set egre key
        slice_tags.append({'name': 'egre_key', 'value': self.free_egre_key()})
    
        # set netns
        slice_tags.append({'name': 'netns', 'value': '1'})

        # set cap_net_admin 
        # need to update the attribute string?
        slice_tags.append({'name': 'capabilities', 'value': 'CAP_NET_ADMIN'}) 
        
        for link in requested_links:
            # get the ip address of the first node in the link
            ifname1 = Xrn(link['interface1']['component_id']).get_leaf()
            (node_raw, device) = ifname1.split(':')
            node_id = int(node_raw.replace('node', ''))
            node = nodes_dict[node_id]
            if1 = interfaces_dict[node['interface_ids'][0]]
            ipaddr = if1['ip']
            topo_rspec = VLink.get_topo_rspec(link, ipaddr)
            # set topo_rspec tag
            slice_tags.append({'name': 'topo_rspec', 'value': str([topo_rspec]), 'node_id': node_id})
            # set vini_topo tag
            slice_tags.append({'name': 'vini_topo', 'value': 'manual', 'node_id': node_id})
            #self.driver.shell.AddSliceTag(slice['name'], 'topo_rspec', str([topo_rspec]), node_id) 

        self.verify_slice_attributes(slice, slice_tags, {'append': True}, admin=True)
                        
        

    def handle_peer(self, site, slice, persons, peer):
        if peer:
            # bind site
            try:
                if site:
                    self.driver.shell.BindObjectToPeer('site', site['site_id'], peer['shortname'], slice['site_id'])
            except Exception,e:
                self.driver.shell.DeleteSite(site['site_id'])
                raise e
            
            # bind slice
            try:
                if slice:
                    self.driver.shell.BindObjectToPeer('slice', slice['slice_id'], peer['shortname'], slice['slice_id'])
            except Exception,e:
                self.driver.shell.DeleteSlice(slice['slice_id'])
                raise e 

            # bind persons
            for person in persons:
                try:
                    self.driver.shell.BindObjectToPeer('person', 
                                                     person['person_id'], peer['shortname'], person['peer_person_id'])

                    for (key, remote_key_id) in zip(person['keys'], person['key_ids']):
                        try:
                            self.driver.shell.BindObjectToPeer( 'key', key['key_id'], peer['shortname'], remote_key_id)
                        except:
                            self.driver.shell.DeleteKey(key['key_id'])
                            logger("failed to bind key: %s to peer: %s " % (key['key_id'], peer['shortname']))
                except Exception,e:
                    self.driver.shell.DeletePerson(person['person_id'])
                    raise e       

        return slice

    def verify_site(self, slice_xrn, slice_record={}, peer=None, sfa_peer=None, options={}):
        (slice_hrn, type) = urn_to_hrn(slice_xrn)
        site_hrn = get_authority(slice_hrn)
        # login base can't be longer than 20 characters
        slicename = hrn_to_pl_slicename(slice_hrn)
        authority_name = slicename.split('_')[0]
        login_base = authority_name[:20]
        sites = self.driver.shell.GetSites(login_base)
        if not sites:
            # create new site record
            site = {'name': 'geni.%s' % authority_name,
                    'abbreviated_name': authority_name,
                    'login_base': login_base,
                    'max_slices': 100,
                    'max_slivers': 1000,
                    'enabled': True,
                    'peer_site_id': None}
            if peer:
                site['peer_site_id'] = slice_record.get('site_id', None)
            site['site_id'] = self.driver.shell.AddSite(site)
            # exempt federated sites from monitor policies
            self.driver.shell.AddSiteTag(site['site_id'], 'exempt_site_until', "20200101")
            
#            # is this still necessary?
#            # add record to the local registry 
#            if sfa_peer and slice_record:
#                peer_dict = {'type': 'authority', 'hrn': site_hrn, \
#                             'peer_authority': sfa_peer, 'pointer': site['site_id']}
#                self.registry.register_peer_object(self.credential, peer_dict)
        else:
            site =  sites[0]
            if peer:
                # unbind from peer so we can modify if necessary. Will bind back later
                self.driver.shell.UnBindObjectFromPeer('site', site['site_id'], peer['shortname']) 
        
        return site        

    def verify_slice(self, slice_hrn, slice_record, peer, sfa_peer, options={}):
        slicename = hrn_to_pl_slicename(slice_hrn)
        parts = slicename.split("_")
        login_base = parts[0]
        slices = self.driver.shell.GetSlices([slicename]) 
        if not slices:
            slice = {'name': slicename,
                     'url': slice_record.get('url', slice_hrn), 
                     'description': slice_record.get('description', slice_hrn)}
            # add the slice                          
            slice['slice_id'] = self.driver.shell.AddSlice(slice)
            slice['node_ids'] = []
            slice['person_ids'] = []
            if peer:
                slice['peer_slice_id'] = slice_record.get('slice_id', None) 
            # mark this slice as an sfa peer record
#            if sfa_peer:
#                peer_dict = {'type': 'slice', 'hrn': slice_hrn, 
#                             'peer_authority': sfa_peer, 'pointer': slice['slice_id']}
#                self.registry.register_peer_object(self.credential, peer_dict)
        else:
            slice = slices[0]
            if peer:
                slice['peer_slice_id'] = slice_record.get('slice_id', None)
                # unbind from peer so we can modify if necessary. Will bind back later
                self.driver.shell.UnBindObjectFromPeer('slice', slice['slice_id'], peer['shortname'])
	        #Update existing record (e.g. expires field) it with the latest info.
            if slice_record.get('expires'):
                requested_expires = int(datetime_to_epoch(utcparse(slice_record['expires'])))
                if requested_expires and slice['expires'] != requested_expires:
                    self.driver.shell.UpdateSlice( slice['slice_id'], {'expires' : requested_expires})
       
        return slice

    #def get_existing_persons(self, users):
    def verify_persons(self, slice_hrn, slice_record, users, peer, sfa_peer, options={}):
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
            

    def verify_keys(self, persons, users, peer, options={}):
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

    def verify_slice_attributes(self, slice, requested_slice_attributes, options={}, admin=False):
        append = options.get('append', True)
        # get list of attributes users ar able to manage
        filter = {'category': '*slice*'}
        if not admin:
            filter['|roles'] = ['user']
        slice_attributes = self.driver.shell.GetTagTypes(filter)
        valid_slice_attribute_names = [attribute['tagname'] for attribute in slice_attributes]

        # get sliver attributes
        added_slice_attributes = []
        removed_slice_attributes = []
        ignored_slice_attribute_names = []
        existing_slice_attributes = self.driver.shell.GetSliceTags({'slice_id': slice['slice_id']})
        
        # get attributes that should be removed
        for slice_tag in existing_slice_attributes:
            if slice_tag['tagname'] in ignored_slice_attribute_names:
                # If a slice already has a admin only role it was probably given to them by an
                # admin, so we should ignore it.
                ignored_slice_attribute_names.append(slice_tag['tagname'])
            else:
                # If an existing slice attribute was not found in the request it should
                # be removed
                attribute_found=False
                for requested_attribute in requested_slice_attributes:
                    if requested_attribute['name'] == slice_tag['tagname'] and \
                       requested_attribute['value'] == slice_tag['value']:
                        attribute_found=True
                        break

            if not attribute_found and not append:
                removed_slice_attributes.append(slice_tag)
        
        # get attributes that should be added:
        for requested_attribute in requested_slice_attributes:
            # if the requested attribute wasn't found  we should add it
            if requested_attribute['name'] in valid_slice_attribute_names:
                attribute_found = False
                for existing_attribute in existing_slice_attributes:
                    if requested_attribute['name'] == existing_attribute['tagname'] and \
                       requested_attribute['value'] == existing_attribute['value']:
                        attribute_found=True
                        break
                if not attribute_found:
                    added_slice_attributes.append(requested_attribute)


        # remove stale attributes
        for attribute in removed_slice_attributes:
            try:
                self.driver.shell.DeleteSliceTag(attribute['slice_tag_id'])
            except Exception, e:
                logger.warn('Failed to remove sliver attribute. name: %s, value: %s, node_id: %s\nCause:%s'\
                                % (slice['name'], attribute['value'],  attribute.get('node_id'), str(e)))

        # add requested_attributes
        for attribute in added_slice_attributes:
            try:
                self.driver.shell.AddSliceTag(slice['name'], attribute['name'], attribute['value'], attribute.get('node_id', None))
            except Exception, e:
                logger.warn('Failed to add sliver attribute. name: %s, value: %s, node_id: %s\nCause:%s'\
                                % (slice['name'], attribute['value'],  attribute.get('node_id'), str(e)))

