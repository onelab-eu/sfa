"""
File containing the IotlabShell, used to interact with nodes, users,
slices, leases and keys,  as well as the dedicated iotlab database and table,
holding information about which slice is running which job.

"""
from datetime import datetime

from sfa.util.sfalogging import logger
from sfa.util.sfatime import SFATIME_FORMAT

from sfa.iotlab.OARrestapi import OARrestapi
from sfa.iotlab.LDAPapi import LDAPapi


class IotlabShell():
    """ Class enabled to use LDAP and OAR api calls. """

    _MINIMUM_DURATION = 10  # 10 units of granularity 60 s, 10 mins

    def __init__(self, config):
        """Creates an instance of OARrestapi and LDAPapi which will be used to
        issue calls to OAR or LDAP methods.
        Set the time format  and the testbed granularity used for OAR
        reservation and leases.

        :param config: configuration object from sfa.util.config
        :type config: Config object
        """

        # self.leases_db = TestbedAdditionalSfaDB(config)
        self.oar = OARrestapi()
        self.ldap = LDAPapi()
        self.time_format = SFATIME_FORMAT
        self.root_auth = config.SFA_REGISTRY_ROOT_AUTH
        self.grain = 60  # 10 mins lease minimum, 60 sec granularity
        #import logging, logging.handlers
        #from sfa.util.sfalogging import _SfaLogger
        #sql_logger = _SfaLogger(loggername = 'sqlalchemy.engine', \
                                                    #level=logging.DEBUG)
        return

    @staticmethod
    def GetMinExperimentDurationInGranularity():
        """ Returns the minimum allowed duration for an experiment on the
        testbed. In seconds.

        """
        return IotlabShell._MINIMUM_DURATION




    #TODO  : Handling OR request in make_ldap_filters_from_records
    #instead of the for loop
    #over the records' list
    def GetPersons(self, person_filter=None):
        """
        Get the enabled users and their properties from Iotlab LDAP.
        If a filter is specified, looks for the user whose properties match
        the filter, otherwise returns the whole enabled users'list.

        :param person_filter: Must be a list of dictionnaries with users
            properties when not set to None.
        :type person_filter: list of dict

        :returns: Returns a list of users whose accounts are enabled
            found in ldap.
        :rtype: list of dicts

        """
        logger.debug("IOTLAB_API \tGetPersons person_filter %s"
                     % (person_filter))
        person_list = []
        if person_filter and isinstance(person_filter, list):
        #If we are looking for a list of users (list of dict records)
        #Usually the list contains only one user record
            for searched_attributes in person_filter:

                #Get only enabled user accounts in iotlab LDAP :
                #add a filter for make_ldap_filters_from_record
                person = self.ldap.LdapFindUser(searched_attributes,
                                                is_user_enabled=True)
                #If a person was found, append it to the list
                if person:
                    person_list.append(person)

            #If the list is empty, return None
            if len(person_list) is 0:
                person_list = None

        else:
            #Get only enabled user accounts in iotlab LDAP :
            #add a filter for make_ldap_filters_from_record
            person_list  = self.ldap.LdapFindUser(is_user_enabled=True)

        return person_list


    #def GetTimezone(self):
        #""" Returns the OAR server time and timezone.
        #Unused SA 30/05/13"""
        #server_timestamp, server_tz = self.oar.parser.\
                                            #SendRequest("GET_timezone")
        #return server_timestamp, server_tz

    def DeleteJobs(self, job_id, username):
        """

        Deletes the job with the specified job_id and username on OAR by
            posting a delete request to OAR.

        :param job_id: job id in OAR.
        :param username: user's iotlab login in LDAP.
        :type job_id: integer
        :type username: string

        :returns: dictionary with the job id and if delete has been successful
            (True) or no (False)
        :rtype: dict

        """
        logger.debug("IOTLAB_API \tDeleteJobs jobid  %s username %s "
                     % (job_id, username))
        if not job_id or job_id is -1:
            return

        reqdict = {}
        reqdict['method'] = "delete"
        reqdict['strval'] = str(job_id)

        answer = self.oar.POSTRequestToOARRestAPI('DELETE_jobs_id',
                                                  reqdict, username)
        if answer['status'] == 'Delete request registered':
            ret = {job_id: True}
        else:
            ret = {job_id: False}
        logger.debug("IOTLAB_API \tDeleteJobs jobid  %s \r\n answer %s \
                                username %s" % (job_id, answer, username))
        return ret



        ##TODO : Unused GetJobsId ? SA 05/07/12
    #def GetJobsId(self, job_id, username = None ):
        #"""
        #Details about a specific job.
        #Includes details about submission time, jot type, state, events,
        #owner, assigned ressources, walltime etc...

        #"""
        #req = "GET_jobs_id"
        #node_list_k = 'assigned_network_address'
        ##Get job info from OAR
        #job_info = self.oar.parser.SendRequest(req, job_id, username)

        #logger.debug("IOTLAB_API \t GetJobsId  %s " %(job_info))
        #try:
            #if job_info['state'] == 'Terminated':
                #logger.debug("IOTLAB_API \t GetJobsId job %s TERMINATED"\
                                                            #%(job_id))
                #return None
            #if job_info['state'] == 'Error':
                #logger.debug("IOTLAB_API \t GetJobsId ERROR message %s "\
                                                            #%(job_info))
                #return None

        #except KeyError:
            #logger.error("IOTLAB_API \tGetJobsId KeyError")
            #return None

        #parsed_job_info  = self.get_info_on_reserved_nodes(job_info, \
                                                            #node_list_k)
        ##Replaces the previous entry
        ##"assigned_network_address" / "reserved_resources"
        ##with "node_ids"
        #job_info.update({'node_ids':parsed_job_info[node_list_k]})
        #del job_info[node_list_k]
        #logger.debug(" \r\nIOTLAB_API \t GetJobsId job_info %s " %(job_info))
        #return job_info


    def GetJobsResources(self, job_id, username = None):
        """ Gets the list of nodes associated with the job_id and username
        if provided.

        Transforms the iotlab hostnames to the corresponding SFA nodes hrns.
        Returns dict key :'node_ids' , value : hostnames list.

        :param username: user's LDAP login
        :paran job_id: job's OAR identifier.
        :type username: string
        :type job_id: integer

        :returns: dicionary with nodes' hostnames belonging to the job.
        :rtype: dict

        .. warning:: Unused. SA 16/10/13
        """

        req = "GET_jobs_id_resources"


        #Get job resources list from OAR
        node_id_list = self.oar.parser.SendRequest(req, job_id, username)
        logger.debug("IOTLAB_API \t GetJobsResources  %s " %(node_id_list))
        resources = self.GetNodes()
        oar_id_node_dict = {}
        for node in resources:
            oar_id_node_dict[node['oar_id']] = node['hostname']
        hostname_list = \
            self.__get_hostnames_from_oar_node_ids(oar_id_node_dict,
                                                            node_id_list)


        #Replaces the previous entry "assigned_network_address" /
        #"reserved_resources" with "node_ids"
        job_info = {'node_ids': hostname_list}

        return job_info


    def GetNodesCurrentlyInUse(self):
        """Returns a list of all the nodes already involved in an oar running
        job.
        :rtype: list of nodes hostnames.
        """
        return self.oar.parser.SendRequest("GET_running_jobs")

    @staticmethod
    def __get_hostnames_from_oar_node_ids(oar_id_node_dict,
            resource_id_list ):
        """Get the hostnames of the nodes from their OAR identifiers.
        Get the list of nodes dict using GetNodes and find the hostname
        associated with the identifier.
        :param oar_id_node_dict: full node dictionary list keyed by oar node id
        :param resource_id_list: list of nodes identifiers
        :returns: list of node hostnames.
        """

        hostname_list = []
        for resource_id in resource_id_list:
            #Because jobs requested "asap" do not have defined resources
            if resource_id is not "Undefined":
                hostname_list.append(\
                        oar_id_node_dict[resource_id]['hostname'])

        return hostname_list

    def GetReservedNodes(self, username=None):
        """ Get list of leases. Get the leases for the username if specified,
        otherwise get all the leases. Finds the nodes hostnames for each
        OAR node identifier.
        :param username: user's LDAP login
        :type username: string
        :returns: list of reservations dict
        :rtype: dict list
        """

        #Get the nodes in use and the reserved nodes
        reservation_dict_list = \
                        self.oar.parser.SendRequest("GET_reserved_nodes", \
                        username = username)

        # Get the full node dict list once for all
        # so that we can get the hostnames given their oar node id afterwards
        # when the reservations are checked.
        full_nodes_dict_list = self.GetNodes()
        #Put the full node list into a dictionary keyed by oar node id
        oar_id_node_dict = {}
        for node in full_nodes_dict_list:
            oar_id_node_dict[node['oar_id']] = node

        for resa in reservation_dict_list:
            logger.debug ("GetReservedNodes resa %s"%(resa))
            #dict list of hostnames and their site
            resa['reserved_nodes'] = \
                self.__get_hostnames_from_oar_node_ids(oar_id_node_dict,
                    resa['resource_ids'])

        #del resa['resource_ids']
        return reservation_dict_list

    def GetNodes(self, node_filter_dict=None, return_fields_list=None):
        """

        Make a list of iotlab nodes and their properties from information
            given by OAR. Search for specific nodes if some filters are
            specified. Nodes properties returned if no return_fields_list given:
            'hrn','archi','mobile','hostname','site','boot_state','node_id',
            'radio','posx','posy','oar_id','posz'.

        :param node_filter_dict: dictionnary of lists with node properties. For
            instance, if you want to look for a specific node with its hrn,
            the node_filter_dict should be {'hrn': [hrn_of_the_node]}
        :type node_filter_dict: dict
        :param return_fields_list: list of specific fields the user wants to be
            returned.
        :type return_fields_list: list
        :returns: list of dictionaries with node properties
        :rtype: list

        """
        node_dict_by_id = self.oar.parser.SendRequest("GET_resources_full")
        node_dict_list = node_dict_by_id.values()
        logger.debug (" IOTLAB_API GetNodes  node_filter_dict %s \
            return_fields_list %s " % (node_filter_dict, return_fields_list))
        #No  filtering needed return the list directly
        if not (node_filter_dict or return_fields_list):
            return node_dict_list

        return_node_list = []
        if node_filter_dict:
            for filter_key in node_filter_dict:
                try:
                    #Filter the node_dict_list by each value contained in the
                    #list node_filter_dict[filter_key]
                    for value in node_filter_dict[filter_key]:
                        for node in node_dict_list:
                            if node[filter_key] == value:
                                if return_fields_list:
                                    tmp = {}
                                    for k in return_fields_list:
                                        tmp[k] = node[k]
                                    return_node_list.append(tmp)
                                else:
                                    return_node_list.append(node)
                except KeyError:
                    logger.log_exc("GetNodes KeyError")
                    return


        return return_node_list





    def GetSites(self, site_filter_name_list=None, return_fields_list=None):
        """Returns the list of Iotlab's sites with the associated nodes and
        the sites' properties as dictionaries.

        Site properties:
        ['address_ids', 'slice_ids', 'name', 'node_ids', 'url', 'person_ids',
        'site_tag_ids', 'enabled', 'site', 'longitude', 'pcu_ids',
        'max_slivers', 'max_slices', 'ext_consortium_id', 'date_created',
        'latitude', 'is_public', 'peer_site_id', 'peer_id', 'abbreviated_name']
        Uses the OAR request GET_sites to find the Iotlab's sites.

        :param site_filter_name_list: used to specify specific sites
        :param return_fields_list: field that has to be returned
        :type site_filter_name_list: list
        :type return_fields_list: list


        """
        site_dict = self.oar.parser.SendRequest("GET_sites")
        #site_dict : dict where the key is the sit ename
        return_site_list = []
        if not (site_filter_name_list or return_fields_list):
            return_site_list = site_dict.values()
            return return_site_list

        for site_filter_name in site_filter_name_list:
            if site_filter_name in site_dict:
                if return_fields_list:
                    for field in return_fields_list:
                        tmp = {}
                        try:
                            tmp[field] = site_dict[site_filter_name][field]
                        except KeyError:
                            logger.error("GetSites KeyError %s " % (field))
                            return None
                    return_site_list.append(tmp)
                else:
                    return_site_list.append(site_dict[site_filter_name])

        return return_site_list


    #TODO : Check rights to delete person
    def DeletePerson(self, person_record):
        """Disable an existing account in iotlab LDAP.

        Users and techs can only delete themselves. PIs can only
            delete themselves and other non-PIs at their sites.
            ins can delete anyone.

        :param person_record: user's record
        :type person_record: dict
        :returns:  True if successful, False otherwise.
        :rtype: boolean

        .. todo:: CHECK THAT ONLY THE USER OR ADMIN CAN DEL HIMSELF.
        """
        #Disable user account in iotlab LDAP
        ret = self.ldap.LdapMarkUserAsDeleted(person_record)
        logger.warning("IOTLAB_API DeletePerson %s " % (person_record))
        return ret['bool']

    def DeleteSlice(self, slice_record):
        """Deletes the specified slice and kills the jobs associated with
            the slice if any,  using DeleteSliceFromNodes.

        :param slice_record: record of the slice, must contain oar_job_id, user
        :type slice_record: dict
        :returns: True if all the jobs in the slice have been deleted,
            or the list of jobs that could not be deleted otherwise.
        :rtype: list or boolean

         .. seealso:: DeleteSliceFromNodes

        """
        ret = self.DeleteSliceFromNodes(slice_record)
        delete_failed = None
        for job_id in ret:
            if False in ret[job_id]:
                if delete_failed is None:
                    delete_failed = []
                delete_failed.append(job_id)

        logger.info("IOTLAB_API DeleteSlice %s  answer %s"%(slice_record, \
                    delete_failed))
        return delete_failed or True











    #TODO AddPersonKey 04/07/2012 SA
    def AddPersonKey(self, person_uid, old_attributes_dict, new_key_dict):
        """Adds a new key to the specified account. Adds the key to the
            iotlab ldap, provided that the person_uid is valid.

        Non-admins can only modify their own keys.

        :param person_uid: user's iotlab login in LDAP
        :param old_attributes_dict: dict with the user's old sshPublicKey
        :param new_key_dict: dict with the user's new sshPublicKey
        :type person_uid: string


        :rtype: Boolean
        :returns: True if the key has been modified, False otherwise.

        """
        ret = self.ldap.LdapModify(person_uid, old_attributes_dict, \
                                                                new_key_dict)
        logger.warning("IOTLAB_API AddPersonKey EMPTY - DO NOTHING \r\n ")
        return ret['bool']

    def DeleteLeases(self, leases_id_list, slice_hrn):
        """

        Deletes several leases, based on their job ids and the slice
            they are associated with. Uses DeleteJobs to delete the jobs
            on OAR. Note that one slice can contain multiple jobs, and in this
            case all the jobs in the leases_id_list MUST belong to ONE slice,
            since there is only one slice hrn provided here.

        :param leases_id_list: list of job ids that belong to the slice whose
            slice hrn is provided.
        :param slice_hrn: the slice hrn.
        :type slice_hrn: string

        .. warning:: Does not have a return value since there was no easy
            way to handle failure when dealing with multiple job delete. Plus,
            there was no easy way to report it to the user.

        """
        logger.debug("IOTLAB_API DeleteLeases leases_id_list %s slice_hrn %s \
                \r\n " %(leases_id_list, slice_hrn))
        for job_id in leases_id_list:
            self.DeleteJobs(job_id, slice_hrn)

        return

    @staticmethod
    def _process_walltime(duration):
        """ Calculates the walltime in seconds from the duration in H:M:S
            specified in the RSpec.

        """
        if duration:
            # Fixing the walltime by adding a few delays.
            # First put the walltime in seconds oarAdditionalDelay = 20;
            #  additional delay for /bin/sleep command to
            # take in account  prologue and epilogue scripts execution
            # int walltimeAdditionalDelay = 240;  additional delay
            #for prologue/epilogue execution = $SERVER_PROLOGUE_EPILOGUE_TIMEOUT
            #in oar.conf
            # Put the duration in seconds first
            #desired_walltime = duration * 60
            desired_walltime = duration
            total_walltime = desired_walltime + 240 #+4 min Update SA 23/10/12
            sleep_walltime = desired_walltime  # 0 sec added Update SA 23/10/12
            walltime = []
            #Put the walltime back in str form
            #First get the hours
            walltime.append(str(total_walltime / 3600))
            total_walltime = total_walltime - 3600 * int(walltime[0])
            #Get the remaining minutes
            walltime.append(str(total_walltime / 60))
            total_walltime = total_walltime - 60 * int(walltime[1])
            #Get the seconds
            walltime.append(str(total_walltime))

        else:
            logger.log_exc(" __process_walltime duration null")

        return walltime, sleep_walltime

    @staticmethod
    def _create_job_structure_request_for_OAR(lease_dict):
        """ Creates the structure needed for a correct POST on OAR.
        Makes the timestamp transformation into the appropriate format.
        Sends the POST request to create the job with the resources in
        added_nodes.

        """

        nodeid_list = []
        reqdict = {}


        reqdict['workdir'] = '/tmp'
        reqdict['resource'] = "{network_address in ("

        for node in lease_dict['added_nodes']:
            logger.debug("\r\n \r\n OARrestapi \t \
            __create_job_structure_request_for_OAR node %s" %(node))

            # Get the ID of the node
            nodeid = node
            reqdict['resource'] += "'" + nodeid + "', "
            nodeid_list.append(nodeid)

        custom_length = len(reqdict['resource'])- 2
        reqdict['resource'] = reqdict['resource'][0:custom_length] + \
                                            ")}/nodes=" + str(len(nodeid_list))


        walltime, sleep_walltime = \
                    IotlabShell._process_walltime(\
                                     int(lease_dict['lease_duration']))


        reqdict['resource'] += ",walltime=" + str(walltime[0]) + \
                            ":" + str(walltime[1]) + ":" + str(walltime[2])
        reqdict['script_path'] = "/bin/sleep " + str(sleep_walltime)

        #In case of a scheduled experiment (not immediate)
        #To run an XP immediately, don't specify date and time in RSpec
        #They will be set to None.
        if lease_dict['lease_start_time'] is not '0':
            #Readable time accepted by OAR
            # converting timestamp to date in the local timezone tz = None 
            start_time = datetime.fromtimestamp( \
                int(lease_dict['lease_start_time']), tz=None).\
                strftime(lease_dict['time_format'])

            reqdict['reservation'] = str(start_time)
        #If there is not start time, Immediate XP. No need to add special
        # OAR parameters


        reqdict['type'] = "deploy"
        reqdict['directory'] = ""
        reqdict['name'] = "SFA_" + lease_dict['slice_user']

        return reqdict


    def LaunchExperimentOnOAR(self, added_nodes, slice_name, \
                        lease_start_time, lease_duration, slice_user=None):

        """
        Create a job request structure based on the information provided
        and post the job on OAR.
        :param added_nodes: list of nodes that belong to the described lease.
        :param slice_name: the slice hrn associated to the lease.
        :param lease_start_time: timestamp of the lease startting time.
        :param lease_duration: lease durationin minutes

        """
        lease_dict = {}
        lease_dict['lease_start_time'] = lease_start_time
        lease_dict['lease_duration'] = lease_duration
        lease_dict['added_nodes'] = added_nodes
        lease_dict['slice_name'] = slice_name
        lease_dict['slice_user'] = slice_user
        lease_dict['grain'] = self.GetLeaseGranularity()
        # I don't know why the SFATIME_FORMAT has changed...
        # from sfa.util.sfatime import SFATIME_FORMAT
        # Let's use a fixed format %Y-%m-%d %H:%M:%S
        #lease_dict['time_format'] = self.time_format
        lease_dict['time_format'] = '%Y-%m-%d %H:%M:%S'


        logger.debug("IOTLAB_API.PY \tLaunchExperimentOnOAR slice_user %s\
                             \r\n "  %(slice_user))
        #Create the request for OAR
        reqdict = self._create_job_structure_request_for_OAR(lease_dict)
         # first step : start the OAR job and update the job
        logger.debug("IOTLAB_API.PY \tLaunchExperimentOnOAR reqdict %s\
                             \r\n "  %(reqdict))

        answer = self.oar.POSTRequestToOARRestAPI('POST_job', \
                                                reqdict, slice_user)
        logger.debug("IOTLAB_API \tLaunchExperimentOnOAR jobid  %s " %(answer))
        try:
            jobid = answer['id']
        except KeyError:
            logger.log_exc("IOTLAB_API \tLaunchExperimentOnOAR \
                                Impossible to create job  %s "  %(answer))
            return None




        if jobid :
            logger.debug("IOTLAB_API \tLaunchExperimentOnOAR jobid %s \
                    added_nodes %s slice_user %s" %(jobid, added_nodes, \
                                                            slice_user))


        return jobid





    #Delete the jobs from job_iotlab table
    def DeleteSliceFromNodes(self, slice_record):
        """

        Deletes all the running or scheduled jobs of a given slice
            given its record.

        :param slice_record: record of the slice, must contain oar_job_id, user
        :type slice_record: dict

        :returns: dict of the jobs'deletion status. Success= True, Failure=
            False, for each job id.
        :rtype: dict

        """
        logger.debug("IOTLAB_API \t  DeleteSliceFromNodes %s "
                     % (slice_record))

        if isinstance(slice_record['oar_job_id'], list):
            oar_bool_answer = {}
            for job_id in slice_record['oar_job_id']:
                ret = self.DeleteJobs(job_id, slice_record['user'])

                oar_bool_answer.update(ret)

        else:
            oar_bool_answer = self.DeleteJobs(slice_record['oar_job_id'],
                                               slice_record['user'])

        return oar_bool_answer



    def GetLeaseGranularity(self):
        """ Returns the granularity of an experiment in the Iotlab testbed.
        OAR uses seconds for experiments duration , the granulaity is also
        defined in seconds.
        Experiments which last less than 10 min (600 sec) are invalid"""
        return self.grain



    @staticmethod
    def filter_lease(reservation_list, filter_type, filter_value ):
        """Filters the lease reservation list by removing each lease whose
        filter_type is not equal to the filter_value provided. Returns the list
        of leases in one slice, defined by the slice_hrn if filter_type
        is 'slice_hrn'. Otherwise, returns all leases scheduled starting from
        the filter_value if filter_type is 't_from'.

        :param reservation_list: leases list
        :type reservation_list: list of dictionary
        :param filter_type: can be either 't_from' or 'slice hrn'
        :type  filter_type: string
        :param filter_value: depending on the filter_type, can be the slice_hrn
            or can be defining a timespan.
        :type filter_value: if filter_type is 't_from', filter_value is int.
            if filter_type is 'slice_hrn', filter_value is a string.


        :returns: filtered_reservation_list, contains only leases running or
            scheduled in the given slice (wanted_slice).Dict keys are
            'lease_id','reserved_nodes','slice_id', 'state', 'user',
            'component_id_list','slice_hrn', 'resource_ids', 't_from', 't_until'
        :rtype: list of dict

        """
        filtered_reservation_list = list(reservation_list)
        logger.debug("IOTLAB_API \t filter_lease_name reservation_list %s" \
                        % (reservation_list))
        try:
            for reservation in reservation_list:
                if \
                (filter_type is 'slice_hrn' and \
                    reservation['slice_hrn'] != filter_value) or \
                (filter_type is 't_from' and \
                        reservation['t_from'] > filter_value):
                    filtered_reservation_list.remove(reservation)
        except TypeError:
            logger.log_exc("Iotlabshell filter_lease : filter_type %s \
                        filter_value %s not in lease" %(filter_type,
                            filter_value))

        return filtered_reservation_list

    # @staticmethod
    # def filter_lease_start_time(reservation_list, timespan):
    #     """Filters the lease reservation list by removing each lease whose
    #     slice_hrn is not the wanted_slice provided. Returns the list of leases
    #     in one slice (wanted_slice).

    #     """
    #     filtered_reservation_list = list(reservation_list)

    #     for reservation in reservation_list:
    #         if 't_from' in reservation and \
    #             reservation['t_from'] > timespan:
    #             filtered_reservation_list.remove(reservation)

    #     return filtered_reservation_list






