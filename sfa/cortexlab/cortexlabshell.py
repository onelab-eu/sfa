"""
File containing the CortexlabShell, used to interact with nodes, users,
slices, leases and keys,  as well as the dedicated iotlab database and table,
holding information about which slice is running which job.

"""
from datetime import datetime

from sfa.util.sfalogging import logger
from sfa.util.sfatime import SFATIME_FORMAT

from sfa.iotlab.iotlabpostgres import LeaseTableXP
from sfa.cortexlab.LDAPapi import LDAPapi



from sfa.iotlab.iotlabxrn import xrn_object
from sfa.cortexlab.cortexlabnodes import CortexlabQueryNodes

class CortexlabShell():
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

        self.query_sites = CortexlabQueryNodes()
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
        return CortexlabShell._MINIMUM_DURATION

    #TODO  : Handling OR request in make_ldap_filters_from_records
    #instead of the for loop
    #over the records' list
    def GetPersons(self, person_filter=None):
        """
        Get the enabled users and their properties from Cortexlab LDAP.
        If a filter is specified, looks for the user whose properties match
        the filter, otherwise returns the whole enabled users'list.

        :param person_filter: Must be a list of dictionnaries with users
            properties when not set to None.
        :type person_filter: list of dict

        :returns: Returns a list of users whose accounts are enabled
            found in ldap.
        :rtype: list of dicts

        """
        logger.debug("CORTEXLAB_API \tGetPersons person_filter %s"
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



    def DeleteOneLease(self, lease_id, username):
        """

        Deletes the lease with the specified lease_id and username on OAR by
            posting a delete request to OAR.

        :param lease_id: Reservation identifier.
        :param username: user's iotlab login in LDAP.
        :type lease_id: Depends on what tou are using, could be integer or
            string
        :type username: string

        :returns: dictionary with the lease id and if delete has been successful
            (True) or no (False)
        :rtype: dict

        """

        # Here delete the lease specified
        answer = self.query_sites.delete_experiment(lease_id, username)

        # If the username is not necessary to delete the lease, then you can
        # remove it from the parameters, given that you propagate the changes
        # Return delete status so that you know if the delete has been
        # successuf or not


        if answer['status'] is True:
            ret = {lease_id: True}
        else:
            ret = {lease_id: False}
        logger.debug("CORTEXLAB_API \DeleteOneLease lease_id  %s \r\n answer %s \
                                username %s" % (lease_id, answer, username))
        return ret



    def GetNodesCurrentlyInUse(self):
        """Returns a list of all the nodes involved in a currently running
        experiment (and only the one not available at the moment the call to
        this method is issued)
        :rtype: list of nodes hostnames.
        """
        node_hostnames_list = []
        return node_hostnames_list


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
        mandatory_sfa_keys = ['reserved_nodes','lease_id']
        reservation_dict_list = \
                        self.query_sites.get_reserved_nodes(username = username)

        if len(reservation_dict_list) == 0:
            return []

        else:
            # Ensure mandatory keys are in the dict
            if not self.ensure_format_is_valid(reservation_dict_list,
                mandatory_sfa_keys):
                raise KeyError, "GetReservedNodes : Missing SFA mandatory keys"


        return reservation_dict_list

    @staticmethod
    def ensure_format_is_valid(list_dictionary_to_check, mandatory_keys_list):
        for entry in list_dictionary_to_check:
            if not all (key in entry for key in mandatory_keys_list):
                return False
        return True

    def GetNodes(self, node_filter_dict=None, return_fields_list=None):
        """

        Make a list of cortexlab nodes and their properties from information
            given by ?. Search for specific nodes if some filters are
            specified. Nodes properties returned if no return_fields_list given:
            'hrn','archi','mobile','hostname','site','boot_state','node_id',
            'radio','posx','posy,'posz'.

        :param node_filter_dict: dictionnary of lists with node properties. For
            instance, if you want to look for a specific node with its hrn,
            the node_filter_dict should be {'hrn': [hrn_of_the_node]}
        :type node_filter_dict: dict
        :param return_fields_list: list of specific fields the user wants to be
            returned.
        :type return_fields_list: list
        :returns: list of dictionaries with node properties. Mandatory
            properties hrn, site, hostname. Complete list (iotlab) ['hrn',
            'archi', 'mobile', 'hostname', 'site', 'mobility_type',
            'boot_state', 'node_id','radio', 'posx', 'posy', 'oar_id', 'posz']
            Radio, archi, mobile and position are useful to help users choose
            the appropriate nodes.
        :rtype: list

        :TODO: FILL IN THE BLANKS
        """

        # Here get full dict of nodes with all their properties.
        mandatory_sfa_keys = ['hrn', 'site', 'hostname']
        node_list_dict  = self.query_sites.get_all_nodes(node_filter_dict,
            return_fields_list)

        if len(node_list_dict) == 0:
            return_node_list = []

        else:
            # Ensure mandatory keys are in the dict
            if not self.ensure_format_is_valid(node_list_dict,
                mandatory_sfa_keys):
                raise KeyError, "GetNodes : Missing SFA mandatory keys"


        return_node_list = node_list_dict
        return return_node_list




    def GetSites(self, site_filter_name_list=None, return_fields_list=None):
        """Returns the list of Cortexlab's sites with the associated nodes and
        the sites' properties as dictionaries. Used in import.

        Site properties:
        ['address_ids', 'slice_ids', 'name', 'node_ids', 'url', 'person_ids',
        'site_tag_ids', 'enabled', 'site', 'longitude', 'pcu_ids',
        'max_slivers', 'max_slices', 'ext_consortium_id', 'date_created',
        'latitude', 'is_public', 'peer_site_id', 'peer_id', 'abbreviated_name']
        can be empty ( []): address_ids, slice_ids, pcu_ids, person_ids,
        site_tag_ids

        :param site_filter_name_list: used to specify specific sites
        :param return_fields_list: field that has to be returned
        :type site_filter_name_list: list
        :type return_fields_list: list
        :rtype: list of dicts

        """
        site_list_dict = self.query_sites.get_sites(site_filter_name_list,
                        return_fields_list)

        mandatory_sfa_keys = ['name', 'node_ids', 'longitude','site' ]

        if len(site_list_dict) == 0:
            return_site_list = []

        else:
            # Ensure mandatory keys are in the dict
            if not self.ensure_format_is_valid(site_list_dict,
                mandatory_sfa_keys):
                raise KeyError, "GetSites : Missing sfa mandatory keys"

        return_site_list = site_list_dict
        return return_site_list


    #TODO : Check rights to delete person
    def DeletePerson(self, person_record):
        """Disable an existing account in cortexlab LDAP.

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
        logger.warning("CORTEXLAB_API DeletePerson %s " % (person_record))
        return ret['bool']

    def DeleteSlice(self, slice_record):
        """Deletes the specified slice and kills the jobs associated with
            the slice if any,  using DeleteSliceFromNodes.

        :param slice_record: record of the slice, must contain experiment_id, user
        :type slice_record: dict
        :returns: True if all the jobs in the slice have been deleted,
            or the list of jobs that could not be deleted otherwise.
        :rtype: list or boolean

         .. seealso:: DeleteSliceFromNodes

        """
        ret = self.DeleteSliceFromNodes(slice_record)
        delete_failed = None
        for experiment_id in ret:
            if False in ret[experiment_id]:
                if delete_failed is None:
                    delete_failed = []
                delete_failed.append(experiment_id)

        logger.info("CORTEXLAB_API DeleteSlice %s  answer %s"%(slice_record, \
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
        logger.warning("CORTEXLAB_API AddPersonKey EMPTY - DO NOTHING \r\n ")
        return ret['bool']

    def DeleteLeases(self, leases_id_list, slice_hrn):
        """

        Deletes several leases, based on their experiment ids and the slice
            they are associated with. Uses DeleteOneLease to delete the
            experiment on the testbed. Note that one slice can contain multiple
            experiments, and in this
            case all the experiments in the leases_id_list MUST belong to this
            same slice, since there is only one slice hrn provided here.

        :param leases_id_list: list of job ids that belong to the slice whose
            slice hrn is provided.
        :param slice_hrn: the slice hrn.
        :type slice_hrn: string

        .. warning:: Does not have a return value since there was no easy
            way to handle failure when dealing with multiple job delete. Plus,
            there was no easy way to report it to the user.

        """
        logger.debug("CORTEXLAB_API DeleteLeases leases_id_list %s slice_hrn %s \
                \r\n " %(leases_id_list, slice_hrn))
        for experiment_id in leases_id_list:
            self.DeleteOneLease(experiment_id, slice_hrn)

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
                    CortexlabShell._process_walltime(\
                                     int(lease_dict['lease_duration']))


        reqdict['resource'] += ",walltime=" + str(walltime[0]) + \
                            ":" + str(walltime[1]) + ":" + str(walltime[2])
        reqdict['script_path'] = "/bin/sleep " + str(sleep_walltime)

        #In case of a scheduled experiment (not immediate)
        #To run an XP immediately, don't specify date and time in RSpec
        #They will be set to None.
        if lease_dict['lease_start_time'] is not '0':
            #Readable time accepted by OAR
            start_time = datetime.fromtimestamp( \
                int(lease_dict['lease_start_time'])).\
                strftime(lease_dict['time_format'])
            reqdict['reservation'] = start_time
        #If there is not start time, Immediate XP. No need to add special
        # OAR parameters


        reqdict['type'] = "deploy"
        reqdict['directory'] = ""
        reqdict['name'] = "SFA_" + lease_dict['slice_user']

        return reqdict


    def LaunchExperimentOnTestbed(self, added_nodes, slice_name, \
                        lease_start_time, lease_duration, slice_user=None):

        """
        Create an experiment request structure based on the information provided
        and schedule/run the experiment on the testbed  by reserving the nodes.
        :param added_nodes: list of nodes that belong to the described lease.
        :param slice_name: the slice hrn associated to the lease.
        :param lease_start_time: timestamp of the lease startting time.
        :param lease_duration: lease duration in minutes

        """
        lease_dict = {}
        # Add in the dict whatever is necessary to create the experiment on
        # the testbed
        lease_dict['lease_start_time'] = lease_start_time
        lease_dict['lease_duration'] = lease_duration
        lease_dict['added_nodes'] = added_nodes
        lease_dict['slice_name'] = slice_name
        lease_dict['slice_user'] = slice_user
        lease_dict['grain'] = self.GetLeaseGranularity()



        answer = self.query_sites.schedule_experiment(lease_dict)
        try:
            experiment_id = answer['id']
        except KeyError:
            logger.log_exc("CORTEXLAB_API \tLaunchExperimentOnTestbed \
                                Impossible to create xp  %s "  %(answer))
            return None

        if experiment_id :
            logger.debug("CORTEXLAB_API \tLaunchExperimentOnTestbed \
                experiment_id %s added_nodes %s slice_user %s"
                %(experiment_id, added_nodes, slice_user))


        return experiment_id




    #Delete the jobs from job_iotlab table
    def DeleteSliceFromNodes(self, slice_record):
        """
        Deletes all the running or scheduled jobs of a given slice
            given its record.

        :param slice_record: record of the slice, must contain experiment_id,
        user
        :type slice_record: dict
        :returns: dict of the jobs'deletion status. Success= True, Failure=
            False, for each job id.
        :rtype: dict

        .. note: used in driver delete_sliver

        """
        logger.debug("CORTEXLAB_API \t  DeleteSliceFromNodes %s "
                     % (slice_record))

        if isinstance(slice_record['experiment_id'], list):
            experiment_bool_answer = {}
            for experiment_id in slice_record['experiment_id']:
                ret = self.DeleteOneLease(experiment_id, slice_record['user'])

                experiment_bool_answer.update(ret)

        else:
            experiment_bool_answer = [self.DeleteOneLease(
                                        slice_record['experiment_id'],
                                        slice_record['user'])]

        return experiment_bool_answer



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
    # def filter_lease_name(reservation_list, filter_value):
    #     filtered_reservation_list = list(reservation_list)
    #     logger.debug("CORTEXLAB_API \t filter_lease_name reservation_list %s" \
    #                     % (reservation_list))
    #     for reservation in reservation_list:
    #         if 'slice_hrn' in reservation and \
    #             reservation['slice_hrn'] != filter_value:
    #             filtered_reservation_list.remove(reservation)

    #     logger.debug("CORTEXLAB_API \t filter_lease_name filtered_reservation_list %s" \
    #                     % (filtered_reservation_list))
    #     return filtered_reservation_list

    # @staticmethod
    # def filter_lease_start_time(reservation_list, filter_value):
    #     filtered_reservation_list = list(reservation_list)

    #     for reservation in reservation_list:
    #         if 't_from' in reservation and \
    #             reservation['t_from'] > filter_value:
    #             filtered_reservation_list.remove(reservation)

    #     return filtered_reservation_list

    def complete_leases_info(self, unfiltered_reservation_list, db_xp_dict):

        """Check that the leases list of dictionaries contains the appropriate
        fields and piece of information here
        :param unfiltered_reservation_list: list of leases to be completed.
        :param db_xp_dict: leases information in the lease_sfa table
        :returns local_unfiltered_reservation_list: list of leases completed.
        list of dictionaries describing the leases, with all the needed
        information (sfa,ldap,nodes)to identify one particular lease.
        :returns testbed_xp_list: list of experiments'ids running or scheduled
        on the testbed.
        :rtype local_unfiltered_reservation_list: list of dict
        :rtype testbed_xp_list: list

        """
        testbed_xp_list = []
        local_unfiltered_reservation_list = list(unfiltered_reservation_list)
        # slice_hrn and lease_id are in the lease_table,
        # so they are in the db_xp_dict.
        # component_id_list : list of nodes xrns
        # reserved_nodes : list of nodes' hostnames
        # slice_id : slice urn, can be made from the slice hrn using hrn_to_urn
        for resa in local_unfiltered_reservation_list:

            #Construct list of scheduled experiments (runing, waiting..)
            testbed_xp_list.append(resa['lease_id'])
            #If there is information on the experiment in the lease table
            #(slice used and experiment id), meaning the experiment was created
            # using sfa
            if resa['lease_id'] in db_xp_dict:
                xp_info = db_xp_dict[resa['lease_id']]
                logger.debug("CORTEXLAB_API \tGetLeases xp_info %s"
                          % (xp_info))
                resa['slice_hrn'] = xp_info['slice_hrn']
                resa['slice_id'] = hrn_to_urn(resa['slice_hrn'], 'slice')

            #otherwise, assume it is a cortexlab slice, created via the
            # cortexlab portal
            else:
                resa['slice_id'] = hrn_to_urn(self.root_auth + '.' +
                                              resa['user'] + "_slice", 'slice')
                resa['slice_hrn'] = Xrn(resa['slice_id']).get_hrn()

            resa['component_id_list'] = []
            #Transform the hostnames into urns (component ids)
            for node in resa['reserved_nodes']:

                iotlab_xrn = xrn_object(self.root_auth, node)
                resa['component_id_list'].append(iotlab_xrn.urn)

        return local_unfiltered_reservation_list, testbed_xp_list


#TODO FUNCTIONS SECTION 04/07/2012 SA

    ##TODO : Is UnBindObjectFromPeer still necessary ? Currently does nothing
    ##04/07/2012 SA
    #@staticmethod
    #def UnBindObjectFromPeer( auth, object_type, object_id, shortname):
        #""" This method is a hopefully temporary hack to let the sfa correctly
        #detach the objects it creates from a remote peer object. This is
        #needed so that the sfa federation link can work in parallel with
        #RefreshPeer, as RefreshPeer depends on remote objects being correctly
        #marked.
        #Parameters:
        #auth : struct, API authentication structure
            #AuthMethod : string, Authentication method to use
        #object_type : string, Object type, among 'site','person','slice',
        #'node','key'
        #object_id : int, object_id
        #shortname : string, peer shortname
        #FROM PLC DOC

        #"""
        #logger.warning("CORTEXLAB_API \tUnBindObjectFromPeer EMPTY-\
                        #DO NOTHING \r\n ")
        #return

    ##TODO Is BindObjectToPeer still necessary ? Currently does nothing
    ##04/07/2012 SA
    #|| Commented out 28/05/13 SA
    #def BindObjectToPeer(self, auth, object_type, object_id, shortname=None, \
                                                    #remote_object_id=None):
        #"""This method is a hopefully temporary hack to let the sfa correctly
        #attach the objects it creates to a remote peer object. This is needed
        #so that the sfa federation link can work in parallel with RefreshPeer,
        #as RefreshPeer depends on remote objects being correctly marked.
        #Parameters:
        #shortname : string, peer shortname
        #remote_object_id : int, remote object_id, set to 0 if unknown
        #FROM PLC API DOC

        #"""
        #logger.warning("CORTEXLAB_API \tBindObjectToPeer EMPTY - DO NOTHING \r\n ")
        #return

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
        #logger.warning("CORTEXLAB_API UpdateSlice EMPTY - DO NOTHING \r\n ")
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

        #logger.debug("CORTEXLAB_API UpdatePerson EMPTY - DO NOTHING \r\n ")
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
        logger.debug("CORTEXLAB_API  DeleteKey  %s- " % (ret))
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
            #logger.debug("CORTEXLAB_API.PY sfa_fields_to_iotlab_fields \
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










