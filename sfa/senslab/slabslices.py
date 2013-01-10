from sfa.util.xrn import get_authority, urn_to_hrn
from sfa.util.sfalogging import logger


MAXINT =  2L**31-1

class SlabSlices:

    rspec_to_slice_tag = {'max_rate':'net_max_rate'}
    
    
    def __init__(self, driver):
        self.driver = driver
        
    
    def get_peer(self, xrn):
        hrn, hrn_type = urn_to_hrn(xrn)
        #Does this slice belong to a local site or a peer senslab site?
        peer = None
        
        # get this slice's authority (site)
        slice_authority = get_authority(hrn)
        site_authority = slice_authority
        # get this site's authority (sfa root authority or sub authority)
        #site_authority = get_authority(slice_authority).lower()
        logger.debug("SLABSLICES \ get_peer slice_authority  %s \
                    site_authority %s hrn %s" %(slice_authority, \
                                        site_authority, hrn))
        #This slice belongs to the current site
        if site_authority == self.driver.root_auth :
            return None
        # check if we are already peered with this site_authority, if so
        #peers = self.driver.GetPeers({})  
        peers = self.driver.GetPeers(peer_filter = slice_authority)
        for peer_record in peers:
          
            if site_authority == peer_record.hrn:
                peer = peer_record
        logger.debug(" SLABSLICES \tget_peer peer  %s " %(peer))
        return peer

    def get_sfa_peer(self, xrn):
        hrn, hrn_type = urn_to_hrn(xrn)

        # return the authority for this hrn or None if we are the authority
        sfa_peer = None
        slice_authority = get_authority(hrn)
        site_authority = get_authority(slice_authority)

        if site_authority != self.driver.hrn:
            sfa_peer = site_authority

        return sfa_peer

        
    def verify_slice_leases(self, sfa_slice, requested_jobs_dict, peer):

        logger.debug("SLABSLICES verify_slice_leases sfa_slice %s \
                        "%( sfa_slice))
        #First get the list of current leases from OAR          
        leases = self.driver.GetLeases({'name':sfa_slice['hrn']})
        logger.debug("SLABSLICES verify_slice_leases requested_jobs_dict %s \
                        leases %s "%(requested_jobs_dict, leases ))
        
        current_nodes_reserved_by_start_time = {}
        requested_nodes_by_start_time = {}
        leases_by_start_time = {}
        reschedule_jobs_dict = {}

        
        #Create reduced dictionary with key start_time and value 
        # the list of nodes
        #-for the leases already registered by OAR first
        # then for the new leases requested by the user
        
        #Leases already scheduled/running in OAR
        for lease in leases :
            current_nodes_reserved_by_start_time[lease['t_from']] = \
                    lease['reserved_nodes']
            leases_by_start_time[lease['t_from']] = lease
            
        
        #Requested jobs     
        for start_time in requested_jobs_dict:
            requested_nodes_by_start_time[int(start_time)]  = \
                    requested_jobs_dict[start_time]['hostname']            
        #Check if there is any difference between the leases already
        #registered in OAR and the requested jobs.   
        #Difference could be:
        #-Lease deleted in the requested jobs
        #-Added/removed nodes
        #-Newly added lease 

        logger.debug("SLABSLICES verify_slice_leases \
                        requested_nodes_by_start_time %s \
                        "%(requested_nodes_by_start_time ))
        #Find all deleted leases
        start_time_list = \
            list(set(leases_by_start_time.keys()).\
            difference(requested_nodes_by_start_time.keys()))
        deleted_leases = [leases_by_start_time[start_time]['lease_id'] \
                            for start_time in start_time_list]


            
        #Find added or removed nodes in exisiting leases
        for start_time in requested_nodes_by_start_time: 
            logger.debug("SLABSLICES verify_slice_leases  start_time %s \
                         "%( start_time))
            if start_time in current_nodes_reserved_by_start_time:
                
                if requested_nodes_by_start_time[start_time] == \
                    current_nodes_reserved_by_start_time[start_time]:
                    continue
                
                else:
                    update_node_set = \
                            set(requested_nodes_by_start_time[start_time])
                    added_nodes = \
                        update_node_set.difference(\
                        current_nodes_reserved_by_start_time[start_time])
                    shared_nodes = \
                        update_node_set.intersection(\
                        current_nodes_reserved_by_start_time[start_time])
                    old_nodes_set = \
                        set(\
                        current_nodes_reserved_by_start_time[start_time])
                    removed_nodes = \
                        old_nodes_set.difference(\
                        requested_nodes_by_start_time[start_time])
                    logger.debug("SLABSLICES verify_slice_leases \
                        shared_nodes %s  added_nodes %s removed_nodes %s"\
                        %(shared_nodes, added_nodes,removed_nodes ))
                    #If the lease is modified, delete it before 
                    #creating it again.
                    #Add the deleted lease job id in the list
                    #WARNING :rescheduling does not work if there is already  
                    # 2 running/scheduled jobs because deleting a job 
                    #takes time SA 18/10/2012
                    if added_nodes or removed_nodes:
                        deleted_leases.append(\
                            leases_by_start_time[start_time]['lease_id'])
                        #Reschedule the job 
                        if added_nodes or shared_nodes:
                            reschedule_jobs_dict[str(start_time)] = \
                                        requested_jobs_dict[str(start_time)]

            else: 
                    #New lease
                    
                    job = requested_jobs_dict[str(start_time)]
                    logger.debug("SLABSLICES \
                    NEWLEASE slice %s  job %s"\
                    %(sfa_slice, job)) 
                    self.driver.AddLeases(job['hostname'], \
                            sfa_slice, int(job['start_time']), \
                            int(job['duration']))

        #Deleted leases are the ones with lease id not declared in the Rspec
        if deleted_leases:
            self.driver.DeleteLeases(deleted_leases, sfa_slice['hrn'])
            logger.debug("SLABSLICES \
                    verify_slice_leases slice %s deleted_leases %s"\
                    %(sfa_slice, deleted_leases))
                    
                    
        if reschedule_jobs_dict : 
            for start_time in  reschedule_jobs_dict:
                job = reschedule_jobs_dict[start_time]
                self.driver.AddLeases(job['hostname'], \
                    sfa_slice, int(job['start_time']), \
                    int(job['duration']))
        return leases

    def verify_slice_nodes(self, sfa_slice, requested_slivers, peer):
        current_slivers = []
        deleted_nodes = []

        if 'node_ids' in sfa_slice:
            nodes = self.driver.GetNodes(sfa_slice['list_node_ids'], \
                ['hostname'])
            current_slivers = [node['hostname'] for node in nodes]
    
            # remove nodes not in rspec
            deleted_nodes = list(set(current_slivers).\
                                                difference(requested_slivers))
            # add nodes from rspec
            #added_nodes = list(set(requested_slivers).\
                                        #difference(current_slivers))


            logger.debug("SLABSLICES \tverify_slice_nodes slice %s\
                                         \r\n \r\n deleted_nodes %s"\
                                        %(sfa_slice, deleted_nodes))

            if deleted_nodes:
                #Delete the entire experience
                self.driver.DeleteSliceFromNodes(sfa_slice)
                #self.driver.DeleteSliceFromNodes(sfa_slice['slice_hrn'], \
                                                                #deleted_nodes)
            return nodes

            

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

  
       
                        
        

    def handle_peer(self, site, sfa_slice, persons, peer):
        if peer:
            # bind site
            try:
                if site:
                    self.driver.BindObjectToPeer('site', site['site_id'], \
                                        peer['shortname'], sfa_slice['site_id'])
            except Exception, error:
                self.driver.DeleteSite(site['site_id'])
                raise error
            
            # bind slice
            try:
                if sfa_slice:
                    self.driver.BindObjectToPeer('slice', slice['slice_id'], \
                                    peer['shortname'], sfa_slice['slice_id'])
            except Exception, error:
                self.driver.DeleteSlice(sfa_slice['slice_id'])
                raise error 

            # bind persons
            for person in persons:
                try:
                    self.driver.BindObjectToPeer('person', \
                                    person['person_id'], peer['shortname'], \
                                    person['peer_person_id'])

                    for (key, remote_key_id) in zip(person['keys'], \
                                                        person['key_ids']):
                        try:
                            self.driver.BindObjectToPeer( 'key', \
                                            key['key_id'], peer['shortname'], \
                                            remote_key_id)
                        except:
                            self.driver.DeleteKey(key['key_id'])
                            logger.log_exc("failed to bind key: %s \
                                            to peer: %s " % (key['key_id'], \
                                            peer['shortname']))
                except Exception, error:
                    self.driver.DeletePerson(person['person_id'])
                    raise error       

        return sfa_slice

    #def verify_site(self, slice_xrn, slice_record={}, peer=None, \
                                        #sfa_peer=None, options={}):
        #(slice_hrn, type) = urn_to_hrn(slice_xrn)
        #site_hrn = get_authority(slice_hrn)
        ## login base can't be longer than 20 characters
        ##slicename = hrn_to_pl_slicename(slice_hrn)
        #authority_name = slice_hrn.split('.')[0]
        #login_base = authority_name[:20]
        #logger.debug(" SLABSLICES.PY \tverify_site authority_name %s  \
                                        #login_base %s slice_hrn %s" \
                                        #%(authority_name,login_base,slice_hrn)
        
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
            #self.driver.AddSiteTag(site['site_id'], 'exempt_site_until', \
                                                                #"20200101")
            
            ### is this still necessary?
            ### add record to the local registry 
            ##if sfa_peer and slice_record:
                ##peer_dict = {'type': 'authority', 'hrn': site_hrn, \
                             ##'peer_authority': sfa_peer, 'pointer': \
                                                        #site['site_id']}
                ##self.registry.register_peer_object(self.credential, peer_dict)
        #else:
            #site =  sites[0]
            #if peer:
                ## unbind from peer so we can modify if necessary.
                ## Will bind back later
                #self.driver.UnBindObjectFromPeer('site', site['site_id'], \
                                                            #peer['shortname']) 
        
        #return site        

    def verify_slice(self, slice_hrn, slice_record, peer, sfa_peer):

        #login_base = slice_hrn.split(".")[0]
        slicename = slice_hrn
        slices_list = self.driver.GetSlices(slice_filter = slicename, \
                                            slice_filter_type = 'slice_hrn') 
        sfa_slice = None                                 
        if slices_list:
            for sl in slices_list:
            
                logger.debug("SLABSLICE \tverify_slice slicename %s slices_list %s sl %s \
                                    slice_record %s"%(slicename, slices_list,sl, \
                                                            slice_record))
                sfa_slice = sl
                sfa_slice.update(slice_record)
                #del slice['last_updated']
                #del slice['date_created']
                #if peer:
                    #slice['peer_slice_id'] = slice_record.get('slice_id', None)
                    ## unbind from peer so we can modify if necessary. 
                    ## Will bind back later
                    #self.driver.UnBindObjectFromPeer('slice', \
                                                        #slice['slice_id'], \
                                                            #peer['shortname'])
                #Update existing record (e.g. expires field) 
                    #it with the latest info.
                ##if slice_record and slice['expires'] != slice_record['expires']:
                    ##self.driver.UpdateSlice( slice['slice_id'], {'expires' : \
                                                        #slice_record['expires']})
        else:
            #Search for user in ldap based on email SA 14/11/12
            ldap_user = self.driver.ldap.LdapFindUser(slice_record['user'])
            logger.debug(" SLABSLICES \tverify_slice Oups \
                        slice_record %s peer %s sfa_peer %s ldap_user %s"\
                        %(slice_record, peer,sfa_peer ,ldap_user ))
            #User already registered in ldap, meaning user should be in SFA db
            #and hrn = sfa_auth+ uid           
            if ldap_user : 
                hrn = self.driver.root_auth +'.'+ ldap_user['uid']
                
                user = self.driver.get_user(hrn)
                
                logger.debug(" SLABSLICES \tverify_slice hrn %s USER %s" %(hrn, user))
                sfa_slice = {'slice_hrn': slicename,
                     #'url': slice_record.get('url', slice_hrn), 
                     #'description': slice_record.get('description', slice_hrn)
                     'node_list' : [],
                     'authority' : slice_record['authority'],
                     'gid':slice_record['gid'],
                     #'record_id_user' : user.record_id,
                     'slice_id' : slice_record['record_id'],
                     'reg-researchers':slice_record['reg-researchers'],
                     #'record_id_slice': slice_record['record_id'],
                     'peer_authority':str(peer.hrn)
                    
                     }
                     
                if peer:
                    sfa_slice['slice_id'] = slice_record['record_id']
            # add the slice  
            if sfa_slice:
                self.driver.AddSlice(sfa_slice, user)                         
            #slice['slice_id'] = self.driver.AddSlice(slice)
            logger.debug("SLABSLICES \tverify_slice ADDSLICE OK") 
            #slice['node_ids']=[]
            #slice['person_ids'] = []
            #if peer:
                #sfa_slice['peer_slice_id'] = slice_record.get('slice_id', None) 
            # mark this slice as an sfa peer record
            #if sfa_peer:
                #peer_dict = {'type': 'slice', 'hrn': slice_hrn, 
                             #'peer_authority': sfa_peer, 'pointer': \
                                                    #slice['slice_id']}
                #self.registry.register_peer_object(self.credential, peer_dict)
            

       
        return sfa_slice


    def verify_persons(self, slice_hrn, slice_record, users,  peer, sfa_peer, \
                                                                options={}):
        """ 
        users is a record list. Records can either be local records 
        or users records from known and trusted federated sites. 
        If the user is from another site that senslab doesn't trust yet,
        then Resolve will raise an error before getting to create_sliver. 
        """
        #TODO SA 21/08/12 verify_persons Needs review 
        
        logger.debug("SLABSLICES \tverify_persons \tslice_hrn  %s  \t slice_record %s\r\n users %s \t peer %s "%( slice_hrn, slice_record, users,  peer)) 
        users_by_id = {}  
        #users_by_hrn = {} 
        users_by_email = {}
        #users_dict : dict whose keys can either be the user's hrn or its id.
        #Values contains only id and hrn 
        users_dict = {}
        
        #First create dicts by hrn and id for each user in the user record list:      
        for info in users:
            
            if 'slice_record' in info :
                slice_rec = info['slice_record'] 
                user = slice_rec['user']

            if 'email' in user:  
                users_by_email[user['email']] = user
                users_dict[user['email']] = user
                
            #if 'hrn' in user:
                #users_by_hrn[user['hrn']] = user
                #users_dict[user['hrn']] = user
        
        logger.debug( "SLABSLICE.PY \t verify_person  \
                        users_dict %s \r\n user_by_email %s \r\n \
                        \tusers_by_id %s " \
                        %(users_dict,users_by_email, users_by_id))
        
        existing_user_ids = []
        #existing_user_hrns = []
        existing_user_emails = []
        existing_users = []
        # Check if user is in Senslab LDAP using its hrn.
        # Assuming Senslab is centralised :  one LDAP for all sites, 
        # user_id unknown from LDAP
        # LDAP does not provide users id, therefore we rely on hrns containing
        # the login of the user.
        # If the hrn is not a senslab hrn, the user may not be in LDAP.
        #if users_by_hrn:
        if users_by_email :
            #Construct the list of filters (list of dicts) for GetPersons
            filter_user = []
            #for hrn in users_by_hrn:
            for email in users_by_email :
                #filter_user.append (users_by_hrn[hrn])
                filter_user.append (users_by_email[email])
            #Check user's in LDAP with GetPersons
            #Needed because what if the user has been deleted in LDAP but 
            #is still in SFA?
            existing_users = self.driver.GetPersons(filter_user) 
            logger.debug(" \r\n SLABSLICE.PY \tverify_person  filter_user %s existing_users %s " \
                                                    %(filter_user, existing_users))               
            #User's in senslab LDAP               
            if existing_users:
                for user in existing_users :
                    users_dict[user['email']].update(user)
                    existing_user_emails.append(users_dict[user['email']]['email'])
                    
                    #existing_user_hrns.append(users_dict[user['hrn']]['hrn'])
                    #existing_user_ids.\
                                    #append(users_dict[user['hrn']]['person_id'])
         
            # User from another known trusted federated site. Check 
            # if a senslab account matching the email has already been created.
            else: 
                req = 'mail='
                if isinstance(users, list):
                    
                    req += users[0]['email']  
                else:
                    req += users['email']
                    
                ldap_reslt = self.driver.ldap.LdapSearch(req)
                if ldap_reslt:
                    logger.debug(" SLABSLICE.PY \tverify_person users \
                                USER already in Senslab \t ldap_reslt %s \
                                "%( ldap_reslt)) 
                    existing_users.append(ldap_reslt[1])
                 
                else:
                    #User not existing in LDAP
                    #TODO SA 21/08/12 raise smthg to add user or add it auto ?
                    #new_record = {}
                    #new_record['pkey'] = users[0]['keys'][0]
                    #new_record['mail'] = users[0]['email']
                  
                    logger.debug(" SLABSLICE.PY \tverify_person users \
                                not in ldap ...NEW ACCOUNT NEEDED %s \r\n \t \
                                ldap_reslt %s "  %(users, ldap_reslt))
   
        #requested_user_ids = users_by_id.keys() 
        #requested_user_hrns = users_by_hrn.keys()
        requested_user_emails = users_by_email.keys()
        logger.debug("SLABSLICE.PY \tverify_person  \
                       users_by_email  %s " %( users_by_email)) 
        #logger.debug("SLABSLICE.PY \tverify_person  \
                        #user_by_hrn %s " %( users_by_hrn)) 
      
   
        #Check that the user of the slice in the slice record
        #matches the existing users 
        try:
            if slice_record['PI'][0] in requested_user_hrns:
            #if slice_record['record_id_user'] in requested_user_ids and \
                                #slice_record['PI'][0] in requested_user_hrns:
                logger.debug(" SLABSLICE  \tverify_person ['PI'] slice_record %s" \
                        %(slice_record))
           
        except KeyError:
            pass
            
      
        # users to be added, removed or updated
        #One user in one senslab slice : there should be no need
        #to remove/ add any user from/to a slice.
        #However a user from SFA which is not registered in Senslab yet
        #should be added to the LDAP.
        added_user_emails = set(requested_user_emails).\
                                            difference(set(existing_user_emails))
        #added_user_hrns = set(requested_user_hrns).\
                                            #difference(set(existing_user_hrns))

        #self.verify_keys(existing_slice_users, updated_users_list, \
                                                            #peer, append)

        added_persons = []
        # add new users
        
        #requested_user_email is in existing_user_emails
        if len(added_user_emails) == 0:
           
            slice_record['login'] = users_dict[requested_user_emails[0]]['uid']
            logger.debug(" SLABSLICE  \tverify_person QUICK DIRTY %s" \
                        %(slice_record))
            
        #for added_user_hrn in added_user_hrns:
            #added_user = users_dict[added_user_hrn]
            
            
        for added_user_email in added_user_emails:
            #hrn, type = urn_to_hrn(added_user['urn'])  
            added_user = users_dict[added_user_email]
            logger.debug(" SLABSLICE \r\n \r\n  \t THE SECOND verify_person  added_user %s" %(added_user))
            person = {}
            person['peer_person_id'] =  None
            k_list  = ['first_name','last_name','person_id']
            for k in k_list:
                if k in added_user:
                    person[k] = added_user[k]

            person['pkey'] = added_user['keys'][0]
            person['mail'] = added_user['email']
            person['email'] = added_user['email']
            person['key_ids'] =  added_user.get('key_ids', [])
            #person['urn'] =   added_user['urn']
              
            #person['person_id'] = self.driver.AddPerson(person)
            person['uid'] = self.driver.AddPerson(person)
            
            logger.debug(" SLABSLICE \r\n \r\n  \t THE SECOND verify_person ppeersonne  %s" %(person))
            #Update slice_Record with the id now known to LDAP
            slice_record['login'] = person['uid']
            #slice_record['reg_researchers'] = [self.driver.root_auth + '.' + person['uid']]
            #slice_record['reg-researchers'] =  slice_record['reg_researchers']
            
            #if peer:
                #person['peer_person_id'] = added_user['person_id']
            added_persons.append(person)
           
            # enable the account 
            #self.driver.UpdatePerson(slice_record['reg_researchers'][0], added_user_email)
            
            # add person to site
            #self.driver.AddPersonToSite(added_user_id, login_base)

            #for key_string in added_user.get('keys', []):
                #key = {'key':key_string, 'key_type':'ssh'}
                #key['key_id'] = self.driver.AddPersonKey(person['person_id'], \
                                                #                       key)
                #person['keys'].append(key)

            # add the registry record
            #if sfa_peer:
                #peer_dict = {'type': 'user', 'hrn': hrn, 'peer_authority': \
                                                #sfa_peer, \
                                                #'pointer': person['person_id']}
                #self.registry.register_peer_object(self.credential, peer_dict)
        #for added_slice_user_hrn in \
                                #added_slice_user_hrns.union(added_user_hrns):
            #self.driver.AddPersonToSlice(added_slice_user_hrn, \
                                                    #slice_record['name'])
        #for added_slice_user_id in \
                                    #added_slice_user_ids.union(added_user_ids):
            # add person to the slice 
            #self.driver.AddPersonToSlice(added_slice_user_id, \
                                                #slice_record['name'])
            # if this is a peer record then it 
            # should already be bound to a peer.
            # no need to return worry about it getting bound later 

        return added_persons
            
    #Unused
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
                            self.driver.UnBindObjectFromPeer('person', \
                                        person['person_id'], peer['shortname'])
                        key['key_id'] = \
                                self.driver.AddPersonKey(user['email'], key)
                        if peer:
                            key_index = user_keys.index(key['key'])
                            remote_key_id = user['key_ids'][key_index]
                            self.driver.BindObjectToPeer('key', \
                                            key['key_id'], peer['shortname'], \
                                            remote_key_id)
                            
                    finally:
                        if peer:
                            self.driver.BindObjectToPeer('person', \
                                    person['person_id'], peer['shortname'], \
                                    user['person_id'])
        
        # remove old keys (only if we are not appending)
        append = options.get('append', True)
        if append == False: 
            removed_keys = set(existing_keys).difference(requested_keys)
            for existing_key_id in keydict:
                if keydict[existing_key_id] in removed_keys:

                    if peer:
                        self.driver.UnBindObjectFromPeer('key', \
                                        existing_key_id, peer['shortname'])
                    self.driver.DeleteKey(existing_key_id)
 

    #def verify_slice_attributes(self, slice, requested_slice_attributes, \
                                            #append=False, admin=False):
        ## get list of attributes users ar able to manage
        #filter = {'category': '*slice*'}
        #if not admin:
            #filter['|roles'] = ['user']
        #slice_attributes = self.driver.GetTagTypes(filter)
        #valid_slice_attribute_names = [attribute['tagname'] \
                                            #for attribute in slice_attributes]

        ## get sliver attributes
        #added_slice_attributes = []
        #removed_slice_attributes = []
        #ignored_slice_attribute_names = []
        #existing_slice_attributes = self.driver.GetSliceTags({'slice_id': \
                                                            #slice['slice_id']})

        ## get attributes that should be removed
        #for slice_tag in existing_slice_attributes:
            #if slice_tag['tagname'] in ignored_slice_attribute_names:
                ## If a slice already has a admin only role 
                ## it was probably given to them by an
                ## admin, so we should ignore it.
                #ignored_slice_attribute_names.append(slice_tag['tagname'])
            #else:
                ## If an existing slice attribute was not 
                ## found in the request it should
                ## be removed
                #attribute_found=False
                #for requested_attribute in requested_slice_attributes:
                    #if requested_attribute['name'] == slice_tag['tagname'] \
                        #and requested_attribute['value'] == slice_tag['value']:
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
                    #if requested_attribute['name'] == \
                        #existing_attribute['tagname'] and \
                       #requested_attribute['value'] == \
                       #existing_attribute['value']:
                        #attribute_found=True
                        #break
                #if not attribute_found:
                    #added_slice_attributes.append(requested_attribute)


        ## remove stale attributes
        #for attribute in removed_slice_attributes:
            #try:
                #self.driver.DeleteSliceTag(attribute['slice_tag_id'])
            #except Exception, error:
                #self.logger.warn('Failed to remove sliver attribute. name: \
                                #%s, value: %s, node_id: %s\nCause:%s'\
                                #% (name, value,  node_id, str(error)))

        ## add requested_attributes
        #for attribute in added_slice_attributes:
            #try:
                #self.driver.AddSliceTag(slice['name'], attribute['name'], \
                            #attribute['value'], attribute.get('node_id', None))
            #except Exception, error:
                #self.logger.warn('Failed to add sliver attribute. name: %s, \
                                #value: %s, node_id: %s\nCause:%s'\
                                #% (name, value,  node_id, str(error)))

 
