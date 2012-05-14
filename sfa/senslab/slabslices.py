from types import StringTypes
from collections import defaultdict
import sys
from sfa.util.xrn import get_leaf, get_authority, urn_to_hrn
from sfa.util.plxrn import hrn_to_pl_slicename
from sfa.util.policy import Policy
from sfa.rspecs.rspec import RSpec
from sfa.plc.vlink import VLink
from sfa.util.xrn import Xrn
from sfa.util.sfalogging import logger

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import Table, Column, MetaData, join, ForeignKey
from sfa.storage.model import RegRecord
from sfa.storage.alchemy import dbsession,engine

MAXINT =  2L**31-1

class SlabSlices:

    rspec_to_slice_tag = {'max_rate':'net_max_rate'}

    #def __init__(self, api, ttl = .5, origin_hrn=None):
        #self.api = api
        ##filepath = path + os.sep + filename
        #self.policy = Policy(self.api)    
        #self.origin_hrn = origin_hrn
        #self.registry = api.registries[api.hrn]
        #self.credential = api.getCredential()
        #self.nodes = []
        #self.persons = []


    def __init__(self, driver):
        self.driver = driver
        
        
    def get_slivers(self, xrn, node=None):
        hrn, type = urn_to_hrn(xrn)
         
        slice_name = hrn_to_pl_slicename(hrn)
        # XX Should we just call PLCAPI.GetSliceTicket(slice_name) instead
        # of doing all of this?
        #return self.api.driver.GetSliceTicket(self.auth, slice_name) 
        

       
        slice = self.driver.GetSlices(slice_filter = slice_name, filter_type = 'slice_hrn')
 

        # Get user information
        alchemy_person = dbsession.query(RegRecord).filter_by(record_id = slice['record_id_user']).first()

        slivers = []
        sliver_attributes = []
            
        if slice['oar_job_id'] is not -1:
            nodes_all = self.GetNodes({'hostname':slice['node_ids']},
                            ['node_id', 'hostname','site','boot_state'])
            nodeall_byhostname = dict([(n['hostname'], n) for n in nodes_all])
            nodes = slice['node_ids']
            
            for node in nodes:
                #for sliver_attribute in filter(lambda a: a['node_id'] == node['node_id'], slice_tags):
                sliver_attribute['tagname'] = 'slab-tag'
                sliver_attribute['value'] = 'slab-value'
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
        
        
        
 #def get_slivers(self, xrn, node=None):
        #hrn, type = urn_to_hrn(xrn)
         
        #slice_name = hrn_to_pl_slicename(hrn)
        ## XX Should we just call PLCAPI.GetSliceTicket(slice_name) instead
        ## of doing all of this?
        ##return self.api.driver.GetSliceTicket(self.auth, slice_name) 
        
        ## from PLCAPI.GetSlivers.get_slivers()
        #slice_fields = ['slice_id', 'name', 'instantiation', 'expires', 'person_ids', 'slice_tag_ids']
        #slices = self.api.driver.GetSlices(slice_name, slice_fields)
        ## Build up list of users and slice attributes
        #person_ids = set()
        #all_slice_tag_ids = set()
        #for slice in slices:
            #person_ids.update(slice['person_ids'])
            #all_slice_tag_ids.update(slice['slice_tag_ids'])
        #person_ids = list(person_ids)
        #all_slice_tag_ids = list(all_slice_tag_ids)
        ## Get user information
        #all_persons_list = self.api.driver.GetPersons({'person_id':person_ids,'enabled':True}, ['person_id', 'enabled', 'key_ids'])
        #all_persons = {}
        #for person in all_persons_list:
            #all_persons[person['person_id']] = person        

        ## Build up list of keys
        #key_ids = set()
        #for person in all_persons.values():
            #key_ids.update(person['key_ids'])
        #key_ids = list(key_ids)
        ## Get user account keys
        #all_keys_list = self.api.driver.GetKeys(key_ids, ['key_id', 'key', 'key_type'])
        #all_keys = {}
        #for key in all_keys_list:
            #all_keys[key['key_id']] = key
        ## Get slice attributes
        #all_slice_tags_list = self.api.driver.GetSliceTags(all_slice_tag_ids)
        #all_slice_tags = {}
        #for slice_tag in all_slice_tags_list:
            #all_slice_tags[slice_tag['slice_tag_id']] = slice_tag
           
        #slivers = []
        #for slice in slices:
            #keys = []
            #for person_id in slice['person_ids']:
                #if person_id in all_persons:
                    #person = all_persons[person_id]
                    #if not person['enabled']:
                        #continue
                    #for key_id in person['key_ids']:
                        #if key_id in all_keys:
                            #key = all_keys[key_id]
                            #keys += [{'key_type': key['key_type'],
                                    #'key': key['key']}]
            #attributes = []
            ## All (per-node and global) attributes for this slice
            #slice_tags = []
            #for slice_tag_id in slice['slice_tag_ids']:
                #if slice_tag_id in all_slice_tags:
                    #slice_tags.append(all_slice_tags[slice_tag_id]) 
            ## Per-node sliver attributes take precedence over global
            ## slice attributes, so set them first.
            ## Then comes nodegroup slice attributes
            ## Followed by global slice attributes
            #sliver_attributes = []

            #if node is not None:
                #for sliver_attribute in filter(lambda a: a['node_id'] == node['node_id'], slice_tags):
                    #sliver_attributes.append(sliver_attribute['tagname'])
                    #attributes.append({'tagname': sliver_attribute['tagname'],
                                    #'value': sliver_attribute['value']})

            ## set nodegroup slice attributes
            #for slice_tag in filter(lambda a: a['nodegroup_id'] in node['nodegroup_ids'], slice_tags):
                ## Do not set any nodegroup slice attributes for
                ## which there is at least one sliver attribute
                ## already set.
                #if slice_tag not in slice_tags:
                    #attributes.append({'tagname': slice_tag['tagname'],
                        #'value': slice_tag['value']})

            #for slice_tag in filter(lambda a: a['node_id'] is None, slice_tags):
                ## Do not set any global slice attributes for
                ## which there is at least one sliver attribute
                ## already set.
                #if slice_tag['tagname'] not in sliver_attributes:
                    #attributes.append({'tagname': slice_tag['tagname'],
                                   #'value': slice_tag['value']})

            ## XXX Sanity check; though technically this should be a system invariant
            ## checked with an assertion
            #if slice['expires'] > MAXINT:  slice['expires']= MAXINT
            
            #slivers.append({
                #'hrn': hrn,
                #'name': slice['name'],
                #'slice_id': slice['slice_id'],
                #'instantiation': slice['instantiation'],
                #'expires': slice['expires'],
                #'keys': keys,
                #'attributes': attributes
            #})

        #return slivers
    def get_peer(self, xrn):
        hrn, type = urn_to_hrn(xrn)
        #Does this slice belong to a local site or a peer senslab site?
        peer = None
        
        # get this slice's authority (site)
        slice_authority = get_authority(hrn)
        site_authority = slice_authority
        # get this site's authority (sfa root authority or sub authority)
        #site_authority = get_authority(slice_authority).lower()
        print>>sys.stderr, " \r\n \r\n \t slices.py get_peer slice_authority  %s site_authority %s hrn %s" %(slice_authority, site_authority, hrn)
        # check if we are already peered with this site_authority, if so
        #peers = self.driver.GetPeers({})  
        peers = self.driver.GetPeers(peer_filter = slice_authority)
        for peer_record in peers:
          
            if site_authority == peer_record.hrn:
                peer = peer_record
        print>>sys.stderr, " \r\n \r\n \t slices.py get_peerAPRES Mpeer  %s " %(peer) 
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
        current_slivers = []
        deleted_nodes = []
        
        if slice['node_ids']:
            nodes = self.driver.GetNodes(slice['node_ids'], ['hostname'])
            current_slivers = [node['hostname'] for node in nodes]
    
            # remove nodes not in rspec
            deleted_nodes = list(set(current_slivers).difference(requested_slivers))
    
        # add nodes from rspec
        added_nodes = list(set(requested_slivers).difference(current_slivers))        
        #print>>sys.stderr , "\r\n \r\n \t slices.py  verify_slice_nodes added_nodes %s slice %s" %( added_nodes,slice)
        try:
            #if peer:
                #self.driver.UnBindObjectFromPeer('slice', slice['slice_id'], peer['shortname'])
            #PI is a list, get the only username in this list
            #so that the OAR/LDAP knows the user: remove the authority from the name
            tmp=  slice['PI'][0].split(".")
            username = tmp[(len(tmp)-1)]
            #Update the table with the nodes that populate the slice
            self.driver.db.update_job(slice['name'],nodes = added_nodes)
            print>>sys.stderr, "\r\n \\r\n \r\n \t\t\t VERIFY_SLICE_NODES slice %s \r\n \r\n \r\n " %(slice)
            #If there is a timeslot specified, then a job can be launched
            try:
                slot = slice['timeslot']
                self.driver.LaunchExperimentOnOAR(slice, added_nodes, username)
            except KeyError:
                pass

            
            if deleted_nodes:
                self.driver.DeleteSliceFromNodes(slice['name'], deleted_nodes)

        except: 
            logger.log_exc('Failed to add/remove slice from nodes')
            

    def free_egre_key(self):
        used = set()
        for tag in self.driver.GetSliceTags({'tagname': 'egre_key'}):
                used.add(int(tag['value']))

        for i in range(1, 256):
            if i not in used:
                key = i
                break
        else:
            raise KeyError("No more EGRE keys available")

        return str(key)

  
       
                        
        

    def handle_peer(self, site, slice, persons, peer):
        if peer:
            # bind site
            try:
                if site:
                    self.driver.BindObjectToPeer('site', site['site_id'], peer['shortname'], slice['site_id'])
            except Exception,e:
                self.driver.DeleteSite(site['site_id'])
                raise e
            
            # bind slice
            try:
                if slice:
                    self.driver.BindObjectToPeer('slice', slice['slice_id'], peer['shortname'], slice['slice_id'])
            except Exception,e:
                self.driver.DeleteSlice(slice['slice_id'])
                raise e 

            # bind persons
            for person in persons:
                try:
                    self.driver.BindObjectToPeer('person', 
                                                     person['person_id'], peer['shortname'], person['peer_person_id'])

                    for (key, remote_key_id) in zip(person['keys'], person['key_ids']):
                        try:
                            self.driver.BindObjectToPeer( 'key', key['key_id'], peer['shortname'], remote_key_id)
                        except:
                            self.driver.DeleteKey(key['key_id'])
                            logger("failed to bind key: %s to peer: %s " % (key['key_id'], peer['shortname']))
                except Exception,e:
                    self.driver.DeletePerson(person['person_id'])
                    raise e       

        return slice

    #def verify_site(self, slice_xrn, slice_record={}, peer=None, sfa_peer=None, options={}):
        #(slice_hrn, type) = urn_to_hrn(slice_xrn)
        #site_hrn = get_authority(slice_hrn)
        ## login base can't be longer than 20 characters
        ##slicename = hrn_to_pl_slicename(slice_hrn)
        #authority_name = slice_hrn.split('.')[0]
        #login_base = authority_name[:20]
        #print >>sys.stderr, " \r\n \r\n \t\t SLABSLICES.PY verify_site authority_name %s  login_base %s slice_hrn %s" %(authority_name,login_base,slice_hrn)
        
        #sites = self.driver.GetSites(login_base)
        #if not sites:
            ## create new site record
            #site = {'name': 'geni.%s' % authority_name,
                    #'abbreviated_name': authority_name,
                    #'login_base': login_base,
                    #'max_slices': 100,
                    #'max_slivers': 1000,
                    #'enabled': True,
                    #'peer_site_id': None}
            #if peer:
                #site['peer_site_id'] = slice_record.get('site_id', None)
            #site['site_id'] = self.driver.AddSite(site)
            ## exempt federated sites from monitor policies
            #self.driver.AddSiteTag(site['site_id'], 'exempt_site_until', "20200101")
            
            ### is this still necessary?
            ### add record to the local registry 
            ##if sfa_peer and slice_record:
                ##peer_dict = {'type': 'authority', 'hrn': site_hrn, \
                             ##'peer_authority': sfa_peer, 'pointer': site['site_id']}
                ##self.registry.register_peer_object(self.credential, peer_dict)
        #else:
            #site =  sites[0]
            #if peer:
                ## unbind from peer so we can modify if necessary. Will bind back later
                #self.driver.UnBindObjectFromPeer('site', site['site_id'], peer['shortname']) 
        
        #return site        

    def verify_slice(self, slice_hrn, slice_record, peer, sfa_peer, options={} ):

        login_base = slice_hrn.split(".")[0]
        slicename = slice_hrn
        sl = self.driver.GetSlices(slice_filter=slicename, filter_type = 'slice_hrn') 
        if sl:

            print>>sys.stderr, " \r\n \r\rn Slices.py verify_slice slicename %s sl %s slice_record %s"%(slicename ,sl, slice_record)
            slice = sl
            slice.update(slice_record)
            #del slice['last_updated']
            #del slice['date_created']
            #if peer:
                #slice['peer_slice_id'] = slice_record.get('slice_id', None)
                ## unbind from peer so we can modify if necessary. Will bind back later
                #self.driver.UnBindObjectFromPeer('slice', slice['slice_id'], peer['shortname'])
	        #Update existing record (e.g. expires field) it with the latest info.
            ##if slice_record and slice['expires'] != slice_record['expires']:
                ##self.driver.UpdateSlice( slice['slice_id'], {'expires' : slice_record['expires']})
        else:
            print>>sys.stderr, " \r\n \r\rn Slices.py verify_slice UH-Oh...slice_record %s peer %s sfa_peer %s "%(slice_record, peer,sfa_peer)
            slice = {'slice_hrn': slicename,
                     #'url': slice_record.get('url', slice_hrn), 
                     #'description': slice_record.get('description', slice_hrn)
                     'node_list' : [],
                     'record_id_user' : slice_record['person_ids'][0],
                     'record_id_slice': slice_record['record_id'],
                     'peer_authority':str(peer.hrn)
                    
                     }
            # add the slice  
            self.driver.AddSlice(slice)                         
            #slice['slice_id'] = self.driver.AddSlice(slice)
            print>>sys.stderr, " \r\n \r\rn Slices.py verify_slice ADDSLICE OHYEEEEEEEEEEAH! " 
            #slice['node_ids']=[]
            #slice['person_ids'] = []
            #if peer:
                #slice['peer_slice_id'] = slice_record.get('slice_id', None) 
            # mark this slice as an sfa peer record
            #if sfa_peer:
                #peer_dict = {'type': 'slice', 'hrn': slice_hrn, 
                             #'peer_authority': sfa_peer, 'pointer': slice['slice_id']}
                #self.registry.register_peer_object(self.credential, peer_dict)
            

       
        return slice


    def verify_persons(self, slice_hrn, slice_record, users,  peer, sfa_peer, options={}):
        users_by_id = {}
        users_by_hrn = {}
        users_dict = {}
      
        for user in users:
            
            if 'urn' in user and (not 'hrn' in user ) :
                user['hrn'],user['type'] = urn_to_hrn(user['urn'])
               
            if 'person_id' in user and 'hrn' in user:
                users_by_id[user['person_id']] = user
                users_dict[user['person_id']] = {'person_id':user['person_id'], 'hrn':user['hrn']}

                users_by_hrn[user['hrn']] = user
                users_dict[user['hrn']] = {'person_id':user['person_id'], 'hrn':user['hrn']}
                
        print>>sys.stderr, " \r\n \r\n \t slabslices.py verify_person  users_dict %s \r\n user_by_hrn %s \r\n \tusers_by_id %s " %( users_dict,users_by_hrn, users_by_id) 
        
        existing_user_ids = []
        existing_user_hrns = []
        existing_users= []
        #Check if user is in LDAP using its hrn.
        #Assuming Senslab is centralised :  one LDAP for all sites, user_id unknown from LDAP
        # LDAP does not provide users id, therfore we rely on hrns
        if users_by_hrn:            
            existing_users = self.driver.GetPersons({'hrn': users_by_hrn.keys()})
            #existing_users = self.driver.GetPersons({'hrn': users_by_hrn.keys()}, 
                                                        #['hrn','pkey'])
            if existing_users:
                for user in existing_users :
                    #for  k in users_dict[user['hrn']] :
                    existing_user_hrns.append (users_dict[user['hrn']]['hrn'])
                    existing_user_ids.append (users_dict[user['hrn']]['person_id'])
                    #print>>sys.stderr, " \r\n \r\n \t slabslices.py verify_person  existing_user_ids.append (users_dict[user['hrn']][k]) %s \r\n existing_users %s " %(  existing_user_ids,existing_users) 
         
            #User from another federated site , does not have a senslab account yet?
            #or have multiple SFA accounts
            #Check before adding  them to LDAP
            
            else: 
                ldap_reslt = self.driver.ldap.ldapSearch(users)
                print>>sys.stderr, " \r\n \r\n \t slabslices.py verify_person users HUMHUMHUMHUM ... %s \r\n \t ldap_reslt %s "  %(users, ldap_reslt)
                pass
                
        # requested slice users        
        requested_user_ids = users_by_id.keys() 
        requested_user_hrns = users_by_hrn.keys()
        print>>sys.stderr, " \r\n \r\n \t slabslices.py verify_person  requested_user_ids  %s user_by_hrn %s " %( requested_user_ids,users_by_hrn) 
        # existing slice users
        existing_slice_users_filter = {'hrn': slice_record.get('PI', [])}
        print>>sys.stderr, " \r\n \r\n slices.py verify_person requested_user_ids %s existing_slice_users_filter %s slice_record %s" %(requested_user_ids,existing_slice_users_filter,slice_record)
        
        existing_slice_users = self.driver.GetPersons(existing_slice_users_filter)
        #existing_slice_users = self.driver.GetPersons(existing_slice_users_filter,['hrn','pkey'])
        print>>sys.stderr, " \r\n \r\n slices.py verify_person   existing_slice_users %s " %(existing_slice_users)

        existing_slice_user_hrns = [user['hrn'] for user in existing_slice_users]

        #print>>sys.stderr, " \r\n \r\n slices.py verify_person requested_user_ids %s  existing_slice_user_hrns %s " %(requested_user_ids,existing_slice_user_hrns)
        # users to be added, removed or updated

        added_user_hrns = set(requested_user_hrns).difference(set(existing_user_hrns))

        added_slice_user_hrns = set(requested_user_hrns).difference(existing_slice_user_hrns)
        
        removed_user_hrns = set(existing_slice_user_hrns).difference(requested_user_hrns)
        

        updated_user_hrns = set(existing_slice_user_hrns).intersection(requested_user_hrns)
        #print>>sys.stderr, " \r\n \r\n slices.py verify_persons  added_user_ids %s added_slice_user_ids %s " %(added_user_ids,added_slice_user_ids)
        #print>>sys.stderr, " \r\n \r\n slices.py verify_persons  removed_user_hrns %s updated_user_hrns %s " %(removed_user_hrns,updated_user_hrns)
        # Remove stale users (only if we are not appending) 
        append = options.get('append', True)
        if append == False:
            for removed_user_hrn in removed_user_hrns:
                self.driver.DeletePersonFromSlice(removed_user_hrn, slice_record['name'])
        # update_existing users
        updated_users_list = [user for user in existing_slice_users if user['hrn'] in \
          updated_user_hrns]
        #print>>sys.stderr, " \r\n \r\n slices.py verify_persons  removed_user_hrns %s updated_users_list %s " %(removed_user_hrns,updated_users_list) 
        #self.verify_keys(existing_slice_users, updated_users_list, peer, append)

        added_persons = []
        # add new users
        for added_user_hrn in added_user_hrns:
            added_user = users_dict[added_user_hrn]
            #hrn, type = urn_to_hrn(added_user['urn'])  
            person = {
                #'first_name': added_user.get('first_name', hrn),
                #'last_name': added_user.get('last_name', hrn),
                'person_id': added_user['person_id'],
                #'peer_person_id': None,
                #'keys': [],
                #'key_ids': added_user.get('key_ids', []),
                
            } 
            #print>>sys.stderr, " \r\n \r\n slices.py verify_persons   added_user_ids %s " %(added_user_ids)
            person['person_id'] = self.driver.AddPerson(person)
            if peer:
                person['peer_person_id'] = added_user['person_id']
            added_persons.append(person)
           
            # enable the account 
            self.driver.UpdatePerson(person['person_id'], {'enabled': True})
            
            # add person to site
            #self.driver.AddPersonToSite(added_user_id, login_base)

            #for key_string in added_user.get('keys', []):
                #key = {'key':key_string, 'key_type':'ssh'}
                #key['key_id'] = self.driver.AddPersonKey(person['person_id'], key)
                #person['keys'].append(key)

            # add the registry record
            #if sfa_peer:
                #peer_dict = {'type': 'user', 'hrn': hrn, 'peer_authority': sfa_peer, \
                    #'pointer': person['person_id']}
                #self.registry.register_peer_object(self.credential, peer_dict)
        for added_slice_user_hrn in added_slice_user_hrns.union(added_user_hrns):           
            self.driver.AddPersonToSlice(added_slice_user_hrn, slice_record['name'])
        #for added_slice_user_id in added_slice_user_ids.union(added_user_ids):
            # add person to the slice 
            #self.driver.AddPersonToSlice(added_slice_user_id, slice_record['name'])
            # if this is a peer record then it should already be bound to a peer.
            # no need to return worry about it getting bound later 

        return added_persons
            

    def verify_keys(self, persons, users, peer, options={}):
        # existing keys 
        key_ids = []
        for person in persons:
            key_ids.extend(person['key_ids'])
        keylist = self.driver.GetKeys(key_ids, ['key_id', 'key'])
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
                            self.driver.UnBindObjectFromPeer('person', person['person_id'], peer['shortname'])
                        key['key_id'] = self.driver.AddPersonKey(user['email'], key)
                        if peer:
                            key_index = user_keys.index(key['key'])
                            remote_key_id = user['key_ids'][key_index]
                            self.driver.BindObjectToPeer('key', key['key_id'], peer['shortname'], remote_key_id)
                            
                    finally:
                        if peer:
                            self.driver.BindObjectToPeer('person', person['person_id'], peer['shortname'], user['person_id'])
        
        # remove old keys (only if we are not appending)
        if append == False: 
            removed_keys = set(existing_keys).difference(requested_keys)
            for existing_key_id in keydict:
                if keydict[existing_key_id] in removed_keys:
                    try:
                        if peer:
                            self.driver.UnBindObjectFromPeer('key', existing_key_id, peer['shortname'])
                        self.driver.DeleteKey(existing_key_id)
                    except:
                        pass   

    #def verify_slice_attributes(self, slice, requested_slice_attributes, append=False, admin=False):
        ## get list of attributes users ar able to manage
        #filter = {'category': '*slice*'}
        #if not admin:
            #filter['|roles'] = ['user']
        #slice_attributes = self.driver.GetTagTypes(filter)
        #valid_slice_attribute_names = [attribute['tagname'] for attribute in slice_attributes]

        ## get sliver attributes
        #added_slice_attributes = []
        #removed_slice_attributes = []
        #ignored_slice_attribute_names = []
        #existing_slice_attributes = self.driver.GetSliceTags({'slice_id': slice['slice_id']})

        ## get attributes that should be removed
        #for slice_tag in existing_slice_attributes:
            #if slice_tag['tagname'] in ignored_slice_attribute_names:
                ## If a slice already has a admin only role it was probably given to them by an
                ## admin, so we should ignore it.
                #ignored_slice_attribute_names.append(slice_tag['tagname'])
            #else:
                ## If an existing slice attribute was not found in the request it should
                ## be removed
                #attribute_found=False
                #for requested_attribute in requested_slice_attributes:
                    #if requested_attribute['name'] == slice_tag['tagname'] and \
                       #requested_attribute['value'] == slice_tag['value']:
                        #attribute_found=True
                        #break

            #if not attribute_found and not append:
                #removed_slice_attributes.append(slice_tag)
        
        ## get attributes that should be added:
        #for requested_attribute in requested_slice_attributes:
            ## if the requested attribute wasn't found  we should add it
            #if requested_attribute['name'] in valid_slice_attribute_names:
                #attribute_found = False
                #for existing_attribute in existing_slice_attributes:
                    #if requested_attribute['name'] == existing_attribute['tagname'] and \
                       #requested_attribute['value'] == existing_attribute['value']:
                        #attribute_found=True
                        #break
                #if not attribute_found:
                    #added_slice_attributes.append(requested_attribute)


        ## remove stale attributes
        #for attribute in removed_slice_attributes:
            #try:
                #self.driver.DeleteSliceTag(attribute['slice_tag_id'])
            #except Exception, e:
                #self.logger.warn('Failed to remove sliver attribute. name: %s, value: %s, node_id: %s\nCause:%s'\
                                #% (name, value,  node_id, str(e)))

        ## add requested_attributes
        #for attribute in added_slice_attributes:
            #try:
                #self.driver.AddSliceTag(slice['name'], attribute['name'], attribute['value'], attribute.get('node_id', None))
            #except Exception, e:
                #self.logger.warn('Failed to add sliver attribute. name: %s, value: %s, node_id: %s\nCause:%s'\
                                #% (name, value,  node_id, str(e)))

    #def create_slice_aggregate(self, xrn, rspec):
        #hrn, type = urn_to_hrn(xrn)
        ## Determine if this is a peer slice
        #peer = self.get_peer(hrn)
        #sfa_peer = self.get_sfa_peer(hrn)

        #spec = RSpec(rspec)
        ## Get the slice record from sfa
        #slicename = hrn_to_pl_slicename(hrn) 
        #slice = {}
        #slice_record = None
        #registry = self.api.registries[self.api.hrn]
        #credential = self.api.getCredential()

        #site_id, remote_site_id = self.verify_site(registry, credential, hrn, peer, sfa_peer)
        #slice = self.verify_slice(registry, credential, hrn, site_id, remote_site_id, peer, sfa_peer)

        ## find out where this slice is currently running
        #nodelist = self.driver.GetNodes(slice['node_ids'], ['hostname'])
        #hostnames = [node['hostname'] for node in nodelist]

        ## get netspec details
        #nodespecs = spec.getDictsByTagName('NodeSpec')

        ## dict in which to store slice attributes to set for the nodes
        #nodes = {}
        #for nodespec in nodespecs:
            #if isinstance(nodespec['name'], list):
                #for nodename in nodespec['name']:
                    #nodes[nodename] = {}
                    #for k in nodespec.keys():
                        #rspec_attribute_value = nodespec[k]
                        #if (self.rspec_to_slice_tag.has_key(k)):
                            #slice_tag_name = self.rspec_to_slice_tag[k]
                            #nodes[nodename][slice_tag_name] = rspec_attribute_value
            #elif isinstance(nodespec['name'], StringTypes):
                #nodename = nodespec['name']
                #nodes[nodename] = {}
                #for k in nodespec.keys():
                    #rspec_attribute_value = nodespec[k]
                    #if (self.rspec_to_slice_tag.has_key(k)):
                        #slice_tag_name = self.rspec_to_slice_tag[k]
                        #nodes[nodename][slice_tag_name] = rspec_attribute_value

                #for k in nodespec.keys():
                    #rspec_attribute_value = nodespec[k]
                    #if (self.rspec_to_slice_tag.has_key(k)):
                        #slice_tag_name = self.rspec_to_slice_tag[k]
                        #nodes[nodename][slice_tag_name] = rspec_attribute_value

        #node_names = nodes.keys()
        ## remove nodes not in rspec
        #deleted_nodes = list(set(hostnames).difference(node_names))
        ## add nodes from rspec
        #added_nodes = list(set(node_names).difference(hostnames))

        #try:
            #if peer:
                #self.driver.UnBindObjectFromPeer('slice', slice['slice_id'], peer)

            #self.driver.LaunchExperimentOnOAR(slicename, added_nodes) 

            ## Add recognized slice tags
            #for node_name in node_names:
                #node = nodes[node_name]
                #for slice_tag in node.keys():
                    #value = node[slice_tag]
                    #if (isinstance(value, list)):
                        #value = value[0]

                    #self.driver.AddSliceTag(slicename, slice_tag, value, node_name)

            #self.driver.DeleteSliceFromNodes(slicename, deleted_nodes)
        #finally:
            #if peer:
                #self.driver.BindObjectToPeer('slice', slice['slice_id'], peer, slice['peer_slice_id'])

        #return 1

