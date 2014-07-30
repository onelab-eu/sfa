"""
This file defines the IotlabSlices class by which all the slice checkings
upon lease creation are done.
"""
from sfa.util.xrn import get_authority, urn_to_hrn
from sfa.util.sfalogging import logger

MAXINT = 2L**31-1


class CortexlabSlices:
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
        #Does this slice belong to a local site or a peer cortexlab site?
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

        logger.debug("CortexlabSlices \t get_peer slice_authority  %s \
                    site_authority %s hrn %s"
                     % (slice_authority, site_authority, hrn))

        # check if we are already peered with this site_authority
        #if so find the peer record
        peers = self.driver.GetPeers(peer_filter=site_authority)
        for peer_record in peers:
            if site_authority == peer_record.hrn:
                peer = peer_record
        logger.debug(" CortexlabSlices \tget_peer peer  %s " % (peer))
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

        logger.debug("CortexlabSlices verify_slice_leases sfa_slice %s "
                     % (sfa_slice))
        #First get the list of current leases from OAR
        leases = self.driver.GetLeases({'slice_hrn': sfa_slice['hrn']})
        logger.debug("CortexlabSlices verify_slice_leases requested_jobs_dict %s \
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
            if job['duration'] < self.driver.testbed_shell.GetLeaseGranularity():
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

        logger.debug("CortexlabSlices verify_slice_leases \
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
            logger.debug("CortexlabSlices verify_slice_leases  start_time %s \
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
                    logger.debug("CortexlabSlices verify_slice_leases \
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
                logger.debug("CortexlabSlices \
                              NEWLEASE slice %s  job %s"
                             % (sfa_slice, job))
                job_id = self.driver.AddLeases(job['hostname'],
                    sfa_slice, int(job['start_time']),
                    int(job['duration']))
                if job_id is not None:
                    new_leases = self.driver.GetLeases(login=
                        sfa_slice['login'])
                    for new_lease in new_leases:
                        leases.append(new_lease)

        #Deleted leases are the ones with lease id not declared in the Rspec
        if deleted_leases:
            self.driver.testbed_shell.DeleteLeases(deleted_leases,
                                    sfa_slice['user']['uid'])
            logger.debug("CortexlabSlices \
                          verify_slice_leases slice %s deleted_leases %s"
                         % (sfa_slice, deleted_leases))

        if reschedule_jobs_dict:
            for start_time in reschedule_jobs_dict:
                job = reschedule_jobs_dict[start_time]
                self.driver.AddLeases(job['hostname'],
                    sfa_slice, int(job['start_time']),
                    int(job['duration']))
        return leases

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

            logger.debug("CortexlabSlices \tverify_slice_nodes slice %s\
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
        # check if slice belongs to Iotlab
        slices_list = self.driver.GetSlices(
            slice_filter=slicename, slice_filter_type='slice_hrn')

        sfa_slice = None

        if slices_list:
            for sl in slices_list:

                logger.debug("CortexlabSlices \t verify_slice slicename %s \
                                slices_list %s sl %s \r slice_record %s"
                             % (slicename, slices_list, sl, slice_record))
                sfa_slice = sl
                sfa_slice.update(slice_record)

        else:
            #Search for user in ldap based on email SA 14/11/12
            ldap_user = self.driver.testbed_shell.ldap.LdapFindUser(\
                                                    slice_record['user'])
            logger.debug(" CortexlabSlices \tverify_slice Oups \
                        slice_record %s sfa_peer %s ldap_user %s"
                        % (slice_record, sfa_peer, ldap_user))
            #User already registered in ldap, meaning user should be in SFA db
            #and hrn = sfa_auth+ uid
            sfa_slice = {'hrn': slicename,
                         'node_list': [],
                         'authority': slice_record['authority'],
                         'gid': slice_record['gid'],
                         'slice_id': slice_record['record_id'],
                         'reg-researchers': slice_record['reg-researchers'],
                         'peer_authority': str(sfa_peer)
                         }

            if ldap_user:
                hrn = self.driver.testbed_shell.root_auth + '.' \
                                                + ldap_user['uid']
                user = self.driver.get_user_record(hrn)

                logger.debug(" CortexlabSlices \tverify_slice hrn %s USER %s"
                             % (hrn, user))

                 # add the external slice to the local SFA DB
                if sfa_slice:
                    self.driver.AddSlice(sfa_slice, user)

            logger.debug("CortexlabSlices \tverify_slice ADDSLICE OK")
        return sfa_slice


    def verify_persons(self, slice_hrn, slice_record, users, options=None):
        """Ensures the users in users list exist and are enabled in LDAP. Adds
        person if needed(AddPerson).

        Checking that a user exist is based on the user's email. If the user is
        still not found in the LDAP, it means that the user comes from another
        federated testbed. In this case an account has to be created in LDAP
        so as to enable the user to use the testbed, since we trust the testbed
        he comes from. This is done by calling AddPerson.

        :param slice_hrn: slice name
        :param slice_record: record of the slice_hrn
        :param users: users is a record list. Records can either be
            local records or users records from known and trusted federated
            sites.If the user is from another site that cortex;ab doesn't trust
            yet, then Resolve will raise an error before getting to allocate.

        :type slice_hrn: string
        :type slice_record: string
        :type users: list

        .. seealso:: AddPerson
        .. note:: Removed unused peer and sfa_peer parameters. SA 18/07/13.


        """

        if options is None: options={}

        logger.debug("CortexlabSlices \tverify_persons \tslice_hrn  %s  \
                    \t slice_record %s\r\n users %s \t  "
                     % (slice_hrn, slice_record, users))


        users_by_email = {}
        #users_dict : dict whose keys can either be the user's hrn or its id.
        #Values contains only id and hrn
        users_dict = {}

        #First create dicts by hrn and id for each user in the user record list:
        for info in users:
            # if 'slice_record' in info:
            #     slice_rec = info['slice_record']
            #     if 'user' in slice_rec :
            #         user = slice_rec['user']

            if 'email' in info:
                users_by_email[info['email']] = info
                users_dict[info['email']] = info


        logger.debug("CortexlabSlices.PY \t verify_person  \
                        users_dict %s \r\n user_by_email %s \r\n "
                     %(users_dict, users_by_email))

        existing_user_ids = []
        existing_user_emails = []
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
            existing_users = self.driver.testbed_shell.GetPersons(filter_user)
            logger.debug(" \r\n CortexlabSlices.PY \tverify_person  filter_user \
                        %s existing_users %s "
                        % (filter_user, existing_users))
            #User is in  LDAP
            if existing_users:
                for user in existing_users:
                    user['login'] = user['uid']
                    users_dict[user['email']].update(user)
                    existing_user_emails.append(
                        users_dict[user['email']]['email'])


            # User from another known trusted federated site. Check
            # if a cortexlab account matching the email has already been created.
            else:
                req = 'mail='
                if isinstance(users, list):
                    req += users[0]['email']
                else:
                    req += users['email']
                ldap_reslt = self.driver.testbed_shell.ldap.LdapSearch(req)

                if ldap_reslt:
                    logger.debug(" CortexlabSlices.PY \tverify_person users \
                                USER already in Iotlab \t ldap_reslt %s \
                                " % (ldap_reslt))
                    existing_users.append(ldap_reslt[1])

                else:
                    #User not existing in LDAP
                    logger.debug("CortexlabSlices.PY \tverify_person users \
                                not in ldap ...NEW ACCOUNT NEEDED %s \r\n \t \
                                ldap_reslt %s " % (users, ldap_reslt))

        requested_user_emails = users_by_email.keys()
        requested_user_hrns = \
            [users_by_email[user]['hrn'] for user in users_by_email]
        logger.debug("CortexlabSlices.PY \tverify_person  \
                       users_by_email  %s " % (users_by_email))

        #Check that the user of the slice in the slice record
        #matches one of the existing users
        try:
            if slice_record['reg-researchers'][0] in requested_user_hrns:
                logger.debug(" CortexlabSlices  \tverify_person ['PI']\
                                slice_record %s" % (slice_record))

        except KeyError:
            pass

        # users to be added, removed or updated
        #One user in one cortexlab slice : there should be no need
        #to remove/ add any user from/to a slice.
        #However a user from SFA which is not registered in Iotlab yet
        #should be added to the LDAP.
        added_user_emails = set(requested_user_emails).\
                                        difference(set(existing_user_emails))


        #self.verify_keys(existing_slice_users, updated_users_list, \
                                                            #peer, append)

        added_persons = []
        # add new users
        #requested_user_email is in existing_user_emails
        if len(added_user_emails) == 0:
            slice_record['login'] = users_dict[requested_user_emails[0]]['uid']
            logger.debug(" CortexlabSlices  \tverify_person QUICK DIRTY %s"
                         % (slice_record))

        for added_user_email in added_user_emails:
            added_user = users_dict[added_user_email]
            logger.debug(" CortexlabSlices \r\n \r\n  \t  verify_person \
                         added_user %s" % (added_user))
            person = {}
            person['peer_person_id'] = None
            k_list = ['first_name', 'last_name', 'person_id']
            for k in k_list:
                if k in added_user:
                    person[k] = added_user[k]

            person['pkey'] = added_user['keys'][0]
            person['mail'] = added_user['email']
            person['email'] = added_user['email']
            person['key_ids'] = added_user.get('key_ids', [])

            ret = self.driver.testbed_shell.AddPerson(person)
            if 'uid' in ret:
                # meaning bool is True and the AddPerson was successful
                person['uid'] = ret['uid']
                slice_record['login'] = person['uid']
            else:
                # error message in ret
                logger.debug(" CortexlabSlices ret message %s" %(ret))

            logger.debug(" CortexlabSlices \r\n \r\n  \t THE SECOND verify_person\
                           person %s" % (person))
            #Update slice_Record with the id now known to LDAP


            added_persons.append(person)
        return added_persons


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
