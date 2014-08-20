"""
This file defines the IotlabSlices class by which all the slice checkings
upon lease creation are done.
"""
from sfa.util.xrn import get_authority, urn_to_hrn, hrn_to_urn
from sfa.util.sfalogging import logger

MAXINT = 2L**31-1


class IotlabSlices:
    """
    This class is responsible for checking the slice when creating a
    lease or a sliver. Those checks include verifying that the user is valid,
    that the slice is known from the testbed or from our peers, that the list
    of nodes involved has not changed (in this case the lease is modified
    accordingly).
    """
    rspec_to_slice_tag = {'max_rate': 'net_max_rate'}

    def __init__(self, driver):
        """
        Get the reference to the driver here.
        """
        self.driver = driver

    def get_peer(self, xrn):
        """
        Finds the authority of a resource based on its xrn.
        If the authority is Iotlab (local) return None,
        Otherwise, look up in the DB if Iotlab is federated with this site
        authority and returns its DB record if it is the case.

        :param xrn: resource's xrn
        :type xrn: string
        :returns: peer record
        :rtype: dict

        """
        hrn, hrn_type = urn_to_hrn(xrn)
        #Does this slice belong to a local site or a peer iotlab site?
        peer = None

        # get this slice's authority (site)
        slice_authority = get_authority(hrn)
        #Iotlab stuff
        #This slice belongs to the current site
        if slice_authority == self.driver.testbed_shell.root_auth:
            site_authority = slice_authority
            return None

        site_authority = get_authority(slice_authority).lower()
        # get this site's authority (sfa root authority or sub authority)

        logger.debug("IOTLABSLICES \t get_peer slice_authority  %s \
                    site_authority %s hrn %s"
                     % (slice_authority, site_authority, hrn))

        # check if we are already peered with this site_authority
        #if so find the peer record
        peers = self.driver.GetPeers(peer_filter=site_authority)
        for peer_record in peers:
            if site_authority == peer_record.hrn:
                peer = peer_record
        logger.debug(" IOTLABSLICES \tget_peer peer  %s " % (peer))
        return peer

    def get_sfa_peer(self, xrn):
        """Returns the authority name for the xrn or None if the local site
        is the authority.

        :param xrn: the xrn of the resource we are looking the authority for.
        :type xrn: string
        :returns: the resources's authority name.
        :rtype: string

        """
        hrn, hrn_type = urn_to_hrn(xrn)

        # return the authority for this hrn or None if we are the authority
        sfa_peer = None
        slice_authority = get_authority(hrn)
        site_authority = get_authority(slice_authority)

        if site_authority != self.driver.hrn:
            sfa_peer = site_authority

        return sfa_peer

    def verify_slice_leases(self, sfa_slice, requested_jobs_dict, peer):
        """
        Compare requested leases with the leases already scheduled/
        running in OAR. If necessary, delete and recreate modified leases,
        and delete no longer requested ones.

        :param sfa_slice: sfa slice record
        :param requested_jobs_dict: dictionary of requested leases
        :param peer: sfa peer record

        :type sfa_slice: dict
        :type requested_jobs_dict: dict
        :type peer: dict
        :returns: leases list of dictionary
        :rtype: list

        """

        logger.debug("IOTLABSLICES verify_slice_leases sfa_slice %s "
                     % (sfa_slice))
        #First get the list of current leases from OAR
        leases = self.driver.GetLeases({'slice_hrn': sfa_slice['hrn']})
        logger.debug("IOTLABSLICES verify_slice_leases requested_jobs_dict %s \
                        leases %s " % (requested_jobs_dict, leases))

        current_nodes_reserved_by_start_time = {}
        requested_nodes_by_start_time = {}
        leases_by_start_time = {}
        reschedule_jobs_dict = {}

        #Create reduced dictionary with key start_time and value
        # the list of nodes
        #-for the leases already registered by OAR first
        # then for the new leases requested by the user

        #Leases already scheduled/running in OAR
        for lease in leases:
            current_nodes_reserved_by_start_time[lease['t_from']] = \
                    lease['reserved_nodes']
            leases_by_start_time[lease['t_from']] = lease

        #First remove job whose duration is too short
        for job in requested_jobs_dict.values():
            job['duration'] = \
                str(int(job['duration']) \
                * self.driver.testbed_shell.GetLeaseGranularity())
            if job['duration'] < \
                    self.driver.testbed_shell.GetLeaseGranularity():
                del requested_jobs_dict[job['start_time']]

        #Requested jobs
        for start_time in requested_jobs_dict:
            requested_nodes_by_start_time[int(start_time)] = \
                requested_jobs_dict[start_time]['hostname']
        #Check if there is any difference between the leases already
        #registered in OAR and the requested jobs.
        #Difference could be:
        #-Lease deleted in the requested jobs
        #-Added/removed nodes
        #-Newly added lease

        logger.debug("IOTLABSLICES verify_slice_leases \
                        requested_nodes_by_start_time %s \
                        "% (requested_nodes_by_start_time))
        #Find all deleted leases
        start_time_list = \
            list(set(leases_by_start_time.keys()).\
            difference(requested_nodes_by_start_time.keys()))
        deleted_leases = [leases_by_start_time[start_time]['lease_id'] \
                            for start_time in start_time_list]


        #Find added or removed nodes in exisiting leases
        for start_time in requested_nodes_by_start_time:
            logger.debug("IOTLABSLICES verify_slice_leases  start_time %s \
                         "%( start_time))
            if start_time in current_nodes_reserved_by_start_time:

                # JORDAN : if we request the same nodes: do nothing
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
                    logger.debug("IOTLABSLICES verify_slice_leases \
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
                logger.debug("IOTLABSLICES \
                              NEWLEASE slice %s  job %s"
                             % (sfa_slice, job))
                job_id = self.driver.AddLeases(
                    job['hostname'],
                    sfa_slice, int(job['start_time']),
                    int(job['duration']))

                # Removed by jordan
                #if job_id is not None:
                #    new_leases = self.driver.GetLeases(login=
                #        sfa_slice['login'])
                #    for new_lease in new_leases:
                #        leases.append(new_lease)

        #Deleted leases are the ones with lease id not declared in the Rspec
        if deleted_leases:
            self.driver.testbed_shell.DeleteLeases(deleted_leases,
                                                sfa_slice['login'])
            #self.driver.testbed_shell.DeleteLeases(deleted_leases,
            #                                    sfa_slice['user']['uid'])
            logger.debug("IOTLABSLICES \
                          verify_slice_leases slice %s deleted_leases %s"
                         % (sfa_slice, deleted_leases))

        if reschedule_jobs_dict:
            for start_time in reschedule_jobs_dict:
                job = reschedule_jobs_dict[start_time]
                self.driver.AddLeases(
                    job['hostname'],
                    sfa_slice, int(job['start_time']),
                    int(job['duration']))

        # Added by Jordan: until we find a better solution, always update the list of leases
        return self.driver.GetLeases(login= sfa_slice['login'])
        #return leases

    def verify_slice_nodes(self, sfa_slice, requested_slivers, peer):
        """Check for wanted and unwanted nodes in the slice.

        Removes nodes and associated leases that the user does not want anymore
        by deleteing the associated job in OAR (DeleteSliceFromNodes).
        Returns the nodes' hostnames that are going to be in the slice.

        :param sfa_slice: slice record. Must contain node_ids and list_node_ids.

        :param requested_slivers: list of requested nodes' hostnames.
        :param peer: unused so far.

        :type sfa_slice: dict
        :type requested_slivers: list
        :type peer: string

        :returns: list requested nodes hostnames
        :rtype: list

        .. warning:: UNUSED SQA 24/07/13
        .. seealso:: DeleteSliceFromNodes
        .. todo:: check what to do with the peer? Can not remove peer nodes from
            slice here. Anyway, in this case, the peer should have gotten the
            remove request too.

        """
        current_slivers = []
        deleted_nodes = []

        if 'node_ids' in sfa_slice:
            nodes = self.driver.testbed_shell.GetNodes(
                sfa_slice['list_node_ids'],
                ['hostname'])
            current_slivers = [node['hostname'] for node in nodes]

            # remove nodes not in rspec
            deleted_nodes = list(set(current_slivers).
                                 difference(requested_slivers))

            logger.debug("IOTLABSLICES \tverify_slice_nodes slice %s\
                                         \r\n \r\n deleted_nodes %s"
                         % (sfa_slice, deleted_nodes))

            if deleted_nodes:
                #Delete the entire experience
                self.driver.testbed_shell.DeleteSliceFromNodes(sfa_slice)
            return nodes

    def verify_slice(self, slice_hrn, slice_record, sfa_peer):
        """Ensures slice record exists.

        The slice record must exist either in Iotlab or in the other
        federated testbed (sfa_peer). If the slice does not belong to Iotlab,
        check if the user already exists in LDAP. In this case, adds the slice
        to the sfa DB and associates its LDAP user.

        :param slice_hrn: slice's name
        :param slice_record: sfa record of the slice
        :param sfa_peer: name of the peer authority if any.(not Iotlab).

        :type slice_hrn: string
        :type slice_record: dictionary
        :type sfa_peer: string

        .. seealso:: AddSlice


        """

        slicename = slice_hrn
        sfa_slice = None

        # check if slice belongs to Iotlab
        if slicename.startswith("iotlab"):
            slices_list = self.driver.GetSlices(slice_filter=slicename,
                                                slice_filter_type='slice_hrn')
    
            if slices_list:
                for sl in slices_list:
    
                    logger.debug("IOTLABSLICES \t verify_slice slicename %s \
                                    slices_list %s sl %s \r slice_record %s"
                                 % (slicename, slices_list, sl, slice_record))
                    sfa_slice = sl
                    sfa_slice.update(slice_record)

        else:
            #Search for user in ldap based on email SA 14/11/12
            ldap_user = self.driver.testbed_shell.ldap.LdapFindUser(\
                                                    slice_record['user'])
            logger.debug(" IOTLABSLICES \tverify_slice Oups \
                        slice_record %s sfa_peer %s ldap_user %s"
                        % (slice_record, sfa_peer, ldap_user))
            #User already registered in ldap, meaning user should be in SFA db
            #and hrn = sfa_auth+ uid
            sfa_slice = {'hrn': slicename,
                         'node_list': [],
                         'authority': slice_record['authority'],
                         'gid': slice_record['gid'],
                         #'slice_id': slice_record['record_id'],
                         'reg-researchers': slice_record['reg-researchers'],
                         'urn': hrn_to_urn(slicename,'slice'),
                         #'peer_authority': str(sfa_peer)
                         }

            if ldap_user:
#                hrn = self.driver.testbed_shell.root_auth + '.' \
#                                                + ldap_user['uid']
                for hrn in slice_record['reg-researchers']:
                    user = self.driver.get_user_record(hrn)
                    if user:
                        break

                logger.debug(" IOTLABSLICES \tverify_slice hrn %s USER %s"
                             % (hrn, user))

                 # add the external slice to the local SFA iotlab DB
                if sfa_slice:
                    self.driver.AddSlice(sfa_slice, user)

            logger.debug("IOTLABSLICES \tverify_slice ADDSLICE OK")
        return sfa_slice


    def verify_persons(self, slice_hrn, slice_record, users, options=None):
        """Ensures the users in users list exist and are enabled in LDAP. Adds
        person if needed (AddPerson).

        Checking that a user exist is based on the user's email. If the user is
        still not found in the LDAP, it means that the user comes from another
        federated testbed. In this case an account has to be created in LDAP
        so as to enable the user to use the testbed, since we trust the testbed
        he comes from. This is done by calling AddPerson.

        :param slice_hrn: slice name
        :param slice_record: record of the slice_hrn
        :param users: users is a record list. Records can either be
            local records or users records from known and trusted federated
            sites.If the user is from another site that iotlab doesn't trust
            yet, then Resolve will raise an error before getting to allocate.

        :type slice_hrn: string
        :type slice_record: string
        :type users: list

        .. seealso:: AddPerson
        .. note:: Removed unused peer and sfa_peer parameters. SA 18/07/13.


        """
        slice_user = slice_record['user']['hrn']

        if options is None: options={}
        logger.debug("IOTLABSLICES \tverify_persons \tslice_hrn  %s  \
                    \t slice_record %s\r\n users %s \t  "
                     % (slice_hrn, slice_record, users))

        users_by_email = {}
        #users_dict : dict whose keys can either be the user's hrn or its id.
        #Values contains only id and hrn
        users_dict = {}
        
        # XXX LOIC !!! Fix: Only 1 user per slice in iotlab
        users = [slice_record['user']]
        #First create dicts by hrn and id for each user in the user record list:
        for info in users:
            # if 'slice_record' in info:
            #     slice_rec = info['slice_record']
                # if 'user' in slice_rec :
                #     user = slice_rec['user']

            if 'email' in info:
                users_by_email[info['email']] = info
                users_dict[info['email']] = info

        #logger.debug("IOTLABSLICES.PY \t verify_person  \
        #                users_dict %s \r\n user_by_email %s \r\n  "
        #             % (users_dict, users_by_email))

        existing_user_ids = []
        existing_users_by_email = dict()
        existing_users = []
        # Check if user is in Iotlab LDAP using its hrn.
        # Assuming Iotlab is centralised :  one LDAP for all sites,
        # user's record_id unknown from LDAP
        # LDAP does not provide users id, therefore we rely on email to find the
        # user in LDAP

        if users_by_email:
            #Construct the list of filters (list of dicts) for GetPersons
            filter_user = [users_by_email[email] for email in users_by_email]
            #Check user i in LDAP with GetPersons
            #Needed because what if the user has been deleted in LDAP but
            #is still in SFA?
            # GetPersons -> LdapFindUser -> _process_ldap_info_for_one_user
            # XXX LOIC Fix in _process_ldap_info_for_one_user not to update user with hrn=None
            existing_users = self.driver.testbed_shell.GetPersons(filter_user)
            logger.debug(" \r\n IOTLABSLICES.PY \tverify_person  filter_user %s\
                       existing_users %s  "
                        % (filter_user, existing_users))
            #User is in iotlab LDAP
            if existing_users:
                for user in existing_users:
                    user['login'] = user['uid']
                    # XXX LOIC Fix we already have all informations comming from Allocate
                    #users_dict[user['email']].update(user)
                    existing_users_by_email[user['email']] = user
                logger.debug("User is in iotlab LDAP slice_record[user] = %s" % slice_user)

            # User from another known trusted federated site. Check
            # if a iotlab account matching the email has already been created.
            else:
                req = 'mail='
                if isinstance(users, list):
                    req += users[0]['email']
                else:
                    req += users['email']
                ldap_reslt = self.driver.testbed_shell.ldap.LdapSearch(req)
                logger.debug("LdapSearch slice_record[user] = %s" % slice_user)
                if ldap_reslt:
                    logger.debug(" IOTLABSLICES.PY \tverify_person users \
                                USER already in Iotlab \t ldap_reslt %s \
                                " % (ldap_reslt))
                    existing_users.append(ldap_reslt[1])
                    logger.debug("ldap_reslt slice_record[user] = %s" % slice_user)
                else:
                    #User not existing in LDAP
                    logger.debug("IOTLABSLICES.PY \tverify_person users \
                                not in ldap ...NEW ACCOUNT NEEDED %s \r\n \t \
                                ldap_reslt %s " % (users, ldap_reslt))

        requested_user_emails = users_by_email.keys()
        # requested_user_hrns = \
        #     [users_by_email[user]['hrn'] for user in users_by_email]
        # logger.debug("IOTLABSLICES.PY \tverify_person  \
        #                users_by_email  %s " % (users_by_email))

        # #Check that the user of the slice in the slice record
        # #matches one of the existing users
        # try:
        #     if slice_record['reg-researchers'][0] in requested_user_hrns:
        #         logger.debug(" IOTLABSLICES  \tverify_person ['PI']\
        #                         slice_record %s" % (slice_record))

        # except KeyError:
        #     pass

        # The function returns a list of added persons (to the LDAP ?)
        added_persons = list()

        # We go though each requested user and make sure it exists both in the
        # LDAP and in the local DB
        for user_email in requested_user_emails:
            user = users_by_email[user_email]

            person = {
                'peer_person_id': None,
                'mail'      : user['email'],
                'email'     : user['email'],
                'key_ids'   : user.get('key_ids', []),
                'hrn'       : users_by_email[user['email']]['hrn'],
            }
            if 'first_name' in user:
                person['first_name'] = user['first_name']
            if 'last_name' in user:
                person['last_name'] = user['last_name']
            if 'person_id' in user:
                person['person_id'] = user['person_id']
            if user['keys']:
                # XXX Only one key is kept for IoTLAB
                person['pkey'] = user['keys'][0]

            # LDAP 
            if users_by_email not in existing_users_by_email.keys():
                ret = self.driver.AddPerson(person)
                if 'uid' in ret:
                    person['uid'] = ret['uid']
                    added_persons.append(person)
                else:
                    logger.debug(" IOTLABSLICES ret message %s" %(ret))
            else:
                person['uid'] = existing_users_by_email[user['email']]['uid']

            # Local DB
            self.driver.add_person_to_db(person)

            
        # Set the login in the slice_record XXX
        slice_record['login'] = existing_users[0]['uid']

        return added_persons

#DEPRECATED|        # users to be added, removed or updated
#DEPRECATED|        #One user in one iotlab slice : there should be no need
#DEPRECATED|        #to remove/ add any user from/to a slice.
#DEPRECATED|        #However a user from SFA which is not registered in Iotlab yet
#DEPRECATED|        #should be added to the LDAP.
#DEPRECATED|        added_user_emails = set(requested_user_emails).\
#DEPRECATED|                                        difference(set(existing_user_emails))
#DEPRECATED|
#DEPRECATED|
#DEPRECATED|        #self.verify_keys(existing_slice_users, updated_users_list, \
#DEPRECATED|                                                            #peer, append)
#DEPRECATED|
#DEPRECATED|        # XXX JORDAN the uid of the user is put in slice_record['login']
#DEPRECATED|        added_persons = []
#DEPRECATED|        # add new users
#DEPRECATED|        #requested_user_email is in existing_user_emails
#DEPRECATED|        if len(added_user_emails) == 0:
#DEPRECATED|            slice_record['login'] = existing_users[0]['uid']
#DEPRECATED|            #slice_record['login'] = users_dict[requested_user_emails[0]]['uid']
#DEPRECATED|            logger.debug(" IOTLABSLICES  \tverify_person QUICK DIRTY %s"
#DEPRECATED|                         % (slice_record))
#DEPRECATED|            # XXX JORDAN uid == 'register'
#DEPRECATED|        logger.debug("JORDAN USERS BY EMAIL: %r" % users_by_email)
#DEPRECATED|
#DEPRECATED|        # XXX JORDAN i have no added_user_emails
#DEPRECATED|        logger.debug("JORDAN: added_user_emails: %r" % added_user_emails)
#DEPRECATED|        for added_user_email in added_user_emails:
#DEPRECATED|            added_user = users_dict[added_user_email]
#DEPRECATED|            logger.debug(" IOTLABSLICES \r\n \r\n  \t  verify_person \
#DEPRECATED|                         added_user %s" % (added_user))
#DEPRECATED|            person = {}
#DEPRECATED|            person['peer_person_id'] = None
#DEPRECATED|            k_list = ['first_name', 'last_name', 'person_id']
#DEPRECATED|            for k in k_list:
#DEPRECATED|                if k in added_user:
#DEPRECATED|                    person[k] = added_user[k]
#DEPRECATED|            # bug user without key
#DEPRECATED|            if added_user['keys']:
#DEPRECATED|                person['pkey'] = added_user['keys'][0]
#DEPRECATED|            person['mail'] = added_user['email']
#DEPRECATED|            person['email'] = added_user['email']
#DEPRECATED|            person['key_ids'] = added_user.get('key_ids', [])
#DEPRECATED|
#DEPRECATED|            # JORDAN
#DEPRECATED|            # This is the only call to AddPerson. We need to be sure to provide
#DEPRECATED|            # the right hrn, by default it used to be done in the function like
#DEPRECATED|            # this:
#DEPRECATED|            # person['hrn'] = self.testbed_shell.root_auth + '.' + ret['uid']
#DEPRECATED|            person['hrn'] = users_by_email[added_user['email']]['hrn']
#DEPRECATED|
#DEPRECATED|            # This only deals with the LDAP (now)
#DEPRECATED|            ret = self.driver.AddPerson(person)
#DEPRECATED|            # This will check if we have a record in the local DB and add it if necessary
#DEPRECATED|            self.__add_person_to_db(person)
#DEPRECATED|
#DEPRECATED|            if 'uid' in ret:
#DEPRECATED|                # meaning bool is True and the AddPerson was successful
#DEPRECATED|                person['uid'] = ret['uid']
#DEPRECATED|                slice_record['login'] = person['uid']
#DEPRECATED|            else:
#DEPRECATED|                # error message in ret
#DEPRECATED|                logger.debug(" IOTLABSLICES ret message %s" %(ret))
#DEPRECATED|
#DEPRECATED|            logger.debug(" IOTLABSLICES \r\n \r\n  \t THE SECOND verify_person\
#DEPRECATED|                           person %s" % (person))
#DEPRECATED|            #Update slice_Record with the id now known to LDAP
#DEPRECATED|
#DEPRECATED|
#DEPRECATED|            added_persons.append(person)
#DEPRECATED|        return added_persons


    def verify_keys(self, persons, users, peer, options=None):
        """
        .. warning:: unused
        """
        if options is None: options={}
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
        users_by_key_string = {}
        for user in users:
            user_keys = user.get('keys', [])
            updated_persons.append(user)
            for key_string in user_keys:
                users_by_key_string[key_string] = user
                requested_keys.append(key_string)
                if key_string not in existing_keys:
                    key = {'key': key_string, 'key_type': 'ssh'}
                    #try:
                        ##if peer:
                            #person = persondict[user['email']]
                            #self.driver.testbed_shell.UnBindObjectFromPeer(
                                # 'person',person['person_id'],
                                # peer['shortname'])
                    ret = self.driver.testbed_shell.AddPersonKey(
                        user['email'], key)
                        #if peer:
                            #key_index = user_keys.index(key['key'])
                            #remote_key_id = user['key_ids'][key_index]
                            #self.driver.testbed_shell.BindObjectToPeer('key', \
                                            #key['key_id'], peer['shortname'], \
                                            #remote_key_id)

        # remove old keys (only if we are not appending)
        append = options.get('append', True)
        if append is False:
            removed_keys = set(existing_keys).difference(requested_keys)
            for key in removed_keys:
                    #if peer:
                        #self.driver.testbed_shell.UnBindObjectFromPeer('key', \
                                        #key, peer['shortname'])

                user = users_by_key_string[key]
                self.driver.testbed_shell.DeleteKey(user, key)

        return
