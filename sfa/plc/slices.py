### $Id$
### $URL$

import datetime
import time
import traceback
import sys

from types import StringTypes
from sfa.util.namespace import *
from sfa.util.rspec import *
from sfa.util.specdict import *
from sfa.util.faults import *
from sfa.util.record import SfaRecord
from sfa.util.policy import Policy
from sfa.util.prefixTree import prefixTree
from sfa.util.debug import log

MAXINT =  2L**31-1

class Slices:

    rspec_to_slice_tag = {'max_rate':'net_max_rate'}

    def __init__(self, api, ttl = .5, origin_hrn=None):
        self.api = api
        #filepath = path + os.sep + filename
        self.policy = Policy(self.api)    
        self.origin_hrn = origin_hrn

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
                peer = peer_record['shortname']

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

    def verify_site(self, registry, credential, slice_hrn, peer, sfa_peer, reg_objects=None):
        authority = get_authority(slice_hrn)
        authority_urn = hrn_to_urn(authority, 'authority')
        
        if reg_objects:
            site = reg_objects['site']
        else:
            site_records = registry.Resolve(authority_urn, [credential])
            site = {}            
            for site_record in site_records:            
                if site_record['type'] == 'authority':
                    site = site_record
            if not site:
                raise RecordNotFound(authority)
            
        remote_site_id = site.pop('site_id')    
                
        login_base = get_leaf(authority)
        sites = self.api.plshell.GetSites(self.api.plauth, login_base)

        if not sites:
            site_id = self.api.plshell.AddSite(self.api.plauth, site)
            if peer:
                self.api.plshell.BindObjectToPeer(self.api.plauth, 'site', site_id, peer, remote_site_id)   
            # mark this site as an sfa peer record
            if sfa_peer and not reg_objects:
                peer_dict = {'type': 'authority', 'hrn': authority, 'peer_authority': sfa_peer, 'pointer': site_id}
                registry.register_peer_object(credential, peer_dict)
        else:
            site_id = sites[0]['site_id']
            remote_site_id = sites[0]['peer_site_id']
            
	    old_site = sites[0]
	    #the site is already on the remote agg. Let us update(e.g. max_slices field) it with the latest info.
            self.sync_site(old_site, site, peer)


        return (site_id, remote_site_id) 

    def verify_slice(self, registry, credential, slice_hrn, site_id, remote_site_id, peer, sfa_peer, reg_objects=None):
        slice = {}
        slice_record = None
        authority = get_authority(slice_hrn)

        if reg_objects:
            slice_record = reg_objects['slice_record']
        else:
            slice_records = registry.Resolve(slice_hrn, [credential])
    
            for record in slice_records:
                if record['type'] in ['slice']:
                    slice_record = record
            if not slice_record:
                raise RecordNotFound(hrn)
            
        
        slicename = hrn_to_pl_slicename(slice_hrn)
        parts = slicename.split("_")
        login_base = parts[0]
        slices = self.api.plshell.GetSlices(self.api.plauth, [slicename]) 
        if not slices:
            slice_fields = {}
            slice_keys = ['name', 'url', 'description']
            for key in slice_keys:
                if key in slice_record and slice_record[key]:
                    slice_fields[key] = slice_record[key]

            # add the slice  
            slice_id = self.api.plshell.AddSlice(self.api.plauth, slice_fields)
            slice = slice_fields
            slice['slice_id'] = slice_id

            # mark this slice as an sfa peer record
            if sfa_peer:
                peer_dict = {'type': 'slice', 'hrn': slice_hrn, 'peer_authority': sfa_peer, 'pointer': slice_id}
                registry.register_peer_object(credential, peer_dict)

            #this belongs to a peer
            if peer:
                self.api.plshell.BindObjectToPeer(self.api.plauth, 'slice', slice_id, peer, slice_record['pointer'])
            slice['node_ids'] = []
        else:
            slice = slices[0]
            slice_id = slice['slice_id']
            site_id = slice['site_id']
	    #the slice is alredy on the remote agg. Let us update(e.g. expires field) it with the latest info.
	    self.sync_slice(slice, slice_record, peer)

        slice['peer_slice_id'] = slice_record['pointer']
        self.verify_persons(registry, credential, slice_record, site_id, remote_site_id, peer, sfa_peer, reg_objects)
    
        return slice        

    def verify_persons(self, registry, credential, slice_record, site_id, remote_site_id, peer, sfa_peer, reg_objects=None):
        # get the list of valid slice users from the registry and make 
        # sure they are added to the slice 
        slicename = hrn_to_pl_slicename(slice_record['hrn'])
        if reg_objects:
            researchers = reg_objects['users'].keys()
        else:
            researchers = slice_record.get('researcher', [])
        for researcher in researchers:
            if reg_objects:
                person_dict = reg_objects['users'][researcher]
            else:
                person_records = registry.Resolve(researcher, [credential])
                for record in person_records:
                    if record['type'] in ['user'] and record['enabled']:
                        person_record = record
                if not person_record:
                    return 1
                person_dict = person_record

            local_person=False
            if peer:
                peer_id = self.api.plshell.GetPeers(self.api.plauth, {'shortname': peer}, ['peer_id'])[0]['peer_id']
                persons = self.api.plshell.GetPersons(self.api.plauth, {'email': [person_dict['email']], 'peer_id': peer_id}, ['person_id', 'key_ids'])
                if not persons:
                    persons = self.api.plshell.GetPersons(self.api.plauth, [person_dict['email']], ['person_id', 'key_ids'])
                    if persons:
                        local_person=True
                        
            else:
                persons = self.api.plshell.GetPersons(self.api.plauth, [person_dict['email']], ['person_id', 'key_ids'])   
        
            if not persons:
                person_id=self.api.plshell.AddPerson(self.api.plauth, person_dict)
                self.api.plshell.UpdatePerson(self.api.plauth, person_id, {'enabled' : True})
                
                # mark this person as an sfa peer record
                if sfa_peer:
                    peer_dict = {'type': 'user', 'hrn': researcher, 'peer_authority': sfa_peer, 'pointer': person_id}
                    registry.register_peer_object(credential, peer_dict)

                if peer:
                    self.api.plshell.BindObjectToPeer(self.api.plauth, 'person', person_id, peer, person_dict['pointer'])
                key_ids = []
            else:
                person_id = persons[0]['person_id']
                key_ids = persons[0]['key_ids']


            # if this is a peer person, we must unbind them from the peer or PLCAPI will throw
            # an error
            if peer:
                self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'person', person_id, peer)
                self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'site', site_id,  peer)

            self.api.plshell.AddPersonToSlice(self.api.plauth, person_dict['email'], slicename)
            self.api.plshell.AddPersonToSite(self.api.plauth, person_dict['email'], site_id)
            if peer and not local_person:
                self.api.plshell.BindObjectToPeer(self.api.plauth, 'person', person_id, peer, person_dict['pointer'])
            if peer:
                self.api.plshell.BindObjectToPeer(self.api.plauth, 'site', site_id, peer, remote_site_id)
            
            self.verify_keys(registry, credential, person_dict, key_ids, person_id, peer, local_person)

    def verify_keys(self, registry, credential, person_dict, key_ids, person_id,  peer, local_person):
        keylist = self.api.plshell.GetKeys(self.api.plauth, key_ids, ['key'])
        keys = [key['key'] for key in keylist]
        
        #add keys that arent already there
        key_ids = person_dict['key_ids']
        for personkey in person_dict['keys']:
            if personkey not in keys:
                key = {'key_type': 'ssh', 'key': personkey}
                if peer:
                    self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'person', person_id, peer)
                key_id = self.api.plshell.AddPersonKey(self.api.plauth, person_dict['email'], key)
                if peer and not local_person:
                    self.api.plshell.BindObjectToPeer(self.api.plauth, 'person', person_id, peer, person_dict['pointer'])
                if peer:
                    try: self.api.plshell.BindObjectToPeer(self.api.plauth, 'key', key_id, peer, key_ids.pop(0))

                    except: pass   

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
        if peer:
            self.api.plshell.BindObjectToPeer(self.api.plauth, 'slice', slice['slice_id'], peer, slice['peer_slice_id'])

        return 1

    def sync_site(self, old_record, new_record, peer):
        if old_record['max_slices'] != new_record['max_slices'] or old_record['max_slivers'] != new_record['max_slivers']:
            if peer:
                self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'site', old_record['site_id'], peer)
	    if old_record['max_slices'] != new_record['max_slices']:
                self.api.plshell.UpdateSite(self.api.plauth, old_record['site_id'], {'max_slices' : new_record['max_slices']})
	    if old_record['max_slivers'] != new_record['max_slivers']:
		self.api.plshell.UpdateSite(self.api.plauth, old_record['site_id'], {'max_slivers' : new_record['max_slivers']})
	    if peer:
                self.api.plshell.BindObjectToPeer(self.api.plauth, 'site', old_record['site_id'], peer, old_record['peer_site_id'])
	return 1

    def sync_slice(self, old_record, new_record, peer):
        if old_record['expires'] != new_record['expires']:
            if peer:
                self.api.plshell.UnBindObjectFromPeer(self.api.plauth, 'slice', old_record['slice_id'], peer)
            self.api.plshell.UpdateSlice(self.api.plauth, old_record['slice_id'], {'expires' : new_record['expires']})
	    if peer:
                self.api.plshell.BindObjectToPeer(self.api.plauth, 'slice', old_record['slice_id'], peer, old_record['peer_slice_id'])
	return 1