#TODO FUNCTIONS SECTION 04/07/2012 SA


    ##TODO UpdateSlice 04/07/2012 SA || Commented out 28/05/13 SA
    ##Funciton should delete and create another job since oin iotlab slice=job
    #def UpdateSlice(self, auth, slice_id_or_name, slice_fields=None):
        #"""Updates the parameters of an existing slice with the values in
        #slice_fields.
        #Users may only update slices of which they are members.
        #PIs may update any of the slices at their sites, or any slices of
        #which they are members. Admins may update any slice.
        #Only PIs and admins may update max_nodes. Slices cannot be renewed
        #(by updating the expires parameter) more than 8 weeks into the future.
         #Returns 1 if successful, faults otherwise.
        #FROM PLC API DOC

        #"""
        #logger.warning("IOTLAB_API UpdateSlice EMPTY - DO NOTHING \r\n ")
        #return

    #Unused SA 30/05/13, we only update the user's key or we delete it.
    ##TODO UpdatePerson 04/07/2012 SA
    #def UpdatePerson(self, iotlab_hrn, federated_hrn, person_fields=None):
        #"""Updates a person. Only the fields specified in person_fields
        #are updated, all other fields are left untouched.
        #Users and techs can only update themselves. PIs can only update
        #themselves and other non-PIs at their sites.
        #Returns 1 if successful, faults otherwise.
        #FROM PLC API DOC

        #"""
        ##new_row = FederatedToIotlab(iotlab_hrn, federated_hrn)
        ##self.leases_db.testbed_session.add(new_row)
        ##self.leases_db.testbed_session.commit()

        #logger.debug("IOTLAB_API UpdatePerson EMPTY - DO NOTHING \r\n ")
        #return




    #TODO : test
    def DeleteKey(self, user_record, key_string):
        """Deletes a key in the LDAP entry of the specified user.

        Removes the key_string from the user's key list and updates the LDAP
            user's entry with the new key attributes.

        :param key_string: The ssh key to remove
        :param user_record: User's record
        :type key_string: string
        :type user_record: dict
        :returns: True if sucessful, False if not.
        :rtype: Boolean

        """

        all_user_keys = user_record['keys']
        all_user_keys.remove(key_string)
        new_attributes = {'sshPublicKey':all_user_keys}
        ret = self.ldap.LdapModifyUser(user_record, new_attributes)
        logger.debug("IOTLAB_API  DeleteKey  %s- " % (ret))
        return ret['bool']








    #Update slice unused, therefore  sfa_fields_to_iotlab_fields unused
    #SA 30/05/13
    #@staticmethod
    #def sfa_fields_to_iotlab_fields(sfa_type, hrn, record):
        #"""
        #"""

        #iotlab_record = {}
        ##for field in record:
        ##    iotlab_record[field] = record[field]

        #if sfa_type == "slice":
            ##instantion used in get_slivers ?
            #if not "instantiation" in iotlab_record:
                #iotlab_record["instantiation"] = "iotlab-instantiated"
            ##iotlab_record["hrn"] = hrn_to_pl_slicename(hrn)
            ##Unused hrn_to_pl_slicename because Iotlab's hrn already
            ##in the appropriate form SA 23/07/12
            #iotlab_record["hrn"] = hrn
            #logger.debug("IOTLAB_API.PY sfa_fields_to_iotlab_fields \
                        #iotlab_record %s  " %(iotlab_record['hrn']))
            #if "url" in record:
                #iotlab_record["url"] = record["url"]
            #if "description" in record:
                #iotlab_record["description"] = record["description"]
            #if "expires" in record:
                #iotlab_record["expires"] = int(record["expires"])

        ##nodes added by OAR only and then imported to SFA
        ##elif type == "node":
            ##if not "hostname" in iotlab_record:
                ##if not "hostname" in record:
                    ##raise MissingSfaInfo("hostname")
                ##iotlab_record["hostname"] = record["hostname"]
            ##if not "model" in iotlab_record:
                ##iotlab_record["model"] = "geni"

        ##One authority only
        ##elif type == "authority":
            ##iotlab_record["login_base"] = hrn_to_iotlab_login_base(hrn)

            ##if not "name" in iotlab_record:
                ##iotlab_record["name"] = hrn

            ##if not "abbreviated_name" in iotlab_record:
                ##iotlab_record["abbreviated_name"] = hrn

            ##if not "enabled" in iotlab_record:
                ##iotlab_record["enabled"] = True

            ##if not "is_public" in iotlab_record:
                ##iotlab_record["is_public"] = True

        #return iotlab_record










