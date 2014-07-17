"""
Implements what a driver should provide for SFA to work.
"""
from datetime import datetime
from sfa.util.faults import SliverDoesNotExist, Forbidden
from sfa.util.sfalogging import logger

from sfa.storage.model import RegRecord, RegUser, RegSlice, RegKey
from sfa.util.sfatime import utcparse, datetime_to_string
from sfa.trust.certificate import Keypair, convert_public_key

from sfa.trust.hierarchy import Hierarchy
from sfa.trust.gid import create_uuid

from sfa.managers.driver import Driver
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec

from sfa.iotlab.iotlabxrn import IotlabXrn, xrn_object, xrn_to_hostname
from sfa.util.xrn import Xrn, hrn_to_urn, get_authority, urn_to_hrn
from sfa.iotlab.iotlabaggregate import IotlabAggregate

from sfa.iotlab.iotlabslices import IotlabSlices

from sfa.trust.credential import Credential
from sfa.storage.model import SliverAllocation

from sfa.iotlab.iotlabshell import IotlabShell
from sqlalchemy.orm import joinedload
from sfa.iotlab.iotlabpostgres import LeaseTableXP

class IotlabDriver(Driver):
    """ Iotlab Driver class inherited from Driver generic class.

    Contains methods compliant with the SFA standard and the testbed
        infrastructure (calls to LDAP and OAR).

    .. seealso::: Driver class

    """
    def __init__(self, api):
        """

        Sets the iotlab SFA config parameters,
            instanciates the testbed api .

        :param api: SfaApi configuration object. Holds reference to the
            database.
        :type api: SfaApi object

        """
        Driver.__init__(self, api)
        self.api = api
        config = api.config
        self.testbed_shell = IotlabShell(config)
        self.cache = None

    def GetPeers(self, peer_filter=None ):
        """ Gathers registered authorities in SFA DB and looks for specific peer
        if peer_filter is specified.
        :param peer_filter: name of the site authority looked for.
        :type peer_filter: string
        :returns: list of records.

        """

        existing_records = {}
        existing_hrns_by_types = {}
        logger.debug("IOTLAB_API \tGetPeers peer_filter %s " % (peer_filter))
        query = self.api.dbsession().query(RegRecord)
        all_records = query.filter(RegRecord.type.like('%authority%')).all()

        for record in all_records:
            existing_records[(record.hrn, record.type)] = record
            if record.type not in existing_hrns_by_types:
                existing_hrns_by_types[record.type] = [record.hrn]
            else:
                existing_hrns_by_types[record.type].append(record.hrn)

        logger.debug("IOTLAB_API \tGetPeer\texisting_hrns_by_types %s "
                     % (existing_hrns_by_types))
        records_list = []

        try:
            if peer_filter:
                records_list.append(existing_records[(peer_filter,
                                                     'authority')])
            else:
                for hrn in existing_hrns_by_types['authority']:
                    records_list.append(existing_records[(hrn, 'authority')])

            logger.debug("IOTLAB_API \tGetPeer \trecords_list  %s "
                         % (records_list))

        except KeyError:
            pass

        return_records = records_list
        logger.debug("IOTLAB_API \tGetPeer return_records %s "
                     % (return_records))
        return return_records

    def GetKeys(self, key_filter=None):
        """Returns a dict of dict based on the key string. Each dict entry
        contains the key id, the ssh key, the user's email and the
        user's hrn.
        If key_filter is specified and is an array of key identifiers,
        only keys matching the filter will be returned.

        Admin may query all keys. Non-admins may only query their own keys.
        FROM PLC API DOC

        :returns: dict with ssh key as key and dicts as value.
        :rtype: dict
        """
        query = self.api.dbsession().query(RegKey)
        if key_filter is None:
            keys = query.options(joinedload('reg_user')).all()
        else:
            constraint = RegKey.key.in_(key_filter)
            keys = query.options(joinedload('reg_user')).filter(constraint).all()

        key_dict = {}
        for key in keys:
            key_dict[key.key] = {'key_id': key.key_id, 'key': key.key,
                                 'email': key.reg_user.email,
                                 'hrn': key.reg_user.hrn}

        #ldap_rslt = self.ldap.LdapSearch({'enabled']=True})
        #user_by_email = dict((user[1]['mail'][0], user[1]['sshPublicKey']) \
                                        #for user in ldap_rslt)

        logger.debug("IOTLAB_API  GetKeys  -key_dict %s \r\n " % (key_dict))
        return key_dict



    def AddPerson(self, record):
        """

        Adds a new account. Any fields specified in records are used,
            otherwise defaults are used. Creates an appropriate login by calling
            LdapAddUser.

        :param record: dictionary with the sfa user's properties.
        :returns: a dicitonary with the status. If successful, the dictionary
            boolean is set to True and there is a 'uid' key with the new login
            added to LDAP, otherwise the bool is set to False and a key
            'message' is in the dictionary, with the error message.
        :rtype: dict

        """
        ret = self.testbed_shell.ldap.LdapAddUser(record)

        if ret['bool'] is True:
            record['hrn'] = self.testbed_shell.root_auth + '.' + ret['uid']
            logger.debug("IOTLAB_API AddPerson return code %s record %s  "
                         % (ret, record))
            self.__add_person_to_db(record)
        return ret

    def __add_person_to_db(self, user_dict):
        """
        Add a federated user straight to db when the user issues a lease
        request with iotlab nodes and that he has not registered with iotlab
        yet (that is he does not have a LDAP entry yet).
        Uses parts of the routines in IotlabImport when importing user from
        LDAP. Called by AddPerson, right after LdapAddUser.
        :param user_dict: Must contain email, hrn and pkey to get a GID
        and be added to the SFA db.
        :type user_dict: dict

        """
        query = self.api.dbsession().query(RegUser)
        check_if_exists = query.filter_by(email = user_dict['email']).first()
        #user doesn't exists
        if not check_if_exists:
            logger.debug("__add_person_to_db \t Adding %s \r\n \r\n \
                                            " %(user_dict))
            hrn = user_dict['hrn']
            person_urn = hrn_to_urn(hrn, 'user')
            try:
                pubkey = user_dict['pkey']
                pkey = convert_public_key(pubkey)
            except TypeError:
                #key not good. create another pkey
                logger.warn('__add_person_to_db: no public key or unable to convert public \
                                    key for %s' %(hrn ))
                pkey = Keypair(create=True)


            if pubkey is not None and pkey is not None :
                hierarchy = Hierarchy()
                person_gid = hierarchy.create_gid(person_urn, create_uuid(), \
                                pkey)
                if user_dict['email']:
                    logger.debug("__add_person_to_db \r\n \r\n \
                        IOTLAB IMPORTER PERSON EMAIL OK email %s "\
                        %(user_dict['email']))
                    person_gid.set_email(user_dict['email'])

            user_record = RegUser(hrn=hrn , pointer= '-1', \
                                    authority=get_authority(hrn), \
                                    email=user_dict['email'], gid = person_gid)
            #user_record.reg_keys = [RegKey(user_dict['pkey'])]
            user_record.just_created()
            self.api.dbsession().add (user_record)
            self.api.dbsession().commit()
        return



    def _sql_get_slice_info(self, slice_filter):
        """
        Get the slice record based on the slice hrn. Fetch the record of the
        user associated with the slice by using joinedload based on the
        reg_researchers relationship.

        :param slice_filter: the slice hrn we are looking for
        :type slice_filter: string
        :returns: the slice record enhanced with the user's information if the
            slice was found, None it wasn't.

        :rtype: dict or None.
        """
        #DO NOT USE RegSlice - reg_researchers to get the hrn
        #of the user otherwise will mess up the RegRecord in
        #Resolve, don't know why - SA 08/08/2012

        #Only one entry for one user  = one slice in testbed_xp table
        #slicerec = dbsession.query(RegRecord).filter_by(hrn = slice_filter).first()

        raw_slicerec = self.api.dbsession().query(RegSlice).options(joinedload('reg_researchers')).filter_by(hrn=slice_filter).first()
        #raw_slicerec = self.api.dbsession().query(RegRecord).filter_by(hrn = slice_filter).first()
        if raw_slicerec:
            #load_reg_researchers
            #raw_slicerec.reg_researchers
            raw_slicerec = raw_slicerec.__dict__
            logger.debug(" IOTLAB_API \t  _sql_get_slice_info slice_filter %s  \
                            raw_slicerec %s" % (slice_filter, raw_slicerec))
            slicerec = raw_slicerec
            #only one researcher per slice so take the first one
            #slicerec['reg_researchers'] = raw_slicerec['reg_researchers']
            #del slicerec['reg_researchers']['_sa_instance_state']
            return slicerec

        else:
            return None

    def _sql_get_slice_info_from_user(self, slice_filter):
        """
        Get the slice record based on the user recordid by using a joinedload
        on the relationship reg_slices_as_researcher. Format the sql record
        into a dict with the mandatory fields for user and slice.
        :returns: dict with slice record and user record if the record was found
        based on the user's id, None if not..
        :rtype:dict or None..
        """
        #slicerec = dbsession.query(RegRecord).filter_by(record_id = slice_filter).first()
        raw_slicerec = self.api.dbsession().query(RegUser).options(joinedload('reg_slices_as_researcher')).filter_by(record_id=slice_filter).first()
        #raw_slicerec = self.api.dbsession().query(RegRecord).filter_by(record_id = slice_filter).first()
        #Put it in correct order
        user_needed_fields = ['peer_authority', 'hrn', 'last_updated',
                              'classtype', 'authority', 'gid', 'record_id',
                              'date_created', 'type', 'email', 'pointer']
        slice_needed_fields = ['peer_authority', 'hrn', 'last_updated',
                               'classtype', 'authority', 'gid', 'record_id',
                               'date_created', 'type', 'pointer']
        if raw_slicerec:
            #raw_slicerec.reg_slices_as_researcher
            raw_slicerec = raw_slicerec.__dict__
            slicerec = {}
            slicerec = \
                dict([(k, raw_slicerec[
                    'reg_slices_as_researcher'][0].__dict__[k])
                    for k in slice_needed_fields])
            slicerec['reg_researchers'] = dict([(k, raw_slicerec[k])
                                                for k in user_needed_fields])
             #TODO Handle multiple slices for one user SA 10/12/12
                        #for now only take the first slice record associated to the rec user
                        ##slicerec  = raw_slicerec['reg_slices_as_researcher'][0].__dict__
                        #del raw_slicerec['reg_slices_as_researcher']
                        #slicerec['reg_researchers'] = raw_slicerec
                        ##del slicerec['_sa_instance_state']

            return slicerec

        else:
            return None



    def _get_slice_records(self, slice_filter=None,
                           slice_filter_type=None):
        """
        Get the slice record depending on the slice filter and its type.
        :param slice_filter: Can be either the slice hrn or the user's record
        id.
        :type slice_filter: string
        :param slice_filter_type: describes the slice filter type used, can be
        slice_hrn or record_id_user
        :type: string
        :returns: the slice record
        :rtype:dict
        .. seealso::_sql_get_slice_info_from_user
        .. seealso:: _sql_get_slice_info
        """

        #Get list of slices based on the slice hrn
        if slice_filter_type == 'slice_hrn':

            #if get_authority(slice_filter) == self.root_auth:
                #login = slice_filter.split(".")[1].split("_")[0]

            slicerec = self._sql_get_slice_info(slice_filter)

            if slicerec is None:
                return None
                #return login, None

        #Get slice based on user id
        if slice_filter_type == 'record_id_user':

            slicerec = self._sql_get_slice_info_from_user(slice_filter)

        if slicerec:
            fixed_slicerec_dict = slicerec
            #At this point if there is no login it means
            #record_id_user filter has been used for filtering
            #if login is None :
                ##If theslice record is from iotlab
                #if fixed_slicerec_dict['peer_authority'] is None:
                    #login = fixed_slicerec_dict['hrn'].split(".")[1].split("_")[0]
            #return login, fixed_slicerec_dict
            return fixed_slicerec_dict
        else:
            return None



    def GetSlices(self, slice_filter=None, slice_filter_type=None,
                  login=None):
        """Get the slice records from the iotlab db and add lease information
            if any.

        :param slice_filter: can be the slice hrn or slice record id in the db
            depending on the slice_filter_type.
        :param slice_filter_type: defines the type of the filtering used, Can be
            either 'slice_hrn' or "record_id'.
        :type slice_filter: string
        :type slice_filter_type: string
        :returns: a slice dict if slice_filter  and slice_filter_type
            are specified and a matching entry is found in the db. The result
            is put into a list.Or a list of slice dictionnaries if no filters
            arespecified.

        :rtype: list

        """
        #login = None
        authorized_filter_types_list = ['slice_hrn', 'record_id_user']
        return_slicerec_dictlist = []

        #First try to get information on the slice based on the filter provided
        if slice_filter_type in authorized_filter_types_list:
            fixed_slicerec_dict = self._get_slice_records(slice_filter,
                                                    slice_filter_type)
            # if the slice was not found in the sfa db
            if fixed_slicerec_dict is None:
                return return_slicerec_dictlist

            slice_hrn = fixed_slicerec_dict['hrn']

            logger.debug(" IOTLAB_API \tGetSlices login %s \
                            slice record %s slice_filter %s \
                            slice_filter_type %s " % (login,
                            fixed_slicerec_dict, slice_filter,
                            slice_filter_type))


            #Now we have the slice record fixed_slicerec_dict, get the
            #jobs associated to this slice
            leases_list = []

            leases_list = self.GetLeases(login=login)
            #If no job is running or no job scheduled
            #return only the slice record
            if leases_list == [] and fixed_slicerec_dict:
                return_slicerec_dictlist.append(fixed_slicerec_dict)

            # if the jobs running don't belong to the user/slice we are looking
            # for
            leases_hrn = [lease['slice_hrn'] for lease in leases_list]
            if slice_hrn not in leases_hrn:
                return_slicerec_dictlist.append(fixed_slicerec_dict)
            #If several jobs for one slice , put the slice record into
            # each lease information dict
            for lease in leases_list:
                slicerec_dict = {}
                logger.debug("IOTLAB_API.PY  \tGetSlices slice_filter %s   \
                        \t lease['slice_hrn'] %s"
                             % (slice_filter, lease['slice_hrn']))
                if lease['slice_hrn'] == slice_hrn:
                    slicerec_dict['oar_job_id'] = lease['lease_id']
                    #Update lease dict with the slice record
                    if fixed_slicerec_dict:
                        fixed_slicerec_dict['oar_job_id'] = []
                        fixed_slicerec_dict['oar_job_id'].append(
                            slicerec_dict['oar_job_id'])
                        slicerec_dict.update(fixed_slicerec_dict)
                        #slicerec_dict.update({'hrn':\
                                        #str(fixed_slicerec_dict['slice_hrn'])})
                    slicerec_dict['slice_hrn'] = lease['slice_hrn']
                    slicerec_dict['hrn'] = lease['slice_hrn']
                    slicerec_dict['user'] = lease['user']
                    slicerec_dict.update(
                        {'list_node_ids':
                        {'hostname': lease['reserved_nodes']}})
                    slicerec_dict.update({'node_ids': lease['reserved_nodes']})



                    return_slicerec_dictlist.append(slicerec_dict)

                logger.debug("IOTLAB_API.PY  \tGetSlices  \
                        slicerec_dict %s return_slicerec_dictlist %s \
                        lease['reserved_nodes'] \
                        %s" % (slicerec_dict, return_slicerec_dictlist,
                               lease['reserved_nodes']))

            logger.debug("IOTLAB_API.PY  \tGetSlices  RETURN \
                        return_slicerec_dictlist  %s"
                          % (return_slicerec_dictlist))

            return return_slicerec_dictlist


        else:
            #Get all slices from the iotlab sfa database ,
            #put them in dict format
            #query_slice_list = dbsession.query(RegRecord).all()
            query_slice_list = \
                self.api.dbsession().query(RegSlice).options(joinedload('reg_researchers')).all()

            for record in query_slice_list:
                tmp = record.__dict__
                tmp['reg_researchers'] = tmp['reg_researchers'][0].__dict__
                #del tmp['reg_researchers']['_sa_instance_state']
                return_slicerec_dictlist.append(tmp)
                #return_slicerec_dictlist.append(record.__dict__)

            #Get all the jobs reserved nodes
            leases_list = self.testbed_shell.GetReservedNodes()

            for fixed_slicerec_dict in return_slicerec_dictlist:
                slicerec_dict = {}
                #Check if the slice belongs to a iotlab user
                if fixed_slicerec_dict['peer_authority'] is None:
                    owner = fixed_slicerec_dict['hrn'].split(
                        ".")[1].split("_")[0]
                else:
                    owner = None
                for lease in leases_list:
                    if owner == lease['user']:
                        slicerec_dict['oar_job_id'] = lease['lease_id']

                        #for reserved_node in lease['reserved_nodes']:
                        logger.debug("IOTLAB_API.PY  \tGetSlices lease %s "
                                     % (lease))
                        slicerec_dict.update(fixed_slicerec_dict)
                        slicerec_dict.update({'node_ids':
                                              lease['reserved_nodes']})
                        slicerec_dict.update({'list_node_ids':
                                             {'hostname':
                                             lease['reserved_nodes']}})

                        #slicerec_dict.update({'hrn':\
                                    #str(fixed_slicerec_dict['slice_hrn'])})
                        #return_slicerec_dictlist.append(slicerec_dict)
                        fixed_slicerec_dict.update(slicerec_dict)

            logger.debug("IOTLAB_API.PY  \tGetSlices RETURN \
                        return_slicerec_dictlist %s \t slice_filter %s " \
                        %(return_slicerec_dictlist, slice_filter))

        return return_slicerec_dictlist

    def AddLeases(self, hostname_list, slice_record,
                  lease_start_time, lease_duration):

        """Creates a job in OAR corresponding to the information provided
        as parameters. Adds the job id and the slice hrn in the iotlab
        database so that we are able to know which slice has which nodes.

        :param hostname_list: list of nodes' OAR hostnames.
        :param slice_record: sfa slice record, must contain login and hrn.
        :param lease_start_time: starting time , unix timestamp format
        :param lease_duration: duration in minutes

        :type hostname_list: list
        :type slice_record: dict
        :type lease_start_time: integer
        :type lease_duration: integer
        :returns: job_id, can be None if the job request failed.

        """
        logger.debug("IOTLAB_API \r\n \r\n \t AddLeases hostname_list %s  \
                slice_record %s lease_start_time %s lease_duration %s  "\
                 %( hostname_list, slice_record , lease_start_time, \
                 lease_duration))

        #tmp = slice_record['reg-researchers'][0].split(".")
        username = slice_record['login']
        #username = tmp[(len(tmp)-1)]
        job_id = self.testbed_shell.LaunchExperimentOnOAR(hostname_list, \
                                    slice_record['hrn'], \
                                    lease_start_time, lease_duration, \
                                    username)
        if job_id is not None:
            start_time = \
                    datetime.fromtimestamp(int(lease_start_time)).\
                    strftime(self.testbed_shell.time_format)
            end_time = lease_start_time + lease_duration


            logger.debug("IOTLAB_API \r\n \r\n \t AddLeases TURN ON LOGGING SQL \
                        %s %s %s "%(slice_record['hrn'], job_id, end_time))


            logger.debug("IOTLAB_API \r\n \r\n \t AddLeases %s %s %s " \
                    %(type(slice_record['hrn']), type(job_id), type(end_time)))

            iotlab_ex_row = LeaseTableXP(slice_hrn = slice_record['hrn'],
                                                    experiment_id=job_id,
                                                    end_time= end_time)

            logger.debug("IOTLAB_API \r\n \r\n \t AddLeases iotlab_ex_row %s" \
                    %(iotlab_ex_row))
            self.api.dbsession().add(iotlab_ex_row)
            self.api.dbsession().commit()

            logger.debug("IOTLAB_API \t AddLeases hostname_list start_time %s "
                        %(start_time))

        return job_id

    def GetLeases(self, lease_filter_dict=None, login=None):
        """

        Get the list of leases from OAR with complete information
            about which slice owns which jobs and nodes.
            Two purposes:
            -Fetch all the jobs from OAR (running, waiting..)
            complete the reservation information with slice hrn
            found in lease_table . If not available in the table,
            assume it is a iotlab slice.
            -Updates the iotlab table, deleting jobs when necessary.

        :returns: reservation_list, list of dictionaries with 'lease_id',
            'reserved_nodes','slice_id', 'state', 'user', 'component_id_list',
            'slice_hrn', 'resource_ids', 't_from', 't_until'
        :rtype: list

        """

        unfiltered_reservation_list = self.testbed_shell.GetReservedNodes(login)

        reservation_list = []
        #Find the slice associated with this user iotlab ldap uid
        logger.debug(" IOTLAB_API.PY \tGetLeases login %s\
                        unfiltered_reservation_list %s "
                     % (login, unfiltered_reservation_list))
        #Create user dict first to avoid looking several times for
        #the same user in LDAP SA 27/07/12
        job_oar_list = []
        jobs_psql_query = self.api.dbsession().query(LeaseTableXP).all()
        jobs_psql_dict = dict([(row.experiment_id, row.__dict__)
                               for row in jobs_psql_query])
        #jobs_psql_dict = jobs_psql_dict)
        logger.debug("IOTLAB_API \tGetLeases jobs_psql_dict %s"
                     % (jobs_psql_dict))
        jobs_psql_id_list = [row.experiment_id for row in jobs_psql_query]

        for resa in unfiltered_reservation_list:
            logger.debug("IOTLAB_API \tGetLeases USER %s"
                         % (resa['user']))
            #Construct list of jobs (runing, waiting..) in oar
            job_oar_list.append(resa['lease_id'])
            #If there is information on the job in IOTLAB DB ]
            #(slice used and job id)
            if resa['lease_id'] in jobs_psql_dict:
                job_info = jobs_psql_dict[resa['lease_id']]
                logger.debug("IOTLAB_API \tGetLeases job_info %s"
                          % (job_info))
                resa['slice_hrn'] = job_info['slice_hrn']
                resa['slice_id'] = hrn_to_urn(resa['slice_hrn'], 'slice')

            #otherwise, assume it is a iotlab slice:
            else:
                resa['slice_id'] = hrn_to_urn(self.testbed_shell.root_auth \
                                            + '.' + resa['user'] + "_slice",
                                            'slice')
                resa['slice_hrn'] = Xrn(resa['slice_id']).get_hrn()

            resa['component_id_list'] = []
            #Transform the hostnames into urns (component ids)
            for node in resa['reserved_nodes']:

                iotlab_xrn = xrn_object(self.testbed_shell.root_auth, node)
                resa['component_id_list'].append(iotlab_xrn.urn)

        if lease_filter_dict:
            logger.debug("IOTLAB_API \tGetLeases  \
                    \r\n leasefilter %s" % ( lease_filter_dict))

            # filter_dict_functions = {
            # 'slice_hrn' : IotlabShell.filter_lease_name,
            # 't_from' : IotlabShell.filter_lease_start_time
            # }
            reservation_list = list(unfiltered_reservation_list)
            for filter_type in lease_filter_dict:
                logger.debug("IOTLAB_API \tGetLeases reservation_list %s" \
                    % (reservation_list))
                reservation_list = self.testbed_shell.filter_lease(
                        reservation_list,filter_type,
                        lease_filter_dict[filter_type] )

                # Filter the reservation list with a maximum timespan so that the
                # leases and jobs running after this timestamp do not appear
                # in the result leases.
                # if 'start_time' in :
                #     if resa['start_time'] < lease_filter_dict['start_time']:
                #        reservation_list.append(resa)


                # if 'name' in lease_filter_dict and \
                #     lease_filter_dict['name'] == resa['slice_hrn']:
                #     reservation_list.append(resa)


        if lease_filter_dict is None:
            reservation_list = unfiltered_reservation_list

        self.update_experiments_in_lease_table(job_oar_list, jobs_psql_id_list)

        logger.debug(" IOTLAB_API.PY \tGetLeases reservation_list %s"
                     % (reservation_list))
        return reservation_list



    def update_experiments_in_lease_table(self,
        experiment_list_from_testbed, experiment_list_in_db):
        """ Cleans the lease_table by deleting expired and cancelled jobs.

        Compares the list of experiment ids given by the testbed with the
        experiment ids that are already in the database, deletes the
        experiments that are no longer in the testbed experiment id list.

        :param  experiment_list_from_testbed: list of experiment ids coming
            from testbed
        :type experiment_list_from_testbed: list
        :param experiment_list_in_db: list of experiment ids from the sfa
            additionnal database.
        :type experiment_list_in_db: list

        :returns: None
        """
        #Turn the list into a set
        set_experiment_list_in_db = set(experiment_list_in_db)

        kept_experiments = set(experiment_list_from_testbed).intersection(set_experiment_list_in_db)
        logger.debug("\r\n \t update_experiments_in_lease_table \
                        experiment_list_in_db %s \r\n \
                        experiment_list_from_testbed %s \
                        kept_experiments %s "
                     % (set_experiment_list_in_db,
                      experiment_list_from_testbed, kept_experiments))
        deleted_experiments = set_experiment_list_in_db.difference(
            kept_experiments)
        deleted_experiments = list(deleted_experiments)
        if len(deleted_experiments) > 0:
            request = self.api.dbsession().query(LeaseTableXP)
            request.filter(LeaseTableXP.experiment_id.in_(deleted_experiments)).delete(synchronize_session='fetch')
            self.api.dbsession().commit()
        return


    def AddSlice(self, slice_record, user_record):
        """

        Add slice to the local iotlab sfa tables if the slice comes
            from a federated site and is not yet in the iotlab sfa DB,
            although the user has already a LDAP login.
            Called by verify_slice during lease/sliver creation.

        :param slice_record: record of slice, must contain hrn, gid, slice_id
            and authority of the slice.
        :type slice_record: dictionary
        :param user_record: record of the user
        :type user_record: RegUser

        """

        sfa_record = RegSlice(hrn=slice_record['hrn'],
                              gid=slice_record['gid'],
                              pointer=slice_record['slice_id'],
                              authority=slice_record['authority'])
        logger.debug("IOTLAB_API.PY AddSlice  sfa_record %s user_record %s"
                     % (sfa_record, user_record))
        sfa_record.just_created()
        self.api.dbsession().add(sfa_record)
        self.api.dbsession().commit()
        #Update the reg-researchers dependency table
        sfa_record.reg_researchers = [user_record]
        self.api.dbsession().commit()

        return

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
                    recslice_list = self.GetSlices(
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
                    recslice_list = self.GetSlices(
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
                         'name': recuser['hrn'],
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
        slice_list = self.GetSlices(slice_filter=slice_hrn,
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

    def get_user_record(self, hrn):
        """

        Returns the user record based on the hrn from the SFA DB .

        :param hrn: user's hrn
        :type hrn: string
        :returns: user record from SFA database
        :rtype: RegUser

        """
        return self.api.dbsession().query(RegRecord).filter_by(hrn=hrn).first()

    def testbed_name(self):
        """

        Returns testbed's name.
        :returns: testbed authority name.
        :rtype: string

        """
        return self.hrn


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
                        xrn_to_hostname(\
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



    def delete(self, slice_urns, options=None):
        """
        Deletes the lease associated with the slice hrn and the credentials
            if the slice belongs to iotlab. Answer to DeleteSliver.

        :param slice_urn: urn of the slice
        :type slice_urn: string


        :returns: 1 if the slice to delete was not found on iotlab,
            True if the deletion was successful, False otherwise otherwise.

        .. note:: Should really be named delete_leases because iotlab does
            not have any slivers, but only deals with leases. However,
            SFA api only have delete_sliver define so far. SA 13/05/2013
        .. note:: creds are unused, and are not used either in the dummy driver
             delete_sliver .
        """
        if options is None: options={}
        # collect sliver ids so we can update sliver allocation states after
        # we remove the slivers.
        aggregate = IotlabAggregate(self)
        slivers = aggregate.get_slivers(slice_urns)
        if slivers:
            # slice_id = slivers[0]['slice_id']
            node_ids = []
            sliver_ids = []
            sliver_jobs_dict = {}
            for sliver in slivers:
                node_ids.append(sliver['node_id'])
                sliver_ids.append(sliver['sliver_id'])
                job_id = sliver['sliver_id'].split('+')[-1].split('-')[0]
                sliver_jobs_dict[job_id] = sliver['sliver_id']
        logger.debug("IOTLABDRIVER.PY delete_sliver slivers %s slice_urns %s"
            % (slivers, slice_urns))
        slice_hrn = urn_to_hrn(slice_urns[0])[0]

        sfa_slice_list = self.GetSlices(slice_filter=slice_hrn,
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
            oar_bool_ans = self.testbed_shell.DeleteSliceFromNodes(
                                                                    sfa_slice)
            for job_id in oar_bool_ans:
                # if the job has not been successfully deleted
                # don't delete the associated sliver
                # remove it from the sliver list
                if oar_bool_ans[job_id] is False:
                    sliver = sliver_jobs_dict[job_id]
                    sliver_ids.remove(sliver)
            try:

                dbsession = self.api.dbsession()
                SliverAllocation.delete_allocations(sliver_ids, dbsession)
            except :
                logger.log_exc("IOTLABDRIVER.PY delete error ")

        # prepare return struct
        geni_slivers = []
        for sliver in slivers:
            geni_slivers.append(
                {'geni_sliver_urn': sliver['sliver_id'],
                 'geni_allocation_status': 'geni_unallocated',
                 'geni_expires': datetime_to_string(utcparse(sliver['expires']))})
        return geni_slivers




    def list_slices(self, creds, options):
        """Answer to ListSlices.

        List slices belonging to iotlab, returns slice urns list.
            No caching used. Options unused but are defined in the SFA method
            api prototype.

        :returns: slice urns list
        :rtype: list

        .. note:: creds and options are unused - SA 12/12/13
        """
        # look in cache first
        #if self.cache:
            #slices = self.cache.get('slices')
            #if slices:
                #logger.debug("PlDriver.list_slices returns from cache")
                #return slices

        # get data from db

        slices = self.GetSlices()
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
        .. warning:: SA 12/12/13 - Removed. should be done in iotlabimporter
        since users, keys and slice are managed by the LDAP.

        """
        # pointer = old_sfa_record['pointer']
        # old_sfa_record_type = old_sfa_record['type']

        # # new_key implemented for users only
        # if new_key and old_sfa_record_type not in ['user']:
        #     raise UnknownSfaType(old_sfa_record_type)

        # if old_sfa_record_type == "user":
        #     update_fields = {}
        #     all_fields = new_sfa_record
        #     for key in all_fields.keys():
        #         if key in ['key', 'password']:
        #             update_fields[key] = all_fields[key]

        #     if new_key:
        #         # must check this key against the previous one if it exists
        #         persons = self.testbed_shell.GetPersons([old_sfa_record])
        #         person = persons[0]
        #         keys = [person['pkey']]
        #         #Get all the person's keys
        #         keys_dict = self.GetKeys(keys)

        #         # Delete all stale keys, meaning the user has only one key
        #         #at a time
        #         #TODO: do we really want to delete all the other keys?
        #         #Is this a problem with the GID generation to have multiple
        #         #keys? SA 30/05/13
        #         key_exists = False
        #         if key in keys_dict:
        #             key_exists = True
        #         else:
        #             #remove all the other keys
        #             for key in keys_dict:
        #                 self.testbed_shell.DeleteKey(person, key)
        #             self.testbed_shell.AddPersonKey(
        #                 person, {'sshPublicKey': person['pkey']},
        #                 {'sshPublicKey': new_key})
        logger.warning ("UNDEFINED - Update should be done by the \
            iotlabimporter")
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
            if self.GetSlices(slice_filter=hrn,
                                slice_filter_type='slice_hrn'):
                ret = self.testbed_shell.DeleteSlice(sfa_record)
            return True

    def check_sliver_credentials(self, creds, urns):
        """Check that the sliver urns belongs to the slice specified in the
        credentials.

        :param urns: list of sliver urns.
        :type urns: list.
        :param creds: slice credentials.
        :type creds: Credential object.


        """
        # build list of cred object hrns
        slice_cred_names = []
        for cred in creds:
            slice_cred_hrn = Credential(cred=cred).get_gid_object().get_hrn()
            slicename = IotlabXrn(xrn=slice_cred_hrn).iotlab_slicename()
            slice_cred_names.append(slicename)

        # look up slice name of slivers listed in urns arg

        slice_ids = []
        for urn in urns:
            sliver_id_parts = Xrn(xrn=urn).get_sliver_id_parts()
            try:
                slice_ids.append(int(sliver_id_parts[0]))
            except ValueError:
                pass

        if not slice_ids:
            raise Forbidden("sliver urn not provided")

        slices = self.GetSlices(slice_ids)
        sliver_names = [single_slice['name'] for single_slice in slices]

        # make sure we have a credential for every specified sliver
        for sliver_name in sliver_names:
            if sliver_name not in slice_cred_names:
                msg = "Valid credential not found for target: %s" % sliver_name
                raise Forbidden(msg)

    ########################################
    ########## aggregate oriented
    ########################################

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

    # first 2 args are None in case of resource discovery
    def list_resources (self, version=None, options=None):
        if options is None: options={}
        aggregate = IotlabAggregate(self)
        rspec =  aggregate.list_resources(version=version, options=options)
        return rspec

    def describe(self, urns, version, options=None):
        if options is None: options={}
        aggregate = IotlabAggregate(self)
        return aggregate.describe(urns, version=version, options=options)

    def status (self, urns, options=None):
        if options is None: options={}
        aggregate = IotlabAggregate(self)
        desc =  aggregate.describe(urns, version='GENI 3')
        status = {'geni_urn': desc['geni_urn'],
                  'geni_slivers': desc['geni_slivers']}
        return status


    def allocate (self, urn, rspec_string, expiration, options=None):
        if options is None: options={}
        xrn = Xrn(urn)
        aggregate = IotlabAggregate(self)

        slices = IotlabSlices(self)
        peer = slices.get_peer(xrn.get_hrn())
        sfa_peer = slices.get_sfa_peer(xrn.get_hrn())

        caller_hrn = options.get('actual_caller_hrn', [])
        caller_xrn = Xrn(caller_hrn)
        caller_urn = caller_xrn.get_urn()

        logger.debug("IOTLABDRIVER.PY :: Allocate caller = %s" % (caller_urn))

        slice_record = {}
        users = options.get('geni_users', [])
        sfa_users = options.get('sfa_users', [])
        
        if sfa_users:
            user = None
            # Looking for the user who actually called the Allocate function in the list of users of the slice
            for u in sfa_users:
                if 'urn' in u and u['urn'] == caller_urn:
                    user = u
                    logger.debug("user = %s" % u)
            # If we find the user in the list we use it, else we take the 1st in the list as before
            if user:
                user_hrn = caller_hrn
            else:
                user = sfa_users[0]
                # XXX Always empty ??? no slice_record in the Allocate call
                #slice_record = sfa_users[0].get('slice_record', [])
                user_xrn = Xrn(sfa_users[0]['urn'])
                user_hrn = user_xrn.get_hrn()

            slice_record = user.get('slice_record', {})
            slice_record['user'] = {'keys': user['keys'],
                                    'email': user['email'],
                                    'hrn': user_hrn}
            slice_record['authority'] = xrn.get_authority_hrn() 

        logger.debug("IOTLABDRIVER.PY \t urn %s allocate options  %s "
                     % (urn, options))

        # parse rspec
        rspec = RSpec(rspec_string)
        # requested_attributes = rspec.version.get_slice_attributes()

        # ensure site record exists

        # ensure slice record exists

        current_slice = slices.verify_slice(xrn.hrn, slice_record, sfa_peer)
        logger.debug("IOTLABDRIVER.PY \t ===============allocate \t\
                            \r\n \r\n  current_slice %s" % (current_slice))
        # ensure person records exists

        # oui c'est degueulasse, le slice_record se retrouve modifie
        # dans la methode avec les infos du user, els infos sont propagees
        # dans verify_slice_leases
        logger.debug("IOTLABDRIVER.PY  BEFORE slices.verify_persons")
        persons = slices.verify_persons(xrn.hrn, slice_record, users,
                                        options=options)
        logger.debug("IOTLABDRIVER.PY  AFTER slices.verify_persons")
        # ensure slice attributes exists
        # slices.verify_slice_attributes(slice, requested_attributes,
                                    # options=options)

        # add/remove slice from nodes
        requested_xp_dict = self._process_requested_xp_dict(rspec)

        logger.debug("IOTLABDRIVER.PY \tallocate  requested_xp_dict %s "
                     % (requested_xp_dict))
        request_nodes = rspec.version.get_nodes_with_slivers()
        nodes_list = []
        for start_time in requested_xp_dict:
            lease = requested_xp_dict[start_time]
            for hostname in lease['hostname']:
                nodes_list.append(hostname)

        # nodes = slices.verify_slice_nodes(slice_record,request_nodes, peer)
        logger.debug("IOTLABDRIVER.PY \tallocate  nodes_list %s slice_record %s"
                     % (nodes_list, slice_record))

        # add/remove leases
        rspec_requested_leases = rspec.version.get_leases()
        leases = slices.verify_slice_leases(slice_record,
                                                requested_xp_dict, peer)
        logger.debug("IOTLABDRIVER.PY \tallocate leases  %s \
                        rspec_requested_leases %s" % (leases,
                        rspec_requested_leases))
         # update sliver allocations
        for hostname in nodes_list:
            client_id = hostname
            node_urn = xrn_object(self.testbed_shell.root_auth, hostname).urn
            component_id = node_urn
            if 'reg-urn' in current_slice:
                slice_urn = current_slice['reg-urn']
            else:
                slice_urn = current_slice['urn']
            for lease in leases:
                if hostname in lease['reserved_nodes']:
                    index = lease['reserved_nodes'].index(hostname)
                    sliver_hrn = '%s.%s-%s' % (self.hrn, lease['lease_id'],
                                   lease['resource_ids'][index] )
            sliver_id = Xrn(sliver_hrn, type='sliver').urn
            record = SliverAllocation(sliver_id=sliver_id, client_id=client_id,
                                      component_id=component_id,
                                      slice_urn = slice_urn,
                                      allocation_state='geni_allocated')
            record.sync(self.api.dbsession())

        return aggregate.describe([xrn.get_urn()], version=rspec.version)

    def provision(self, urns, options=None):
        if options is None: options={}
        # update users
        slices = IotlabSlices(self)
        aggregate = IotlabAggregate(self)
        slivers = aggregate.get_slivers(urns)
        current_slice = slivers[0]
        peer = slices.get_peer(current_slice['hrn'])
        sfa_peer = slices.get_sfa_peer(current_slice['hrn'])
        users = options.get('geni_users', [])
        # persons = slices.verify_persons(current_slice['hrn'],
            # current_slice, users, peer, sfa_peer, options=options)
        # slices.handle_peer(None, None, persons, peer)
        # update sliver allocation states and set them to geni_provisioned
        sliver_ids = [sliver['sliver_id'] for sliver in slivers]
        dbsession = self.api.dbsession()
        SliverAllocation.set_allocations(sliver_ids, 'geni_provisioned',
                                                                dbsession)
        version_manager = VersionManager()
        rspec_version = version_manager.get_version(options[
                                                        'geni_rspec_version'])
        return self.describe(urns, rspec_version, options=options)
