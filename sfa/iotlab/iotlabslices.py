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
        if options is None: options={}
        user = slice_record['user']
        logger.debug("IOTLABSLICES \tverify_persons \tuser  %s " % user)
        person = {
                'peer_person_id': None,
                'mail'      : user['email'],
                'email'     : user['email'],
                'key_ids'   : user.get('key_ids', []),
                'hrn'       : user['hrn'],
        }
        if 'first_name' in user:
            person['first_name'] = user['first_name']
        if 'last_name' in user:
            person['last_name'] = user['last_name']
        if 'person_id' in user:
            person['person_id'] = user['person_id']
        if user['keys']:
            # Only one key is kept for IoTLAB
            person['pkey'] = user['keys'][0]
        # SFA DB (if user already exist we do nothing)
        self.driver.add_person_to_db(person)
        # Iot-LAB LDAP (if user already exist we do nothing)
        ret = self.driver.AddPerson(person)
        # user uid information is only in LDAP
        # Be carreful : global scope of dict slice_record in driver
        slice_record['login'] = ret['uid']
        return person

       

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
