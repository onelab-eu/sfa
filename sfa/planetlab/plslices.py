import time
from types import StringTypes
from collections import defaultdict

from sfa.util.sfatime import utcparse, datetime_to_epoch
from sfa.util.sfalogging import logger
from sfa.util.xrn import Xrn, get_leaf, get_authority, urn_to_hrn
from sfa.rspecs.rspec import RSpec
from sfa.planetlab.vlink import VLink
from sfa.planetlab.topology import Topology
from sfa.planetlab.plxrn import PlXrn, hrn_to_pl_slicename, xrn_to_hostname, top_auth, hash_loginbase
from sfa.storage.model import SliverAllocation

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
        all_persons_list = self.driver.shell.GetPersons({'person_id':person_ids,'enabled':True}, 
                                                        ['person_id', 'enabled', 'key_ids'])
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
 

    def get_sfa_peer(self, xrn):
        hrn, type = urn_to_hrn(xrn)

        # return the authority for this hrn or None if we are the authority
        sfa_peer = None
        slice_authority = get_authority(hrn)
        site_authority = get_authority(slice_authority)

        if site_authority != self.driver.hrn:
            sfa_peer = site_authority

        return sfa_peer

    def verify_slice_leases(self, slice, rspec_requested_leases):

        leases = self.driver.shell.GetLeases({'name':slice['name'], 'clip':int(time.time())}, 
                                             ['lease_id','name', 'hostname', 't_from', 't_until'])
        grain = self.driver.shell.GetLeaseGranularity()

        requested_leases = []
        for lease in rspec_requested_leases:
             requested_lease = {}
             slice_hrn, _ = urn_to_hrn(lease['slice_id'])

             top_auth_hrn = top_auth(slice_hrn)
             site_hrn = '.'.join(slice_hrn.split('.')[:-1])
             slice_part = slice_hrn.split('.')[-1]
             if top_auth_hrn == self.driver.hrn:
                 login_base = slice_hrn.split('.')[-2][:12]
             else:
                 login_base = hash_loginbase(site_hrn)

             slice_name = '_'.join([login_base, slice_part])

             if slice_name != slice['name']:
                 continue
             elif Xrn(lease['component_id']).get_authority_urn().split(':')[0] != self.driver.hrn:
                 continue

             hostname = xrn_to_hostname(lease['component_id'])
             # fill the requested node with nitos ids
             requested_lease['name'] = slice['name']
             requested_lease['hostname'] = hostname
             requested_lease['t_from'] = int(lease['start_time'])
             requested_lease['t_until'] = int(lease['duration']) * grain + int(lease['start_time'])
             requested_leases.append(requested_lease)



        # prepare actual slice leases by lease_id  
        leases_by_id = {}
        for lease in leases:
             leases_by_id[lease['lease_id']] = {'name': lease['name'], 'hostname': lease['hostname'], \
                                                't_from': lease['t_from'], 't_until': lease['t_until']}
        
        added_leases = []
        kept_leases_id = []
        deleted_leases_id = []
        for lease_id in leases_by_id:
             if leases_by_id[lease_id] not in requested_leases:
                 deleted_leases_id.append(lease_id)
             else:
                 kept_leases_id.append(lease_id)
                 requested_leases.remove(leases_by_id[lease_id])
        added_leases = requested_leases
   

        try:
            self.driver.shell.DeleteLeases(deleted_leases_id)
            for lease in added_leases:
                self.driver.shell.AddLeases(lease['hostname'], slice['name'], lease['t_from'], lease['t_until'])

        except: 
            logger.log_exc('Failed to add/remove slice leases')

        return leases


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
        
        nodes = self.driver.shell.GetNodes(slice['node_ids'], ['node_id', 'hostname', 'interface_ids'])
        current_slivers = [node['hostname'] for node in nodes]

        # remove nodes not in rspec
        deleted_nodes = list(set(current_slivers).difference(slivers.keys()))

        # add nodes from rspec
        added_nodes = list(set(slivers.keys()).difference(current_slivers))        

        try:
            self.driver.shell.AddSliceToNodes(slice['name'], added_nodes)
            self.driver.shell.DeleteSliceFromNodes(slice['name'], deleted_nodes)
            
        except: 
            logger.log_exc('Failed to add/remove slice from nodes')

        slices = self.driver.shell.GetSlices(slice['name'], ['node_ids']) 
        resulting_nodes = self.driver.shell.GetNodes(slices[0]['node_ids'])

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
         
        if not requested_links:
            return

        # exit if links are not supported here
        topology = Topology()
        if not topology:
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

            if ifname1:
                ifname_parts = ifname1.split(':')
                node_raw = ifname_parts[0]
                device = None
                if len(ifname_parts) > 1:
                    device = ifname_parts[1] 
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
                        
        

    def verify_site(self, slice_xrn, slice_record=None, sfa_peer=None, options=None):
        if slice_record is None: slice_record={}
        if options is None: options={}
        (slice_hrn, type) = urn_to_hrn(slice_xrn)
        top_auth_hrn = top_auth(slice_hrn)
        site_hrn = '.'.join(slice_hrn.split('.')[:-1])
        if top_auth_hrn == self.driver.hrn:
            login_base = slice_hrn.split('.')[-2][:12]
        else:
            login_base = hash_loginbase(site_hrn)

        # filter sites by hrn
        sites = self.driver.shell.GetSites({'peer_id': None, 'hrn':site_hrn},
                                           ['site_id','name','abbreviated_name','login_base','hrn'])

        # alredy exists
        if sites:
            site = sites[0]
        else:
            # create new site record
            site = {'name': 'sfa:%s' % site_hrn,
                    'abbreviated_name': site_hrn,
                    'login_base': login_base,
                    'max_slices': 100,
                    'max_slivers': 1000,
                    'enabled': True,
                    'peer_site_id': None,
                    'hrn':site_hrn,
                    'sfa_created': 'True',
            }
            site_id = self.driver.shell.AddSite(site)
            # plcapi tends to mess with the incoming hrn so let's make sure
            self.driver.shell.SetSiteHrn (site_id, site_hrn)
            site['site_id'] = site_id
            # exempt federated sites from monitor policies
            self.driver.shell.AddSiteTag(site_id, 'exempt_site_until', "20200101")

        return site


    def verify_slice(self, slice_hrn, slice_record, sfa_peer, expiration, options=None):
        if options is None: options={}
        top_auth_hrn = top_auth(slice_hrn)
        site_hrn = '.'.join(slice_hrn.split('.')[:-1])
        slice_part = slice_hrn.split('.')[-1]
        if top_auth_hrn == self.driver.hrn:
            login_base = slice_hrn.split('.')[-2][:12]
        else:
            login_base = hash_loginbase(site_hrn)
        slice_name = '_'.join([login_base, slice_part])

        expires = int(datetime_to_epoch(utcparse(expiration)))
        # Filter slices by HRN
        slices = self.driver.shell.GetSlices({'peer_id': None, 'hrn':slice_hrn},
                                             ['slice_id','name','hrn','expires'])
        
        if slices:
            slice = slices[0]
            slice_id = slice['slice_id']
            #Update expiration if necessary
            if slice.get('expires', None) != expires:
                self.driver.shell.UpdateSlice( slice_id, {'expires' : expires})
        else:
            if slice_record:
                url = slice_record.get('url', slice_hrn)
                description = slice_record.get('description', slice_hrn)
            else:
                url = slice_hrn
                description = slice_hrn
            slice = {'name': slice_name,
                     'url': url,
                     'description': description,
                     'hrn': slice_hrn,
                     'sfa_created': 'True',
                     #'expires': expires,
            }
            # add the slice
            slice_id = self.driver.shell.AddSlice(slice)
            # plcapi tends to mess with the incoming hrn so let's make sure
            self.driver.shell.SetSliceHrn (slice_id, slice_hrn)
            # cannot be set with AddSlice
            # set the expiration
            self.driver.shell.UpdateSlice(slice_id, {'expires': expires})

        return self.driver.shell.GetSlices(slice_id)[0]


    # in the following code, we use
    # 'person' to denote a PLCAPI-like record with typically 'person_id' and 'email'
    # 'user' to denote an incoming record with typically 'urn' and 'email' - we add 'hrn' in there
    #        'slice_record': it seems like the first of these 'users' also contains a 'slice_record' 
    #           key that holds stuff like 'hrn', 'slice_id', 'authority',...
    # 
    def create_person_from_user (self, user, site_id):
        user_hrn = user['hrn']
        # the value to use if 'user' has no 'email' attached - or if the attached email already exists
        # typically 
        ( auth_hrn, _ , leaf ) = user_hrn.rpartition('.')
        # somehow this has backslashes, get rid of them
        auth_hrn = auth_hrn.replace('\\','')
        default_email = "%s@%s.stub"%(leaf,auth_hrn)

        person_record = { 
            # required
            'first_name': user.get('first_name',user_hrn),
            'last_name': user.get('last_name',user_hrn),
            'email': user.get('email', default_email),
            # our additions
            'enabled': True,
            'sfa_created': 'True',
            'hrn': user_hrn,
        }

        logger.debug ("about to attempt to AddPerson with %s"%person_record)
        try:
            # the thing is, the PLE db has a limitation on re-using the same e-mail
            # in the case where people have an account on ple.upmc and then then come 
            # again from onelab.upmc, they will most likely have the same e-mail, and so kaboom..
            # so we first try with the accurate email
            person_id = int (self.driver.shell.AddPerson(person_record))
        except:
            logger.log_exc("caught during first attempt at AddPerson")
            # and if that fails we start again with the email based on the hrn, which this time is unique..
            person_record['email']=default_email
            logger.debug ("second chance with email=%s"%person_record['email'])
            person_id = int (self.driver.shell.AddPerson(person_record))
        self.driver.shell.AddRoleToPerson('user', person_id)
        self.driver.shell.AddPersonToSite(person_id, site_id)
        # plcapi tends to mess with the incoming hrn so let's make sure
        self.driver.shell.SetPersonHrn (person_id, user_hrn)
        # also 'enabled':True does not seem to pass through with AddPerson
        self.driver.shell.UpdatePerson (person_id, {'enabled': True})

        return person_id

    def verify_persons(self, slice_hrn, slice_record, users, sfa_peer, options=None):
        if options is None: options={}

        # first we annotate the incoming users arg with a 'hrn' key
        for user in users:
           user['hrn'], _ = urn_to_hrn(user['urn'])
        # this is for retrieving users from a hrn
        users_by_hrn = { user['hrn'] : user for user in users }

        for user in users: logger.debug("incoming user %s"%user)

        # compute the hrn's for the authority and site
        top_auth_hrn = top_auth(slice_hrn)
        site_hrn = '.'.join(slice_hrn.split('.')[:-1])
        slice_part = slice_hrn.split('.')[-1]
        # deduce login_base and slice_name
        if top_auth_hrn == self.driver.hrn:
            login_base = slice_hrn.split('.')[-2][:12]
        else:
            login_base = hash_loginbase(site_hrn)
        slice_name = '_'.join([login_base, slice_part])

        # locate the site object
        # due to a limitation in PLCAPI, we have to specify 'hrn' as part of the return fields
        site = self.driver.shell.GetSites ({'peer_id':None, 'hrn':site_hrn}, ['site_id','hrn'])[0]
        site_id = site['site_id']

        # locate the slice object
        slice = self.driver.shell.GetSlices ({'peer_id':None, 'hrn':slice_hrn}, ['slice_id','hrn','person_ids'])[0]
        slice_id = slice['slice_id']
        slice_person_ids = slice['person_ids']

        # the common set of attributes for our calls to GetPersons
        person_fields = ['person_id','email','hrn']

        # for the intended set of hrns, locate existing persons
        target_hrns = [ user['hrn'] for user in users ]
        target_existing_persons = self.driver.shell.GetPersons ({'peer_id':None, 'hrn': target_hrns}, person_fields)
        target_existing_person_ids = [ person ['person_id'] for person in target_existing_persons ]
        # find out the hrns that *do not* have a corresponding person
        existing_hrns = [ person['hrn'] for person in target_existing_persons ]
        tocreate_hrns = set (target_hrns) - set (existing_hrns)
        # create these
        target_created_person_ids = [ self.create_person_from_user (users_by_hrn[hrn], site_id) for hrn in tocreate_hrns ]

        # we can partition the persons of interest into one of these 3 classes
        add_person_ids  = set(target_created_person_ids) | set(target_existing_person_ids) - set(slice_person_ids)
        keep_person_ids = set(target_existing_person_ids) & set(slice_person_ids)
        del_person_ids  = set(slice_person_ids) - set(target_existing_person_ids)

        # delete 
        for person_id in del_person_ids:
            self.driver.shell.DeletePersonFromSlice (person_id, slice_id)

        # about the last 2 sets, for managing keys, we need to trace back person_id -> user
        # and for this we need all the Person objects; we already have the target_existing ones
        # also we avoid issuing a call if possible
        target_created_persons = [] if not target_created_person_ids \
                                 else self.driver.shell.GetPersons \
                                      ({'peer_id':None, 'person_id':target_created_person_ids}, person_fields)
        persons_by_person_id = { person['person_id'] : person \
                                 for person in target_existing_persons + target_created_persons }

        def user_by_person_id (person_id):
            person = persons_by_person_id [person_id]
            hrn = person ['hrn']
            return users_by_hrn [hrn]
        
        persons_to_verify_keys = {}
        # add 
        for person_id in add_person_ids:
            self.driver.shell.AddPersonToSlice(person_id, slice_id)
            persons_to_verify_keys[person_id] = user_by_person_id(person_id)
        # Update kept persons
        for person_id in keep_person_ids:
            persons_to_verify_keys[person_id] = user_by_person_id(person_id)
        self.verify_keys(persons_to_verify_keys, options)

        # return hrns of the newly added persons

        return [ persons_by_person_id[person_id]['hrn'] for person_id in add_person_ids ]

    def verify_keys(self, persons_to_verify_keys, options=None):
        if options is None: options={}
        # we only add keys that comes from sfa to persons in PL
        for person_id in persons_to_verify_keys:
             person_sfa_keys = persons_to_verify_keys[person_id].get('keys', [])
             person_pl_keys = self.driver.shell.GetKeys({'person_id': int(person_id)})
             person_pl_keys_list = [key['key'] for key in person_pl_keys]

             keys_to_add = set(person_sfa_keys).difference(person_pl_keys_list)

             for key_string in keys_to_add:
                  key = {'key': key_string, 'key_type': 'ssh'}
                  self.driver.shell.AddPersonKey(int(person_id), key)


    def verify_slice_attributes(self, slice, requested_slice_attributes, options=None, admin=False):
        if options is None: options={}
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
        # we need to keep the slice hrn anyway
        ignored_slice_attribute_names = ['hrn']
        existing_slice_attributes = self.driver.shell.GetSliceTags({'slice_id': slice['slice_id']})

        # get attributes that should be removed
        for slice_tag in existing_slice_attributes:
            if slice_tag['tagname'] in ignored_slice_attribute_names:
                # If a slice already has a admin only role it was probably given to them by an
                # admin, so we should ignore it.
                ignored_slice_attribute_names.append(slice_tag['tagname'])
                attribute_found=True
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
                self.driver.shell.AddSliceTag(slice['name'], attribute['name'], 
                                              attribute['value'], attribute.get('node_id', None))
            except Exception, e:
                logger.warn('Failed to add sliver attribute. name: %s, value: %s, node_id: %s\nCause:%s'\
                                % (slice['name'], attribute['value'],  attribute.get('node_id'), str(e)))

