from types import StringTypes
from collections import defaultdict

from sfa.util.xrn import get_leaf, get_authority, urn_to_hrn
from sfa.util.plxrn import hrn_to_pl_slicename
from sfa.util.policy import Policy
from sfa.rspecs.rspec import RSpec
from sfa.plc.vlink import VLink

MAXINT =  2L**31-1

class Slices:

    rspec_to_slice_tag = {'max_rate':'net_max_rate'}

    def __init__(self, api, ttl = .5, origin_hrn=None):
        self.api = api
        #filepath = path + os.sep + filename
        self.policy = Policy(self.api)    
        self.origin_hrn = origin_hrn
        self.registry = api.registries[api.hrn]
        self.credential = api.getCredential()
        self.nodes = []
        self.persons = []

    def get_slivers(self, xrn, node=None):
        hrn, type = urn_to_hrn(xrn)
         
        slice_name = hrn_to_pl_slicename(hrn)
        # XX Should we just call PLCAPI.GetSliceTicket(slice_name) instead
        # of doing all of this?
        #return self.api.GetSliceTicket(self.auth, slice_name) 
        
        # from PLCAPI.GetSlivers.get_slivers()
        slice_fields = ['slice_id', 'name', 'instantiation', 'expires', 'person_ids', 'slice_tag_ids']
        slices = self.api.plshell.GetSlices(self.api.plauth, slice_name, slice_fields)
        # Build up list of users and slice attributes
        person_ids = set()
        all_slice_tag_ids = set()
        for slice in slices:
            person_ids.update(slice['person_ids'])
            all_slice_tag_ids.update(slice['slice_tag_ids'])
        person_ids = list(person_ids)
        all_slice_tag_ids = list(all_slice_tag_ids)
        # Get user information
        all_persons_list = self.api.plshell.GetPersons(self.api.plauth, {'person_id':person_ids,'enabled':True}, ['person_id', 'enabled', 'key_ids'])
        all_persons = {}
        for person in all_persons_list:
            all_persons[person['person_id']] = person        

        # Build up list of keys
        key_ids = set()
        for person in all_persons.values():
            key_ids.update(person['key_ids'])
        key_ids = list(key_ids)
        # Get user account keys
        all_keys_list = self.api.plshell.GetKeys(self.api.plauth, key_ids, ['key_id', 'key', 'key_type'])
        all_keys = {}
        for key in all_keys_list:
            all_keys[key['key_id']] = key
        # Get slice attributes
        all_slice_tags_list = self.api.plshell.GetSliceTags(self.api.plauth, all_slice_tag_ids)
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
        peers = self.api.plshell.GetPeers(self.api.plauth, {}, ['peer_id', 'peername', 'shortname', 'hrn_root'])
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

        if site_authority != self.api.hrn:
            sfa_peer = site_authority

        return sfa_peer

    def verify_slice_nodes(self, slice, requested_slivers, peer):
        
        nodes = self.api.plshell.GetNodes(self.api.plauth, slice['node_ids'], ['hostname'])
        current_slivers = [node['hostname'] for node in nodes]

        # remove nodes not in rspec
        deleted_nodes = list(set(current_slivers).difference(requested_slivers))

        # add nodes from rspec
        added_nodes = list(set(requested_slivers).difference(current_slivers))        

        try:
            if peer:
                self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'slice', slice['slice_id'], peer['shortname'])
            self.api.plshell.AddSliceToNodes(self.api.plauth, slice['name'], added_nodes)
            self.api.plshell.DeleteSliceFromNodes(self.api.plauth, slice['name'], deleted_nodes)

        except: 
            self.api.logger.log_exc('Failed to add/remove slice from nodes')

    def verify_slice_links(self, slice, links, aggregate):
        # nodes is undefined here
        if not links or not aggregate.nodes:
            return 
        for link in links:
            topo_rspec = VLink.get_topo_rspec(link)            
        

    def handle_peer(self, site, slice, persons, peer):
        if peer:
            # bind site
            try:
                if site:
                    self.api.plshell.BindObjectToPeer(self.api.plauth, 'site', \
                       site['site_id'], peer['shortname'], slice['site_id'])
            except Exception,e:
                self.api.plshell.DeleteSite(self.api.plauth, site['site_id'])
                raise e
            
            # bind slice
            try:
                if slice:
                    self.api.plshell.BindObjectToPeer(self.api.plauth, 'slice', \
                       slice['slice_id'], peer['shortname'], slice['slice_id'])
            except Exception,e:
                self.api.plshell.DeleteSlice(self.api.plauth, slice['slice_id'])
                raise e 

            # bind persons
            for person in persons:
                try:
                    self.api.plshell.BindObjectToPeer(self.api.plauth, 'person', \
                        person['person_id'], peer['shortname'], person['peer_person_id'])

                    for (key, remote_key_id) in zip(person['keys'], person['key_ids']):
                        try:
                            self.api.plshell.BindObjectToPeer(self.api.plauth, 'key',\
                                key['key_id'], peer['shortname'], remote_key_id)
                        except:
                            self.api.plshell.DeleteKey(self.api.plauth, key['key_id'])
                            self.api.logger("failed to bind key: %s to peer: %s " % (key['key_id'], peer['shortname']))
                except Exception,e:
                    self.api.plshell.DeletePerson(self.api.plauth, person['person_id'])
                    raise e       

        return slice

    def verify_site(self, slice_xrn, slice_record={}, peer=None, sfa_peer=None):
        (slice_hrn, type) = urn_to_hrn(slice_xrn)
        site_hrn = get_authority(slice_hrn)
        # login base can't be longer than 20 characters
        slicename = hrn_to_pl_slicename(slice_hrn)
        authority_name = slicename.split('_')[0]
        login_base = authority_name[:20]
        sites = self.api.plshell.GetSites(self.api.plauth, login_base)
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
            site['site_id'] = self.api.plshell.AddSite(self.api.plauth, site)
            # exempt federated sites from monitor policies
            self.api.plshell.AddSiteTag(self.api.plauth, site['site_id'], 'exempt_site_until', "20200101")
            
            # is this still necessary?
            # add record to the local registry 
            if sfa_peer and slice_record:
                peer_dict = {'type': 'authority', 'hrn': site_hrn, \
                             'peer_authority': sfa_peer, 'pointer': site['site_id']}
                self.registry.register_peer_object(self.credential, peer_dict)
        else:
            site =  sites[0]
            if peer:
                # unbind from peer so we can modify if necessary. Will bind back later
                self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'site', site['site_id'], peer['shortname']) 
        
        return site        

    def verify_slice(self, slice_hrn, slice_record, peer, sfa_peer):
        slicename = hrn_to_pl_slicename(slice_hrn)
        parts = slicename.split("_")
        login_base = parts[0]
        slices = self.api.plshell.GetSlices(self.api.plauth, [slicename]) 
        if not slices:
            slice = {'name': slicename,
                     'url': slice_record.get('url', slice_hrn), 
                     'description': slice_record.get('description', slice_hrn)}
            # add the slice                          
            slice['slice_id'] = self.api.plshell.AddSlice(self.api.plauth, slice)
            slice['node_ids'] = []
            slice['person_ids'] = []
            if peer:
                slice['peer_slice_id'] = slice_record.get('slice_id', None) 
            # mark this slice as an sfa peer record
            if sfa_peer:
                peer_dict = {'type': 'slice', 'hrn': slice_hrn, 
                             'peer_authority': sfa_peer, 'pointer': slice['slice_id']}
                self.registry.register_peer_object(self.credential, peer_dict)
        else:
            slice = slices[0]
            if peer:
                slice['peer_slice_id'] = slice_record.get('slice_id', None)
                # unbind from peer so we can modify if necessary. Will bind back later
                self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'slice',\
                             slice['slice_id'], peer['shortname'])
	        #Update existing record (e.g. expires field) it with the latest info.
            if slice_record and slice['expires'] != slice_record['expires']:
                self.api.plshell.UpdateSlice(self.api.plauth, slice['slice_id'],\
                             {'expires' : slice_record['expires']})
       
        return slice

    #def get_existing_persons(self, users):
    def verify_persons(self, slice_hrn, slice_record, users, peer, sfa_peer, append=True):
        users_by_email = {}
        users_by_site = defaultdict(list)

        users_dict = {} 
        for user in users:
            if 'append' in user and user['append'] == False:
                append = False
            if 'email' in user:
                users_by_email[user['email']] = user
                users_dict[user['email']] = user
            elif 'urn' in user:
                hrn, type = urn_to_hrn(user['urn'])
                username = get_leaf(hrn) 
                login_base = get_leaf(get_authority(user['urn']))
                user['username'] = username 
                users_by_site[login_base].append(user)

        existing_user_ids = []
        if users_by_email:
            # get existing users by email 
            existing_users = self.api.plshell.GetPersons(self.api.plauth, \
                {'email': users_by_email.keys()}, ['person_id', 'key_ids', 'email'])
            existing_user_ids.extend([user['email'] for user in existing_users])

        if users_by_site:
            # get a list of user sites (based on requeste user urns
            site_list = self.api.plshell.GetSites(self.api.plauth, users_by_site.keys(), \
                ['site_id', 'login_base', 'person_ids'])
            sites = {}
            site_user_ids = []
            
            # get all existing users at these sites
            for site in site_list:
                sites[site['site_id']] = site
                site_user_ids.extend(site['person_ids'])

            existing_site_persons_list = self.api.plshell.GetPersons(self.api.plauth, \
              site_user_ids,  ['person_id', 'key_ids', 'email', 'site_ids'])

            # all requested users are either existing users or new (added) users      
            for login_base in users_by_site:
                requested_site_users = users_by_site[login_base]
                for requested_user in requested_site_users:
                    user_found = False
                    for existing_user in existing_site_persons_list:
                        for site_id in existing_user['site_ids']:
                            site = sites[site_id]
                            if login_base == site['login_base'] and \
                               existing_user['email'].startswith(requested_user['username']):
                                existing_user_ids.append(existing_user['email'])
                                users_dict[existing_user['email']] = requested_user
                                user_found = True
                                break
                        if user_found:
                            break
      
                    if user_found == False:
                        fake_email = requested_user['username'] + '@geni.net'
                        users_dict[fake_email] = requested_user
                

        # requested slice users        
        requested_user_ids = users_dict.keys()
        # existing slice users
        existing_slice_users_filter = {'person_id': slice_record.get('person_ids', [])}
        existing_slice_users = self.api.plshell.GetPersons(self.api.plauth, \
             existing_slice_users_filter, ['person_id', 'key_ids', 'email'])
        existing_slice_user_ids = [user['email'] for user in existing_slice_users]
        
        # users to be added, removed or updated
        added_user_ids = set(requested_user_ids).difference(existing_user_ids)
        added_slice_user_ids = set(requested_user_ids).difference(existing_slice_user_ids)
        removed_user_ids = set(existing_slice_user_ids).difference(requested_user_ids)
        updated_user_ids = set(existing_slice_user_ids).intersection(requested_user_ids)

        # Remove stale users (only if we are not appending).
        if append == False:
            for removed_user_id in removed_user_ids:
                self.api.plshell.DeletePersonFromSlice(self.api.plauth, removed_user_id, slice_record['name'])
        # update_existing users
        updated_users_list = [user for user in existing_slice_users if user['email'] in \
          updated_user_ids]
        self.verify_keys(existing_slice_users, updated_users_list, peer, append)

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
            person['person_id'] = self.api.plshell.AddPerson(self.api.plauth, person)
            if peer:
                person['peer_person_id'] = added_user['person_id']
            added_persons.append(person)
           
            # enable the account 
            self.api.plshell.UpdatePerson(self.api.plauth, person['person_id'], {'enabled': True})
            
            # add person to site
            self.api.plshell.AddPersonToSite(self.api.plauth, added_user_id, login_base)

            for key_string in added_user.get('keys', []):
                key = {'key':key_string, 'key_type':'ssh'}
                key['key_id'] = self.api.plshell.AddPersonKey(self.api.plauth, person['person_id'], key)
                person['keys'].append(key)

            # add the registry record
            if sfa_peer:
                peer_dict = {'type': 'user', 'hrn': hrn, 'peer_authority': sfa_peer, \
                    'pointer': person['person_id']}
                self.registry.register_peer_object(self.credential, peer_dict)
    
        for added_slice_user_id in added_slice_user_ids.union(added_user_ids):
            # add person to the slice 
            self.api.plshell.AddPersonToSlice(self.api.plauth, added_slice_user_id, slice_record['name'])
            # if this is a peer record then it should already be bound to a peer.
            # no need to return worry about it getting bound later 

        return added_persons
            

    def verify_keys(self, persons, users, peer, append=True):
        # existing keys 
        key_ids = []
        for person in persons:
            key_ids.extend(person['key_ids'])
        keylist = self.api.plshell.GetKeys(self.api.plauth, key_ids, ['key_id', 'key'])
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
                            self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'person', person['person_id'], peer['shortname'])
                        key['key_id'] = self.api.plshell.AddPersonKey(self.api.plauth, user['email'], key)
                        if peer:
                            key_index = user_keys.index(key['key'])
                            remote_key_id = user['key_ids'][key_index]
                            self.api.plshell.BindObjectToPeer(self.api.plauth, 'key', key['key_id'], peer['shortname'], remote_key_id)
                            
                    finally:
                        if peer:
                            self.api.plshell.BindObjectToPeer(self.api.plauth, 'person', person['person_id'], peer['shortname'], user['person_id'])
        
        # remove old keys (only if we are not appending)
        if append == False: 
            removed_keys = set(existing_keys).difference(requested_keys)
            for existing_key_id in keydict:
                if keydict[existing_key_id] in removed_keys:
                    try:
                        if peer:
                            self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'key', existing_key_id, peer['shortname'])
                        self.api.plshell.DeleteKey(self.api.plauth, existing_key_id)
                    except:
                        pass   

    def verify_slice_attributes(self, slice, requested_slice_attributes):
        # get list of attributes users ar able to manage
        slice_attributes = self.api.plshell.GetTagTypes(self.api.plauth, {'category': '*slice*', '|roles': ['user']})
        valid_slice_attribute_names = [attribute['tagname'] for attribute in slice_attributes]

        # get sliver attributes
        added_slice_attributes = []
        removed_slice_attributes = []
        ignored_slice_attribute_names = []
        existing_slice_attributes = self.api.plshell.GetSliceTags(self.api.plauth, {'slice_id': slice['slice_id']})

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

            if not attribute_found:
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
                self.api.plshell.DeleteSliceTag(self.api.plauth, attribute['slice_tag_id'])
            except Exception, e:
                self.api.logger.warn('Failed to remove sliver attribute. name: %s, value: %s, node_id: %s\nCause:%s'\
                                % (name, value,  node_id, str(e)))

        # add requested_attributes
        for attribute in added_slice_attributes:
            try:
                self.api.plshell.AddSliceTag(self.api.plauth, slice['name'], attribute['name'], attribute['value'], attribute.get('node_id', None))
            except Exception, e:
                self.api.logger.warn('Failed to add sliver attribute. name: %s, value: %s, node_id: %s\nCause:%s'\
                                % (name, value,  node_id, str(e)))

    def create_slice_aggregate(self, xrn, rspec):
        hrn, type = urn_to_hrn(xrn)
        # Determine if this is a peer slice
        peer = self.get_peer(hrn)
        sfa_peer = self.get_sfa_peer(hrn)

        spec = RSpec(rspec)
        # Get the slice record from sfa
        slicename = hrn_to_pl_slicename(hrn) 
        slice = {}
        slice_record = None
        registry = self.api.registries[self.api.hrn]
        credential = self.api.getCredential()

        site_id, remote_site_id = self.verify_site(registry, credential, hrn, peer, sfa_peer)
        slice = self.verify_slice(registry, credential, hrn, site_id, remote_site_id, peer, sfa_peer)

        # find out where this slice is currently running
        nodelist = self.api.plshell.GetNodes(self.api.plauth, slice['node_ids'], ['hostname'])
        hostnames = [node['hostname'] for node in nodelist]

        # get netspec details
        nodespecs = spec.getDictsByTagName('NodeSpec')

        # dict in which to store slice attributes to set for the nodes
        nodes = {}
        for nodespec in nodespecs:
            if isinstance(nodespec['name'], list):
                for nodename in nodespec['name']:
                    nodes[nodename] = {}
                    for k in nodespec.keys():
                        rspec_attribute_value = nodespec[k]
                        if (self.rspec_to_slice_tag.has_key(k)):
                            slice_tag_name = self.rspec_to_slice_tag[k]
                            nodes[nodename][slice_tag_name] = rspec_attribute_value
            elif isinstance(nodespec['name'], StringTypes):
                nodename = nodespec['name']
                nodes[nodename] = {}
                for k in nodespec.keys():
                    rspec_attribute_value = nodespec[k]
                    if (self.rspec_to_slice_tag.has_key(k)):
                        slice_tag_name = self.rspec_to_slice_tag[k]
                        nodes[nodename][slice_tag_name] = rspec_attribute_value

                for k in nodespec.keys():
                    rspec_attribute_value = nodespec[k]
                    if (self.rspec_to_slice_tag.has_key(k)):
                        slice_tag_name = self.rspec_to_slice_tag[k]
                        nodes[nodename][slice_tag_name] = rspec_attribute_value

        node_names = nodes.keys()
        # remove nodes not in rspec
        deleted_nodes = list(set(hostnames).difference(node_names))
        # add nodes from rspec
        added_nodes = list(set(node_names).difference(hostnames))

        try:
            if peer:
                self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'slice', slice['slice_id'], peer)

            self.api.plshell.AddSliceToNodes(self.api.plauth, slicename, added_nodes) 

            # Add recognized slice tags
            for node_name in node_names:
                node = nodes[node_name]
                for slice_tag in node.keys():
                    value = node[slice_tag]
                    if (isinstance(value, list)):
                        value = value[0]

                    self.api.plshell.AddSliceTag(self.api.plauth, slicename, slice_tag, value, node_name)

            self.api.plshell.DeleteSliceFromNodes(self.api.plauth, slicename, deleted_nodes)
        finally:
            if peer:
                self.api.plshell.BindObjectToPeer(self.api.plauth, 'slice', slice['slice_id'], peer, slice['peer_slice_id'])

        return 1

