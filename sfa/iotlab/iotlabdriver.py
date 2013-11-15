"""
Implements what a driver should provide for SFA to work.
"""
from sfa.util.faults import SliverDoesNotExist, UnknownSfaType
from sfa.util.sfalogging import logger
from sfa.storage.alchemy import dbsession
from sfa.storage.model import RegRecord

from sfa.managers.driver import Driver
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec

from sfa.util.xrn import Xrn, hrn_to_urn, get_authority

from sfa.iotlab.iotlabaggregate import IotlabAggregate, iotlab_xrn_to_hostname
from sfa.iotlab.iotlabslices import IotlabSlices


from sfa.iotlab.iotlabshell import IotlabShell


class IotlabDriver(Driver):
    """ Iotlab Driver class inherited from Driver generic class.

    Contains methods compliant with the SFA standard and the testbed
        infrastructure (calls to LDAP and OAR).

    .. seealso::: Driver class

    """
    def __init__(self, api):
        """

        Sets the iotlab SFA config parameters,
            instanciates the testbed api and the iotlab database.

        :param config: iotlab SFA configuration object
        :type config: Config object

        """
        Driver.__init__(self, api)
        self.api=api
        config = api.config
        self.testbed_shell = IotlabShell(api)
        self.cache = None

    def augment_records_with_testbed_info(self, record_list):
        """

        Adds specific testbed info to the records.

        :param record_list: list of sfa dictionaries records
        :type record_list: list
        :returns: list of records with extended information in each record
        :rtype: list

        """
        return self.fill_record_info(record_list)

    def fill_record_info(self, record_list):
        """

        For each SFA record, fill in the iotlab specific and SFA specific
            fields in the record.

        :param record_list: list of sfa dictionaries records
        :type record_list: list
        :returns: list of records with extended information in each record
        :rtype: list

        .. warning:: Should not be modifying record_list directly because modi
            fication are kept outside the method's scope. Howerver, there is no
            other way to do it given the way it's called in registry manager.

        """

        logger.debug("IOTLABDRIVER \tfill_record_info records %s "
                     % (record_list))
        if not isinstance(record_list, list):
            record_list = [record_list]

        try:
            for record in record_list:

                if str(record['type']) == 'node':
                    # look for node info using GetNodes
                    # the record is about one node only
                    filter_dict = {'hrn': [record['hrn']]}
                    node_info = self.testbed_shell.GetNodes(filter_dict)
                    # the node_info is about one node only, but it is formatted
                    # as a list
                    record.update(node_info[0])
                    logger.debug("IOTLABDRIVER.PY \t \
                                  fill_record_info NODE" % (record))

                #If the record is a SFA slice record, then add information
                #about the user of this slice. This kind of
                #information is in the Iotlab's DB.
                if str(record['type']) == 'slice':
                    if 'reg_researchers' in record and isinstance(record
                                                            ['reg_researchers'],
                                                            list):
                        record['reg_researchers'] = \
                            record['reg_researchers'][0].__dict__
                        record.update(
                            {'PI': [record['reg_researchers']['hrn']],
                             'researcher': [record['reg_researchers']['hrn']],
                             'name': record['hrn'],
                             'oar_job_id': [],
                             'node_ids': [],
                             'person_ids': [record['reg_researchers']
                                            ['record_id']],
                                # For client_helper.py compatibility
                             'geni_urn': '',
                                # For client_helper.py compatibility
                             'keys': '',
                                # For client_helper.py compatibility
                             'key_ids': ''})

                    #Get iotlab slice record and oar job id if any.
                    recslice_list = self.testbed_shell.GetSlices(
                        slice_filter=str(record['hrn']),
                        slice_filter_type='slice_hrn')

                    logger.debug("IOTLABDRIVER \tfill_record_info \
                        TYPE SLICE RECUSER record['hrn'] %s record['oar_job_id']\
                         %s " % (record['hrn'], record['oar_job_id']))
                    del record['reg_researchers']
                    try:
                        for rec in recslice_list:
                            logger.debug("IOTLABDRIVER\r\n  \t  \
                            fill_record_info oar_job_id %s "
                                         % (rec['oar_job_id']))

                            record['node_ids'] = [self.testbed_shell.root_auth +
                                                  '.' + hostname for hostname
                                                  in rec['node_ids']]
                    except KeyError:
                        pass

                    logger.debug("IOTLABDRIVER.PY \t fill_record_info SLICE \
                                    recslice_list  %s \r\n \t RECORD %s \r\n \
                                    \r\n" % (recslice_list, record))

                if str(record['type']) == 'user':
                    #The record is a SFA user record.
                    #Get the information about his slice from Iotlab's DB
                    #and add it to the user record.
                    recslice_list = self.testbed_shell.GetSlices(
                        slice_filter=record['record_id'],
                        slice_filter_type='record_id_user')

                    logger.debug("IOTLABDRIVER.PY \t fill_record_info \
                        TYPE USER recslice_list %s \r\n \t RECORD %s \r\n"
                                 % (recslice_list, record))
                    #Append slice record in records list,
                    #therefore fetches user and slice info again(one more loop)
                    #Will update PIs and researcher for the slice

                    recuser = recslice_list[0]['reg_researchers']
                    logger.debug("IOTLABDRIVER.PY \t fill_record_info USER  \
                                            recuser %s \r\n \r\n" % (recuser))
                    recslice = {}
                    recslice = recslice_list[0]
                    recslice.update(
                        {'PI': [recuser['hrn']],
                         'researcher': [recuser['hrn']],
                         'name': record['hrn'],
                         'node_ids': [],
                         'oar_job_id': [],
                         'person_ids': [recuser['record_id']]})
                    try:
                        for rec in recslice_list:
                            recslice['oar_job_id'].append(rec['oar_job_id'])
                    except KeyError:
                        pass

                    recslice.update({'type': 'slice',
                                     'hrn': recslice_list[0]['hrn']})

                    #GetPersons takes [] as filters
                    user_iotlab = self.testbed_shell.GetPersons([record])

                    record.update(user_iotlab[0])
                    #For client_helper.py compatibility
                    record.update(
                        {'geni_urn': '',
                         'keys': '',
                         'key_ids': ''})
                    record_list.append(recslice)

                    logger.debug("IOTLABDRIVER.PY \t \
                        fill_record_info ADDING SLICE\
                        INFO TO USER records %s" % (record_list))

        except TypeError, error:
            logger.log_exc("IOTLABDRIVER \t fill_record_info  EXCEPTION %s"
                           % (error))

        return record_list

    def sliver_status(self, slice_urn, slice_hrn):
        """
        Receive a status request for slice named urn/hrn
            urn:publicid:IDN+iotlab+nturro_slice hrn iotlab.nturro_slice
            shall return a structure as described in
            http://groups.geni.net/geni/wiki/GAPI_AM_API_V2#SliverStatus
            NT : not sure if we should implement this or not, but used by sface.

        :param slice_urn: slice urn
        :type slice_urn: string
        :param slice_hrn: slice hrn
        :type slice_hrn: string

        """

        #First get the slice with the slice hrn
        slice_list = self.testbed_shell.GetSlices(slice_filter=slice_hrn,
                                               slice_filter_type='slice_hrn')

        if len(slice_list) == 0:
            raise SliverDoesNotExist("%s  slice_hrn" % (slice_hrn))

        #Used for fetching the user info witch comes along the slice info
        one_slice = slice_list[0]

        #Make a list of all the nodes hostnames  in use for this slice
        slice_nodes_list = []
        slice_nodes_list = one_slice['node_ids']
        #Get all the corresponding nodes details
        nodes_all = self.testbed_shell.GetNodes(
            {'hostname': slice_nodes_list},
            ['node_id', 'hostname', 'site', 'boot_state'])
        nodeall_byhostname = dict([(one_node['hostname'], one_node)
                                  for one_node in nodes_all])

        for single_slice in slice_list:
              #For compatibility
            top_level_status = 'empty'
            result = {}
            result.fromkeys(
                ['geni_urn', 'geni_error', 'iotlab_login', 'geni_status',
                 'geni_resources'], None)
            # result.fromkeys(\
            #     ['geni_urn','geni_error', 'pl_login','geni_status',
            # 'geni_resources'], None)
            # result['pl_login'] = one_slice['reg_researchers'][0].hrn
            result['iotlab_login'] = one_slice['user']
            logger.debug("Slabdriver - sliver_status Sliver status \
                            urn %s hrn %s single_slice  %s \r\n "
                         % (slice_urn, slice_hrn, single_slice))

            if 'node_ids' not in single_slice:
                #No job in the slice
                result['geni_status'] = top_level_status
                result['geni_resources'] = []
                return result

            top_level_status = 'ready'

            #A job is running on Iotlab for this slice
            # report about the local nodes that are in the slice only

            result['geni_urn'] = slice_urn

            resources = []
            for node_hostname in single_slice['node_ids']:
                res = {}
                res['iotlab_hostname'] = node_hostname
                res['iotlab_boot_state'] = \
                    nodeall_byhostname[node_hostname]['boot_state']

                #res['pl_hostname'] = node['hostname']
                #res['pl_boot_state'] = \
                            #nodeall_byhostname[node['hostname']]['boot_state']
                #res['pl_last_contact'] = strftime(self.time_format, \
                                                    #gmtime(float(timestamp)))
                sliver_id = Xrn(
                    slice_urn, type='slice',
                    id=nodeall_byhostname[node_hostname]['node_id']).urn

                res['geni_urn'] = sliver_id
                #node_name  = node['hostname']
                if nodeall_byhostname[node_hostname]['boot_state'] == 'Alive':

                    res['geni_status'] = 'ready'
                else:
                    res['geni_status'] = 'failed'
                    top_level_status = 'failed'

                res['geni_error'] = ''

                resources.append(res)

            result['geni_status'] = top_level_status
            result['geni_resources'] = resources
            logger.debug("IOTLABDRIVER \tsliver_statusresources %s res %s "
                         % (resources, res))
            return result

    @staticmethod
    def get_user_record(hrn):
        """

        Returns the user record based on the hrn from the SFA DB .

        :param hrn: user's hrn
        :type hrn: string
        :returns: user record from SFA database
        :rtype: RegUser

        """
        return dbsession.query(RegRecord).filter_by(hrn=hrn).first()

    def testbed_name(self):
        """

        Returns testbed's name.
        :returns: testbed authority name.
        :rtype: string

        """
        return self.hrn

    # 'geni_request_rspec_versions' and 'geni_ad_rspec_versions' are mandatory
    def aggregate_version(self):
        """

        Returns the testbed's supported rspec advertisement and request
        versions.
        :returns: rspec versions supported ad a dictionary.
        :rtype: dict

        """
        version_manager = VersionManager()
        ad_rspec_versions = []
        request_rspec_versions = []
        for rspec_version in version_manager.versions:
            if rspec_version.content_type in ['*', 'ad']:
                ad_rspec_versions.append(rspec_version.to_dict())
            if rspec_version.content_type in ['*', 'request']:
                request_rspec_versions.append(rspec_version.to_dict())
        return {
            'testbed': self.testbed_name(),
            'geni_request_rspec_versions': request_rspec_versions,
            'geni_ad_rspec_versions': ad_rspec_versions}

    def _get_requested_leases_list(self, rspec):
        """
        Process leases in rspec depending on the rspec version (format)
            type. Find the lease requests in the rspec and creates
            a lease request list with the mandatory information ( nodes,
            start time and duration) of the valid leases (duration above or
            equal to the iotlab experiment minimum duration).

        :param rspec: rspec request received.
        :type rspec: RSpec
        :returns: list of lease requests found in the rspec
        :rtype: list
        """
        requested_lease_list = []
        for lease in rspec.version.get_leases():
            single_requested_lease = {}
            logger.debug("IOTLABDRIVER.PY \t \
                _get_requested_leases_list lease %s " % (lease))

            if not lease.get('lease_id'):
                if get_authority(lease['component_id']) == \
                        self.testbed_shell.root_auth:
                    single_requested_lease['hostname'] = \
                        iotlab_xrn_to_hostname(\
                            lease.get('component_id').strip())
                    single_requested_lease['start_time'] = \
                        lease.get('start_time')
                    single_requested_lease['duration'] = lease.get('duration')
                    #Check the experiment's duration is valid before adding
                    #the lease to the requested leases list
                    duration_in_seconds = \
                        int(single_requested_lease['duration'])
                    if duration_in_seconds >= self.testbed_shell.GetMinExperimentDurationInGranularity():
                        requested_lease_list.append(single_requested_lease)

        return requested_lease_list

    @staticmethod
    def _group_leases_by_start_time(requested_lease_list):
        """
        Create dict of leases by start_time, regrouping nodes reserved
            at the same time, for the same amount of time so as to
            define one job on OAR.

        :param requested_lease_list: list of leases
        :type requested_lease_list: list
        :returns: Dictionary with key = start time, value = list of leases
            with the same start time.
        :rtype: dictionary

        """

        requested_xp_dict = {}
        for lease in requested_lease_list:

            #In case it is an asap experiment start_time is empty
            if lease['start_time'] == '':
                lease['start_time'] = '0'

            if lease['start_time'] not in requested_xp_dict:
                if isinstance(lease['hostname'], str):
                    lease['hostname'] = [lease['hostname']]

                requested_xp_dict[lease['start_time']] = lease

            else:
                job_lease = requested_xp_dict[lease['start_time']]
                if lease['duration'] == job_lease['duration']:
                    job_lease['hostname'].append(lease['hostname'])

        return requested_xp_dict

    def _process_requested_xp_dict(self, rspec):
        """
        Turns the requested leases and information into a dictionary
            of requested jobs, grouped by starting time.

        :param rspec: RSpec received
        :type rspec : RSpec
        :rtype: dictionary

        """
        requested_lease_list = self._get_requested_leases_list(rspec)
        logger.debug("IOTLABDRIVER _process_requested_xp_dict \
            requested_lease_list  %s" % (requested_lease_list))
        xp_dict = self._group_leases_by_start_time(requested_lease_list)
        logger.debug("IOTLABDRIVER _process_requested_xp_dict  xp_dict\
        %s" % (xp_dict))

        return xp_dict

    def create_sliver(self, slice_urn, slice_hrn, creds, rspec_string,
                      users, options):
        """Answer to CreateSliver.

        Creates the leases and slivers for the users from the information
            found in the rspec string.
            Launch experiment on OAR if the requested leases is valid. Delete
            no longer requested leases.


        :param creds: user's credentials
        :type creds: string
        :param users: user record list
        :type users: list
        :param options:
        :type options:

        :returns: a valid Rspec for the slice which has just been
            modified.
        :rtype: RSpec


        """
        aggregate = IotlabAggregate(self)

        slices = IotlabSlices(self)
        peer = slices.get_peer(slice_hrn)
        sfa_peer = slices.get_sfa_peer(slice_hrn)
        slice_record = None

        if not isinstance(creds, list):
            creds = [creds]

        if users:
            slice_record = users[0].get('slice_record', {})
            logger.debug("IOTLABDRIVER.PY \t ===============create_sliver \t\
                            creds %s \r\n \r\n users %s"
                         % (creds, users))
            slice_record['user'] = {'keys': users[0]['keys'],
                                    'email': users[0]['email'],
                                    'hrn': slice_record['reg-researchers'][0]}
        # parse rspec
        rspec = RSpec(rspec_string)
        logger.debug("IOTLABDRIVER.PY \t create_sliver \trspec.version \
                     %s slice_record %s users %s"
                     % (rspec.version, slice_record, users))

        # ensure site record exists?
        # ensure slice record exists
        #Removed options in verify_slice SA 14/08/12
        #Removed peer record in  verify_slice SA 18/07/13
        sfa_slice = slices.verify_slice(slice_hrn, slice_record, sfa_peer)

        # ensure person records exists
        #verify_persons returns added persons but the return value
        #is not used
        #Removed peer record and sfa_peer in  verify_persons SA 18/07/13
        slices.verify_persons(slice_hrn, sfa_slice, users, options=options)
        #requested_attributes returned by rspec.version.get_slice_attributes()
        #unused, removed SA 13/08/12
        #rspec.version.get_slice_attributes()

        logger.debug("IOTLABDRIVER.PY create_sliver slice %s " % (sfa_slice))

        # add/remove slice from nodes

        #requested_slivers = [node.get('component_id') \
                    #for node in rspec.version.get_nodes_with_slivers()\
                    #if node.get('authority_id') is self.testbed_shell.root_auth]
        #l = [ node for node in rspec.version.get_nodes_with_slivers() ]
        #logger.debug("SLADRIVER \tcreate_sliver requested_slivers \
                                    #requested_slivers %s  listnodes %s" \
                                    #%(requested_slivers,l))
        #verify_slice_nodes returns nodes, but unused here. Removed SA 13/08/12.
        #slices.verify_slice_nodes(sfa_slice, requested_slivers, peer)

        requested_xp_dict = self._process_requested_xp_dict(rspec)

        logger.debug("IOTLABDRIVER.PY \tcreate_sliver  requested_xp_dict %s "
                     % (requested_xp_dict))
        #verify_slice_leases returns the leases , but the return value is unused
        #here. Removed SA 13/08/12
        slices.verify_slice_leases(sfa_slice,
                                   requested_xp_dict, peer)

        return aggregate.get_rspec(slice_xrn=slice_urn,
                                   login=sfa_slice['login'],
                                   version=rspec.version)

    def delete_sliver(self, slice_urn, slice_hrn, creds, options):
        """
        Deletes the lease associated with the slice hrn and the credentials
            if the slice belongs to iotlab. Answer to DeleteSliver.

        :param slice_urn: urn of the slice
        :param slice_hrn: name of the slice
        :param creds: slice credenials
        :type slice_urn: string
        :type slice_hrn: string
        :type creds: ? unused

        :returns: 1 if the slice to delete was not found on iotlab,
            True if the deletion was successful, False otherwise otherwise.

        .. note:: Should really be named delete_leases because iotlab does
            not have any slivers, but only deals with leases. However,
            SFA api only have delete_sliver define so far. SA 13/05/2013
        .. note:: creds are unused, and are not used either in the dummy driver
             delete_sliver .
        """

        sfa_slice_list = self.testbed_shell.GetSlices(
            slice_filter=slice_hrn,
            slice_filter_type='slice_hrn')

        if not sfa_slice_list:
            return 1

        #Delete all leases in the slice
        for sfa_slice in sfa_slice_list:
            logger.debug("IOTLABDRIVER.PY delete_sliver slice %s" % (sfa_slice))
            slices = IotlabSlices(self)
            # determine if this is a peer slice

            peer = slices.get_peer(slice_hrn)

            logger.debug("IOTLABDRIVER.PY delete_sliver peer %s \
                \r\n \t sfa_slice %s " % (peer, sfa_slice))
            try:
                self.testbed_shell.DeleteSliceFromNodes(sfa_slice)
                return True
            except:
                return False

    def list_resources (self, slice_urn, slice_hrn, creds, options):
        """

        List resources from the iotlab aggregate and returns a Rspec
            advertisement with resources found when slice_urn and slice_hrn are
            None (in case of resource discovery).
            If a slice hrn and urn are provided, list experiment's slice
            nodes in a rspec format. Answer to ListResources.
            Caching unused.

        :param slice_urn: urn of the slice
        :param slice_hrn: name of the slice
        :param creds: slice credenials
        :type slice_urn: string
        :type slice_hrn: string
        :type creds: ? unused
        :param options: options used when listing resources (list_leases, info,
            geni_available)
        :returns: rspec string in xml
        :rtype: string

        .. note:: creds are unused
        """

        #cached_requested = options.get('cached', True)

        version_manager = VersionManager()
        # get the rspec's return format from options
        rspec_version = \
            version_manager.get_version(options.get('geni_rspec_version'))
        version_string = "rspec_%s" % (rspec_version)

        #panos adding the info option to the caching key (can be improved)
        if options.get('info'):
            version_string = version_string + "_" + \
                options.get('info', 'default')

        # Adding the list_leases option to the caching key
        if options.get('list_leases'):
            version_string = version_string + "_" + \
            options.get('list_leases', 'default')

        # Adding geni_available to caching key
        if options.get('geni_available'):
            version_string = version_string + "_" + \
                str(options.get('geni_available'))

        # look in cache first
        #if cached_requested and self.cache and not slice_hrn:
            #rspec = self.cache.get(version_string)
            #if rspec:
                #logger.debug("IotlabDriver.ListResources: \
                                    #returning cached advertisement")
                #return rspec

        #panos: passing user-defined options
        aggregate = IotlabAggregate(self)

        rspec = aggregate.get_rspec(slice_xrn=slice_urn,
                                    version=rspec_version, options=options)

        # cache the result
        #if self.cache and not slice_hrn:
            #logger.debug("Iotlab.ListResources: stores advertisement in cache")
            #self.cache.add(version_string, rspec)

        return rspec


    def list_slices(self, creds, options):
        """Answer to ListSlices.

        List slices belonging to iotlab, returns slice urns list.
            No caching used. Options unused but are defined in the SFA method
            api prototype.

        :returns: slice urns list
        :rtype: list

        .. note:: creds are unused
        """
        # look in cache first
        #if self.cache:
            #slices = self.cache.get('slices')
            #if slices:
                #logger.debug("PlDriver.list_slices returns from cache")
                #return slices

        # get data from db

        slices = self.testbed_shell.GetSlices()
        logger.debug("IOTLABDRIVER.PY \tlist_slices hrn %s \r\n \r\n"
                     % (slices))
        slice_hrns = [iotlab_slice['hrn'] for iotlab_slice in slices]

        slice_urns = [hrn_to_urn(slice_hrn, 'slice')
                      for slice_hrn in slice_hrns]

        # cache the result
        #if self.cache:
            #logger.debug ("IotlabDriver.list_slices stores value in cache")
            #self.cache.add('slices', slice_urns)

        return slice_urns


    def register(self, sfa_record, hrn, pub_key):
        """
        Adding new user, slice, node or site should not be handled
            by SFA.

        ..warnings:: should not be used. Different components are in charge of
            doing this task. Adding nodes = OAR
            Adding users = LDAP Iotlab
            Adding slice = Import from LDAP users
            Adding site = OAR

        :param sfa_record: record provided by the client of the
            Register API call.
        :type sfa_record: dict
        :param pub_key: public key of the user
        :type pub_key: string

        .. note:: DOES NOTHING. Returns -1.

        """
        return -1


    def update(self, old_sfa_record, new_sfa_record, hrn, new_key):
        """
        No site or node record update allowed in Iotlab. The only modifications
        authorized here are key deletion/addition on an existing user and
        password change. On an existing user, CAN NOT BE MODIFIED: 'first_name',
        'last_name', 'email'. DOES NOT EXIST IN SENSLAB: 'phone', 'url', 'bio',
        'title', 'accepted_aup'. A slice is bound to its user, so modifying the
        user's ssh key should nmodify the slice's GID after an import procedure.

        :param old_sfa_record: what is in the db for this hrn
        :param new_sfa_record: what was passed to the update call
        :param new_key: the new user's public key
        :param hrn: the user's sfa hrn
        :type old_sfa_record: dict
        :type new_sfa_record: dict
        :type new_key: string
        :type hrn: string

        TODO: needs review
        .. seealso:: update in driver.py.

        """
        pointer = old_sfa_record['pointer']
        old_sfa_record_type = old_sfa_record['type']

        # new_key implemented for users only
        if new_key and old_sfa_record_type not in ['user']:
            raise UnknownSfaType(old_sfa_record_type)

        if old_sfa_record_type == "user":
            update_fields = {}
            all_fields = new_sfa_record
            for key in all_fields.keys():
                if key in ['key', 'password']:
                    update_fields[key] = all_fields[key]

            if new_key:
                # must check this key against the previous one if it exists
                persons = self.testbed_shell.GetPersons([old_sfa_record])
                person = persons[0]
                keys = [person['pkey']]
                #Get all the person's keys
                keys_dict = self.testbed_shell.GetKeys(keys)

                # Delete all stale keys, meaning the user has only one key
                #at a time
                #TODO: do we really want to delete all the other keys?
                #Is this a problem with the GID generation to have multiple
                #keys? SA 30/05/13
                key_exists = False
                if key in keys_dict:
                    key_exists = True
                else:
                    #remove all the other keys
                    for key in keys_dict:
                        self.testbed_shell.DeleteKey(person, key)
                    self.testbed_shell.AddPersonKey(
                        person, {'sshPublicKey': person['pkey']},
                        {'sshPublicKey': new_key})
        return True

    def remove(self, sfa_record):
        """

        Removes users only. Mark the user as disabled in LDAP. The user and his
        slice are then deleted from the db by running an import on the registry.

        :param sfa_record: record is the existing sfa record in the db
        :type sfa_record: dict

        ..warning::As fas as the slice is concerned, here only the leases are
            removed from the slice. The slice is record itself is not removed
            from the db.

        TODO: needs review

        TODO : REMOVE SLICE FROM THE DB AS WELL? SA 14/05/2013,

        TODO: return boolean for the slice part
        """
        sfa_record_type = sfa_record['type']
        hrn = sfa_record['hrn']
        if sfa_record_type == 'user':

            #get user from iotlab ldap
            person = self.testbed_shell.GetPersons(sfa_record)
            #No registering at a given site in Iotlab.
            #Once registered to the LDAP, all iotlab sites are
            #accesible.
            if person:
                #Mark account as disabled in ldap
                return self.testbed_shell.DeletePerson(sfa_record)

        elif sfa_record_type == 'slice':
            if self.testbed_shell.GetSlices(slice_filter=hrn,
                                         slice_filter_type='slice_hrn'):
                ret = self.testbed_shell.DeleteSlice(sfa_record)
            return True
