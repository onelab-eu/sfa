from datetime import datetime

from sfa.util.sfalogging import logger

from sfa.storage.alchemy import dbsession
from sqlalchemy.orm import joinedload
from sfa.storage.model import RegRecord, RegUser, RegSlice, RegKey
from sfa.senslab.slabpostgres import SlabDB, slab_dbsession, SenslabXP

from sfa.senslab.OARrestapi import  OARrestapi
from sfa.senslab.LDAPapi import LDAPapi

from sfa.util.xrn import Xrn, hrn_to_urn, get_authority

from sfa.trust.certificate import Keypair, convert_public_key
from sfa.trust.gid import create_uuid
from sfa.trust.hierarchy import Hierarchy

                                                                
from sfa.senslab.slabaggregate import SlabAggregate, slab_xrn_to_hostname, \
                                                            slab_xrn_object

class SlabTestbedAPI():
    
    def __init__(self, config):
        self.oar = OARrestapi()
        self.ldap = LDAPapi()
        self.time_format = "%Y-%m-%d %H:%M:%S"
        self.root_auth = config.SFA_REGISTRY_ROOT_AUTH
        self.grain = 600 # 10 mins lease
        return
     
     
                
    #TODO clean GetPeers. 05/07/12SA   
    @staticmethod     
    def GetPeers ( auth = None, peer_filter=None ):
        """ Gathers registered authorities in SFA DB and looks for specific peer
        if peer_filter is specified. 
        :returns list of records.
     
        """

        existing_records = {}
        existing_hrns_by_types = {}
        logger.debug("SLABDRIVER \tGetPeers auth = %s, peer_filter %s, \
                    " %(auth , peer_filter))
        all_records = dbsession.query(RegRecord).filter(RegRecord.type.like('%authority%')).all()
        
        for record in all_records:
            existing_records[(record.hrn, record.type)] = record
            if record.type not in existing_hrns_by_types:
                existing_hrns_by_types[record.type] = [record.hrn]
            else:
                existing_hrns_by_types[record.type].append(record.hrn)

                        
        logger.debug("SLABDRIVER \tGetPeer\texisting_hrns_by_types %s "\
                                             %( existing_hrns_by_types))
        records_list = [] 
      
        try: 
            if peer_filter:
                records_list.append(existing_records[(peer_filter,'authority')])
            else :
                for hrn in existing_hrns_by_types['authority']:
                    records_list.append(existing_records[(hrn,'authority')])
                    
            logger.debug("SLABDRIVER \tGetPeer \trecords_list  %s " \
                                            %(records_list))

        except KeyError:
            pass
                
        return_records = records_list
        #if not peer_filter :
            #return records_list

       
        logger.debug("SLABDRIVER \tGetPeer return_records %s " \
                                                    %(return_records))
        return return_records
        

          
    #TODO  : Handling OR request in make_ldap_filters_from_records 
    #instead of the for loop 
    #over the records' list
    def GetPersons(self, person_filter=None):
        """
        person_filter should be a list of dictionnaries when not set to None.
        Returns a list of users whose accounts are enabled found in ldap.
       
        """
        logger.debug("SLABDRIVER \tGetPersons person_filter %s" \
                                                    %(person_filter))
        person_list = []
        if person_filter and isinstance(person_filter, list):
        #If we are looking for a list of users (list of dict records)
        #Usually the list contains only one user record
            for searched_attributes in person_filter:
                
                #Get only enabled user accounts in senslab LDAP : 
                #add a filter for make_ldap_filters_from_record
                person = self.ldap.LdapFindUser(searched_attributes, \
                                is_user_enabled=True)
                #If a person was found, append it to the list
                if person:
                    person_list.append(person)
                    
            #If the list is empty, return None
            if len(person_list) is 0:
                person_list = None
          
        else:
            #Get only enabled user accounts in senslab LDAP : 
            #add a filter for make_ldap_filters_from_record
            person_list  = self.ldap.LdapFindUser(is_user_enabled=True)  

        return person_list




    def GetTimezone(self):
        """ Get the OAR servier time and timezone.
        Unused SA 16/11/12"""
        server_timestamp, server_tz = self.oar.parser.\
                                            SendRequest("GET_timezone")
        return server_timestamp, server_tz
    



    def DeleteJobs(self, job_id, username): 
        
        """Delete a job on OAR given its job id and the username assoaciated. 
        Posts a delete request to OAR."""       
        logger.debug("SLABDRIVER \tDeleteJobs jobid  %s username %s " %(job_id, username))
        if not job_id or job_id is -1:
            return

        reqdict = {}
        reqdict['method'] = "delete"
        reqdict['strval'] = str(job_id)
       

        answer = self.oar.POSTRequestToOARRestAPI('DELETE_jobs_id', \
                                                    reqdict,username)
        logger.debug("SLABDRIVER \tDeleteJobs jobid  %s \r\n answer %s \
                                username %s" %(job_id, answer, username))
        return answer

            
        
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

        #logger.debug("SLABDRIVER \t GetJobsId  %s " %(job_info))
        #try:
            #if job_info['state'] == 'Terminated':
                #logger.debug("SLABDRIVER \t GetJobsId job %s TERMINATED"\
                                                            #%(job_id))
                #return None
            #if job_info['state'] == 'Error':
                #logger.debug("SLABDRIVER \t GetJobsId ERROR message %s "\
                                                            #%(job_info))
                #return None
                                                            
        #except KeyError:
            #logger.error("SLABDRIVER \tGetJobsId KeyError")
            #return None 
        
        #parsed_job_info  = self.get_info_on_reserved_nodes(job_info, \
                                                            #node_list_k)
        ##Replaces the previous entry 
        ##"assigned_network_address" / "reserved_resources"
        ##with "node_ids"
        #job_info.update({'node_ids':parsed_job_info[node_list_k]})
        #del job_info[node_list_k]
        #logger.debug(" \r\nSLABDRIVER \t GetJobsId job_info %s " %(job_info))
        #return job_info

        
    def GetJobsResources(self, job_id, username = None):
        """ Gets the list of nodes associated with the job_id. 
        Transforms the senslab hostnames to the corresponding
        SFA nodes hrns.
        Rertuns dict key :'node_ids' , value : hostnames list """

        req = "GET_jobs_id_resources"
       
               
        #Get job resources list from OAR    
        node_id_list = self.oar.parser.SendRequest(req, job_id, username)
        logger.debug("SLABDRIVER \t GetJobsResources  %s " %(node_id_list))
        
        hostname_list = \
            self.__get_hostnames_from_oar_node_ids(node_id_list)
        

        #Replaces the previous entry "assigned_network_address" / 
        #"reserved_resources" with "node_ids"
        job_info = {'node_ids': hostname_list}

        return job_info

            
    def get_info_on_reserved_nodes(self, job_info, node_list_name):
        #Get the list of the testbed nodes records and make a 
        #dictionnary keyed on the hostname out of it
        node_list_dict = self.GetNodes() 
        #node_hostname_list = []
        node_hostname_list = [node['hostname'] for node in node_list_dict] 
        #for node in node_list_dict:
            #node_hostname_list.append(node['hostname'])
        node_dict = dict(zip(node_hostname_list, node_list_dict))
        try :
            reserved_node_hostname_list = []
            for index in range(len(job_info[node_list_name])):
               #job_info[node_list_name][k] = 
                reserved_node_hostname_list[index] = \
                        node_dict[job_info[node_list_name][index]]['hostname']
                            
            logger.debug("SLABDRIVER \t get_info_on_reserved_nodes \
                        reserved_node_hostname_list %s" \
                        %(reserved_node_hostname_list))
        except KeyError:
            logger.error("SLABDRIVER \t get_info_on_reserved_nodes KEYERROR " )
            
        return reserved_node_hostname_list  
            
    def GetNodesCurrentlyInUse(self):
        """Returns a list of all the nodes already involved in an oar job"""
        return self.oar.parser.SendRequest("GET_running_jobs") 
    
    def __get_hostnames_from_oar_node_ids(self, resource_id_list ):
        full_nodes_dict_list = self.GetNodes()
        #Put the full node list into a dictionary keyed by oar node id
        oar_id_node_dict = {}
        for node in full_nodes_dict_list:
            oar_id_node_dict[node['oar_id']] = node
            
        #logger.debug("SLABDRIVER \t  __get_hostnames_from_oar_node_ids\
                        #oar_id_node_dict %s" %(oar_id_node_dict))

        hostname_dict_list = [] 
        for resource_id in resource_id_list:
            #Because jobs requested "asap" do not have defined resources
            if resource_id is not "Undefined":
                hostname_dict_list.append(\
                        oar_id_node_dict[resource_id]['hostname'])
                
            #hostname_list.append(oar_id_node_dict[resource_id]['hostname'])
        return hostname_dict_list 
        
    def GetReservedNodes(self, username = None):
        #Get the nodes in use and the reserved nodes
        reservation_dict_list = \
                        self.oar.parser.SendRequest("GET_reserved_nodes", \
                        username = username)
        
        
        for resa in reservation_dict_list:
            logger.debug ("GetReservedNodes resa %s"%(resa))
            #dict list of hostnames and their site
            resa['reserved_nodes'] = \
                self.__get_hostnames_from_oar_node_ids(resa['resource_ids'])
                
        #del resa['resource_ids']
        return reservation_dict_list
     
    def GetNodes(self, node_filter_dict = None, return_fields_list = None):
        """
        node_filter_dict : dictionnary of lists
        
        """
        node_dict_by_id = self.oar.parser.SendRequest("GET_resources_full")
        node_dict_list = node_dict_by_id.values()
        logger.debug (" SLABDRIVER GetNodes  node_filter_dict %s \
            return_fields_list %s "%(node_filter_dict, return_fields_list))
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
                                if return_fields_list :
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
                                    
                                    
                                    
    @staticmethod
    def AddSlice(slice_record, user_record):
        """Add slice to the sfa tables. Called by verify_slice
        during lease/sliver creation.
        """
 
        sfa_record = RegSlice(hrn=slice_record['hrn'], 
                                gid=slice_record['gid'], 
                                pointer=slice_record['slice_id'],
                                authority=slice_record['authority'])
                                
        logger.debug("SLABDRIVER.PY AddSlice  sfa_record %s user_record %s" \
                                                    %(sfa_record, user_record))
        sfa_record.just_created()
        dbsession.add(sfa_record)
        dbsession.commit() 
        #Update the reg-researcher dependance table
        sfa_record.reg_researchers =  [user_record]
        dbsession.commit()       
     
        #Update the senslab table with the new slice                     
        #slab_slice = SenslabXP( slice_hrn = slice_record['slice_hrn'], \
                        #record_id_slice = sfa_record.record_id , \
                        #record_id_user = slice_record['record_id_user'], \
                        #peer_authority = slice_record['peer_authority'])
                        
        #logger.debug("SLABDRIVER.PY \tAddSlice slice_record %s \
                                    #slab_slice %s sfa_record %s" \
                                    #%(slice_record,slab_slice, sfa_record))
        #slab_dbsession.add(slab_slice)
        #slab_dbsession.commit()
        return
        
    def GetSites(self, site_filter_name_list = None, return_fields_list = None):
        site_dict = self.oar.parser.SendRequest("GET_sites")
        #site_dict : dict where the key is the sit ename
        return_site_list = []
        if not ( site_filter_name_list or return_fields_list):
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
                            logger.error("GetSites KeyError %s "%(field))
                            return None
                    return_site_list.append(tmp)
                else:
                    return_site_list.append( site_dict[site_filter_name])
            

        return return_site_list


   
    
        
    #TODO : Check rights to delete person 
    def DeletePerson(self, person_record):
        """ Disable an existing account in senslab LDAP.
        Users and techs can only delete themselves. PIs can only 
        delete themselves and other non-PIs at their sites. 
        ins can delete anyone.
        Returns 1 if successful, faults otherwise.
        FROM PLC API DOC
        
        """
        #Disable user account in senslab LDAP
        ret = self.ldap.LdapMarkUserAsDeleted(person_record)
        logger.warning("SLABDRIVER DeletePerson %s " %(person_record))
        return ret
    
    #TODO Check DeleteSlice, check rights 05/07/2012 SA
    def DeleteSlice(self, slice_record):
        """ Deletes the specified slice.
         Senslab : Kill the job associated with the slice if there is one
         using DeleteSliceFromNodes.
         Updates the slice record in slab db to remove the slice nodes.
         
         Users may only delete slices of which they are members. PIs may 
         delete any of the slices at their sites, or any slices of which 
         they are members. Admins may delete any slice.
         Returns 1 if successful, faults otherwise.
         FROM PLC API DOC
        
        """
        self.DeleteSliceFromNodes(slice_record)
        logger.warning("SLABDRIVER DeleteSlice %s "%(slice_record))
        return
    
    @staticmethod
    def __add_person_to_db(user_dict):

        check_if_exists = dbsession.query(RegUser).filter_by(email = user_dict['email']).first()
        #user doesn't exists
        if not check_if_exists:
            logger.debug("__add_person_to_db \t Adding %s \r\n \r\n \
            _________________________________________________________________________\
            " %(user_dict)) 
            hrn = user_dict['hrn'] 
            person_urn = hrn_to_urn(hrn, 'user')
            pubkey = user_dict['pkey']
            try:
                pkey = convert_public_key(pubkey)
            except TypeError:
                #key not good. create another pkey
                logger.warn('__add_person_to_db: unable to convert public \
                                    key for %s' %(hrn ))
                pkey = Keypair(create=True)
           
           
            if pubkey is not None and pkey is not None :
                hierarchy = Hierarchy()
                person_gid = hierarchy.create_gid(person_urn, create_uuid(), pkey)
                if user_dict['email']:
                    logger.debug("__add_person_to_db \r\n \r\n SLAB IMPORTER PERSON EMAIL OK email %s " %(user_dict['email']))
                    person_gid.set_email(user_dict['email'])
                    
            user_record = RegUser(hrn=hrn , pointer= '-1', authority=get_authority(hrn), \
                                                    email=user_dict['email'], gid = person_gid)
            user_record.reg_keys = [RegKey(user_dict['pkey'])]
            user_record.just_created()
            dbsession.add (user_record)
            dbsession.commit()
        return 
        
    #TODO AddPerson 04/07/2012 SA
    #def AddPerson(self, auth,  person_fields=None): 
    def AddPerson(self, record):#TODO fixing 28/08//2012 SA
        """Adds a new account. Any fields specified in records are used, 
        otherwise defaults are used.
        Accounts are disabled by default. To enable an account, 
        use UpdatePerson().
        Returns the new person_id (> 0) if successful, faults otherwise. 
        FROM PLC API DOC
        
        """
        ret = self.ldap.LdapAddUser(record)
        
        record['hrn'] = self.root_auth + '.' + ret['uid']
        logger.debug("SLABDRIVER AddPerson return code %s record %s \r\n "\
                                                            %(ret, record))
        self.__add_person_to_db(record)
        return ret['uid']
    
    #TODO AddPersonToSite 04/07/2012 SA
    def AddPersonToSite (self, auth, person_id_or_email, \
                                                site_id_or_login_base=None):
        """  Adds the specified person to the specified site. If the person is 
        already a member of the site, no errors are returned. Does not change 
        the person's primary site.
        Returns 1 if successful, faults otherwise.
        FROM PLC API DOC
        
        """
        logger.warning("SLABDRIVER AddPersonToSite EMPTY - DO NOTHING \r\n ")
        return
    
    #TODO AddRoleToPerson : Not sure if needed in senslab 04/07/2012 SA
    def AddRoleToPerson(self, auth, role_id_or_name, person_id_or_email):
        """Grants the specified role to the person.
        PIs can only grant the tech and user roles to users and techs at their 
        sites. Admins can grant any role to any user.
        Returns 1 if successful, faults otherwise.
        FROM PLC API DOC
        
        """
        logger.warning("SLABDRIVER AddRoleToPerson EMPTY - DO NOTHING \r\n ")
        return
    
    #TODO AddPersonKey 04/07/2012 SA
    def AddPersonKey(self, auth, person_id_or_email, key_fields=None):
        """Adds a new key to the specified account.
        Non-admins can only modify their own keys.
        Returns the new key_id (> 0) if successful, faults otherwise.
        FROM PLC API DOC
        
        """
        logger.warning("SLABDRIVER AddPersonKey EMPTY - DO NOTHING \r\n ")
        return
    
    def DeleteLeases(self, leases_id_list, slice_hrn ):        
        logger.debug("SLABDRIVER DeleteLeases leases_id_list %s slice_hrn %s \
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
                    SlabTestbedAPI._process_walltime(int(lease_dict['lease_duration'])*lease_dict['grain'])


        reqdict['resource'] += ",walltime=" + str(walltime[0]) + \
                            ":" + str(walltime[1]) + ":" + str(walltime[2])
        reqdict['script_path'] = "/bin/sleep " + str(sleep_walltime)

        #In case of a scheduled experiment (not immediate)
        #To run an XP immediately, don't specify date and time in RSpec 
        #They will be set to None.
        if lease_dict['lease_start_time'] is not '0':
            #Readable time accepted by OAR
            start_time = datetime.fromtimestamp(int(lease_dict['lease_start_time'])).\
                                                    strftime(lease_dict['time_format'])
            reqdict['reservation'] = start_time
        #If there is not start time, Immediate XP. No need to add special 
        # OAR parameters


        reqdict['type'] = "deploy" 
        reqdict['directory'] = ""
        reqdict['name'] = "SFA_" + lease_dict['slice_user']

        return reqdict
    
                  
    def LaunchExperimentOnOAR(self, added_nodes, slice_name, \
                        lease_start_time, lease_duration, slice_user=None):
        lease_dict = {}
        lease_dict['lease_start_time'] = lease_start_time
        lease_dict['lease_duration'] = lease_duration
        lease_dict['added_nodes'] = added_nodes
        lease_dict['slice_name'] = slice_name
        lease_dict['slice_user'] = slice_user
        lease_dict['grain'] = self.GetLeaseGranularity()
        lease_dict['time_format'] = self.time_format

        
        logger.debug("SLABDRIVER.PY \tLaunchExperimentOnOAR slice_user %s\
                             \r\n "  %(slice_user))                             
        #Create the request for OAR
        reqdict = self._create_job_structure_request_for_OAR(lease_dict)
         # first step : start the OAR job and update the job 
        logger.debug("SLABDRIVER.PY \tLaunchExperimentOnOAR reqdict %s\
                             \r\n "  %(reqdict))  
       
        answer = self.oar.POSTRequestToOARRestAPI('POST_job', \
                                                            reqdict, slice_user)
        logger.debug("SLABDRIVER \tLaunchExperimentOnOAR jobid   %s " %(answer))
        try:       
            jobid = answer['id']
        except KeyError:
            logger.log_exc("SLABDRIVER \tLaunchExperimentOnOAR \
                                Impossible to create job  %s "  %(answer))
            return None
        
        

        
        if jobid :
            logger.debug("SLABDRIVER \tLaunchExperimentOnOAR jobid %s \
                    added_nodes %s slice_user %s" %(jobid, added_nodes, slice_user))
            
            
        return jobid
        
        
    def AddLeases(self, hostname_list, slice_record, \
                                        lease_start_time, lease_duration):
        logger.debug("SLABDRIVER \r\n \r\n \t AddLeases hostname_list %s  \
                slice_record %s lease_start_time %s lease_duration %s  "\
                 %( hostname_list, slice_record , lease_start_time, \
                 lease_duration))

        #tmp = slice_record['reg-researchers'][0].split(".")
        username = slice_record['login']
        #username = tmp[(len(tmp)-1)]
        job_id = self.LaunchExperimentOnOAR(hostname_list, slice_record['hrn'], \
                                    lease_start_time, lease_duration, username)
        start_time = datetime.fromtimestamp(int(lease_start_time)).strftime(self.time_format)
        end_time = lease_start_time + lease_duration

        import logging, logging.handlers
        from sfa.util.sfalogging import _SfaLogger
        logger.debug("SLABDRIVER \r\n \r\n \t AddLeases TURN ON LOGGING SQL %s %s %s "%(slice_record['hrn'], job_id, end_time))
        sql_logger = _SfaLogger(loggername = 'sqlalchemy.engine', level=logging.DEBUG)
        logger.debug("SLABDRIVER \r\n \r\n \t AddLeases %s %s %s " %(type(slice_record['hrn']), type(job_id), type(end_time)))
        
        slab_ex_row = SenslabXP(slice_hrn = slice_record['hrn'], \
                job_id = job_id, end_time= end_time)
                
        logger.debug("SLABDRIVER \r\n \r\n \t AddLeases slab_ex_row %s" \
                %(slab_ex_row))
        slab_dbsession.add(slab_ex_row)
        slab_dbsession.commit()
        
        logger.debug("SLABDRIVER \t AddLeases hostname_list start_time %s " %(start_time))
        
        return
    
    
    #Delete the jobs from job_senslab table
    def DeleteSliceFromNodes(self, slice_record):
        logger.debug("SLABDRIVER \t  DeleteSliceFromNodese %s " %(slice_record))
        if isinstance(slice_record['oar_job_id'], list):
            for job_id in slice_record['oar_job_id']:
                self.DeleteJobs(job_id, slice_record['user'])
        else:
            self.DeleteJobs(slice_record['oar_job_id'], slice_record['user'])
        return   
    
 
    def GetLeaseGranularity(self):
        """ Returns the granularity of Senslab testbed.
        OAR returns seconds for experiments duration.
        Defined in seconds. 
        Experiments which last less than 10 min are invalid"""
        
        
        return self.grain
    
    
    @staticmethod
    def update_jobs_in_slabdb( job_oar_list, jobs_psql):
        #Get all the entries in slab_xp table
        
        set_jobs_psql = set(jobs_psql)

        kept_jobs = set(job_oar_list).intersection(set_jobs_psql)
        logger.debug ( "\r\n \t\ update_jobs_in_slabdb jobs_psql %s \r\n \t \
            job_oar_list %s kept_jobs %s "%(set_jobs_psql, job_oar_list, kept_jobs))
        deleted_jobs = set_jobs_psql.difference(kept_jobs)
        deleted_jobs = list(deleted_jobs)
        if len(deleted_jobs) > 0:
            slab_dbsession.query(SenslabXP).filter(SenslabXP.job_id.in_(deleted_jobs)).delete(synchronize_session='fetch')
            slab_dbsession.commit()
        
        return

        
    
    def GetLeases(self, lease_filter_dict=None, login=None):
        """ 
        Two purposes:
        -Fetch all the jobs from OAR (running, waiting..)
        complete the reservation information with slice hrn
        found in slabxp table. If not available in the table,
        assume it is a senslab slice.
       - Updates the slab table, deleting jobs when necessary.
        :returns reservation_list, list of dictionaries. """
        
        unfiltered_reservation_list = self.GetReservedNodes(login)

        reservation_list = []
        #Find the slice associated with this user senslab ldap uid
        logger.debug(" SLABDRIVER.PY \tGetLeases login %s\
         unfiltered_reservation_list %s " %(login, unfiltered_reservation_list))
        #Create user dict first to avoid looking several times for
        #the same user in LDAP SA 27/07/12
        resa_user_dict = {}
        job_oar_list = []
        
        jobs_psql_query = slab_dbsession.query(SenslabXP).all()
        jobs_psql_dict = dict( [ (row.job_id, row.__dict__ )for row in jobs_psql_query ])
        #jobs_psql_dict = jobs_psql_dict)
        logger.debug("SLABDRIVER \tGetLeases jobs_psql_dict %s"\
                                            %(jobs_psql_dict))
        jobs_psql_id_list =  [ row.job_id for row in jobs_psql_query ]
        
        
        
        for resa in unfiltered_reservation_list:
            logger.debug("SLABDRIVER \tGetLeases USER %s"\
                                            %(resa['user']))   
            #Construct list of jobs (runing, waiting..) in oar 
            job_oar_list.append(resa['lease_id'])  
            #If there is information on the job in SLAB DB ]
            #(slice used and job id) 
            if resa['lease_id'] in jobs_psql_dict:
                job_info = jobs_psql_dict[resa['lease_id']]
                logger.debug("SLABDRIVER \tGetLeases job_info %s"\
                                            %(job_info))        
                resa['slice_hrn'] = job_info['slice_hrn']
                resa['slice_id'] = hrn_to_urn(resa['slice_hrn'], 'slice')
                
            #otherwise, assume it is a senslab slice:   
            else:
                resa['slice_id'] =  hrn_to_urn(self.root_auth+'.'+ \
                                         resa['user'] +"_slice"  , 'slice')              
                resa['slice_hrn'] = Xrn(resa['slice_id']).get_hrn()

            resa['component_id_list'] = []    
            #Transform the hostnames into urns (component ids)
            for node in resa['reserved_nodes']:
                
                slab_xrn = slab_xrn_object(self.root_auth, node)
                resa['component_id_list'].append(slab_xrn.urn)
                    
            if lease_filter_dict:
                logger.debug("SLABDRIVER \tGetLeases resa_ %s \
                        \r\n leasefilter %s" %(resa, lease_filter_dict)) 
                        
                if lease_filter_dict['name'] == resa['slice_hrn']:
                    reservation_list.append(resa)
                        
        if lease_filter_dict is None:
            reservation_list = unfiltered_reservation_list
               
                    
        self.update_jobs_in_slabdb(job_oar_list, jobs_psql_id_list)
                
        logger.debug(" SLABDRIVER.PY \tGetLeases reservation_list %s"\
                                                    %(reservation_list))
        return reservation_list
           
    
  

#TODO FUNCTIONS SECTION 04/07/2012 SA

    #TODO : Is UnBindObjectFromPeer still necessary ? Currently does nothing
    #04/07/2012 SA
    @staticmethod
    def UnBindObjectFromPeer( auth, object_type, object_id, shortname):
        """ This method is a hopefully temporary hack to let the sfa correctly
        detach the objects it creates from a remote peer object. This is 
        needed so that the sfa federation link can work in parallel with 
        RefreshPeer, as RefreshPeer depends on remote objects being correctly 
        marked.
        Parameters:
        auth : struct, API authentication structure
            AuthMethod : string, Authentication method to use 
        object_type : string, Object type, among 'site','person','slice',
        'node','key'
        object_id : int, object_id
        shortname : string, peer shortname 
        FROM PLC DOC
        
        """
        logger.warning("SLABDRIVER \tUnBindObjectFromPeer EMPTY-\
                        DO NOTHING \r\n ")
        return 
    
    #TODO Is BindObjectToPeer still necessary ? Currently does nothing 
    #04/07/2012 SA
    def BindObjectToPeer(self, auth, object_type, object_id, shortname=None, \
                                                    remote_object_id=None):
        """This method is a hopefully temporary hack to let the sfa correctly 
        attach the objects it creates to a remote peer object. This is needed 
        so that the sfa federation link can work in parallel with RefreshPeer, 
        as RefreshPeer depends on remote objects being correctly marked.
        Parameters:
        shortname : string, peer shortname 
        remote_object_id : int, remote object_id, set to 0 if unknown 
        FROM PLC API DOC
        
        """
        logger.warning("SLABDRIVER \tBindObjectToPeer EMPTY - DO NOTHING \r\n ")
        return
    
    #TODO UpdateSlice 04/07/2012 SA
    #Funciton should delete and create another job since oin senslab slice=job
    def UpdateSlice(self, auth, slice_id_or_name, slice_fields=None):    
        """Updates the parameters of an existing slice with the values in 
        slice_fields.
        Users may only update slices of which they are members. 
        PIs may update any of the slices at their sites, or any slices of 
        which they are members. Admins may update any slice.
        Only PIs and admins may update max_nodes. Slices cannot be renewed
        (by updating the expires parameter) more than 8 weeks into the future.
         Returns 1 if successful, faults otherwise.
        FROM PLC API DOC
        
        """  
        logger.warning("SLABDRIVER UpdateSlice EMPTY - DO NOTHING \r\n ")
        return
    
    #TODO UpdatePerson 04/07/2012 SA
    def UpdatePerson(self, slab_hrn, federated_hrn, person_fields=None):
        """Updates a person. Only the fields specified in person_fields 
        are updated, all other fields are left untouched.
        Users and techs can only update themselves. PIs can only update
        themselves and other non-PIs at their sites.
        Returns 1 if successful, faults otherwise.
        FROM PLC API DOC
         
        """
        #new_row = FederatedToSenslab(slab_hrn, federated_hrn)
        #slab_dbsession.add(new_row)
        #slab_dbsession.commit()
        
        logger.debug("SLABDRIVER UpdatePerson EMPTY - DO NOTHING \r\n ")
        return
    
    #TODO GetKeys 04/07/2012 SA
    def GetKeys(self, auth, key_filter=None, return_fields=None):
        """Returns an array of structs containing details about keys. 
        If key_filter is specified and is an array of key identifiers, 
        or a struct of key attributes, only keys matching the filter 
        will be returned. If return_fields is specified, only the 
        specified details will be returned.

        Admin may query all keys. Non-admins may only query their own keys.
        FROM PLC API DOC
        
        """
        logger.warning("SLABDRIVER  GetKeys EMPTY - DO NOTHING \r\n ")
        return
    
    #TODO DeleteKey 04/07/2012 SA
    def DeleteKey(self, key_id):
        """  Deletes a key.
         Non-admins may only delete their own keys.
         Returns 1 if successful, faults otherwise.
         FROM PLC API DOC
         
        """
        logger.warning("SLABDRIVER  DeleteKey EMPTY - DO NOTHING \r\n ")
        return

     
     
                    
    @staticmethod           
    def _sql_get_slice_info( slice_filter ):
        #DO NOT USE RegSlice - reg_researchers to get the hrn 
        #of the user otherwise will mess up the RegRecord in 
        #Resolve, don't know why - SA 08/08/2012
        
        #Only one entry for one user  = one slice in slab_xp table
        #slicerec = dbsession.query(RegRecord).filter_by(hrn = slice_filter).first()
        raw_slicerec = dbsession.query(RegSlice).options(joinedload('reg_researchers')).filter_by(hrn = slice_filter).first()
        #raw_slicerec = dbsession.query(RegRecord).filter_by(hrn = slice_filter).first()
        if raw_slicerec: 
            #load_reg_researcher
            #raw_slicerec.reg_researchers
            raw_slicerec = raw_slicerec.__dict__
            logger.debug(" SLABDRIVER \t  get_slice_info slice_filter %s  \
                            raw_slicerec %s"%(slice_filter, raw_slicerec))
            slicerec = raw_slicerec
            #only one researcher per slice so take the first one
            #slicerec['reg_researchers'] = raw_slicerec['reg_researchers']
            #del slicerec['reg_researchers']['_sa_instance_state']
            return slicerec
        
        else :
            return None
            
    @staticmethod       
    def _sql_get_slice_info_from_user(slice_filter ): 
        #slicerec = dbsession.query(RegRecord).filter_by(record_id = slice_filter).first()
        raw_slicerec = dbsession.query(RegUser).options(joinedload('reg_slices_as_researcher')).filter_by(record_id = slice_filter).first()
        #raw_slicerec = dbsession.query(RegRecord).filter_by(record_id = slice_filter).first()
        #Put it in correct order 
        user_needed_fields = ['peer_authority', 'hrn', 'last_updated', 'classtype', 'authority', 'gid', 'record_id', 'date_created', 'type', 'email', 'pointer']
        slice_needed_fields = ['peer_authority', 'hrn', 'last_updated', 'classtype', 'authority', 'gid', 'record_id', 'date_created', 'type', 'pointer']
        if raw_slicerec:
            #raw_slicerec.reg_slices_as_researcher
            raw_slicerec = raw_slicerec.__dict__
            slicerec = {}
            slicerec = \
            dict([(k, raw_slicerec['reg_slices_as_researcher'][0].__dict__[k]) \
                        for k in slice_needed_fields])
            slicerec['reg_researchers'] = dict([(k, raw_slicerec[k]) \
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
            
    def _get_slice_records(self, slice_filter = None, \
                    slice_filter_type = None):
      
       
        
        #Get list of slices based on the slice hrn
        if slice_filter_type == 'slice_hrn':
            
            #if get_authority(slice_filter) == self.root_auth:
                #login = slice_filter.split(".")[1].split("_")[0] 
            
            slicerec = self._sql_get_slice_info(slice_filter)
            
            if slicerec is None:
                return  None                
                #return login, None    
            
        #Get slice based on user id                             
        if slice_filter_type == 'record_id_user': 
            
            slicerec = self._sql_get_slice_info_from_user(slice_filter)
                
        if slicerec:
            fixed_slicerec_dict = slicerec
            #At this point if there is no login it means 
            #record_id_user filter has been used for filtering
            #if login is None :
                ##If theslice record is from senslab
                #if fixed_slicerec_dict['peer_authority'] is None:
                    #login = fixed_slicerec_dict['hrn'].split(".")[1].split("_")[0] 
            #return login, fixed_slicerec_dict
            return fixed_slicerec_dict                  
                  
                  
                  
    def GetSlices(self, slice_filter = None, slice_filter_type = None, \
                                                                    login=None):
        """ Get the slice records from the slab db. 
        Returns a slice ditc if slice_filter  and slice_filter_type 
        are specified.
        Returns a list of slice dictionnaries if there are no filters
        specified. 
       
        """
        #login = None
        authorized_filter_types_list = ['slice_hrn', 'record_id_user']
        return_slicerec_dictlist = []
        
        #First try to get information on the slice based on the filter provided     
        if slice_filter_type in authorized_filter_types_list:
            fixed_slicerec_dict = \
                            self._get_slice_records(slice_filter, slice_filter_type)
            slice_hrn = fixed_slicerec_dict['hrn']
   
            logger.debug(" SLABDRIVER \tGetSlices login %s \
                            slice record %s slice_filter %s \
                            slice_filter_type %s " %(login, \
                            fixed_slicerec_dict, slice_filter, \
                            slice_filter_type))
    
            
            #Now we have the slice record fixed_slicerec_dict, get the 
            #jobs associated to this slice
            leases_list = self.GetLeases(login = login)
            #If no job is running or no job scheduled 
            #return only the slice record           
            if leases_list == [] and fixed_slicerec_dict:
                return_slicerec_dictlist.append(fixed_slicerec_dict)
                
            #If several jobs for one slice , put the slice record into 
            # each lease information dict
           
           
            for lease in leases_list : 
                slicerec_dict = {} 
                logger.debug("SLABDRIVER.PY  \tGetSlices slice_filter %s   \
                        \ lease['slice_hrn'] %s" \
                        %(slice_filter, lease['slice_hrn']))
                if  lease['slice_hrn'] == slice_hrn:
                    slicerec_dict['slice_hrn'] = lease['slice_hrn']
                    slicerec_dict['hrn'] = lease['slice_hrn']
                    slicerec_dict['user'] = lease['user']
                    slicerec_dict['oar_job_id'] = lease['lease_id']
                    slicerec_dict.update({'list_node_ids':{'hostname':lease['reserved_nodes']}})   
                    slicerec_dict.update({'node_ids':lease['reserved_nodes']})
                    
                    #Update lease dict with the slice record
                    if fixed_slicerec_dict:
                        fixed_slicerec_dict['oar_job_id'] = []
                        fixed_slicerec_dict['oar_job_id'].append(slicerec_dict['oar_job_id'])
                        slicerec_dict.update(fixed_slicerec_dict)
                        #slicerec_dict.update({'hrn':\
                                        #str(fixed_slicerec_dict['slice_hrn'])})
                                        
                    return_slicerec_dictlist.append(slicerec_dict)    
                    logger.debug("SLABDRIVER.PY  \tGetSlices  \
                        OHOHOHOH %s" %(return_slicerec_dictlist ))
                    
                logger.debug("SLABDRIVER.PY  \tGetSlices  \
                        slicerec_dict %s return_slicerec_dictlist %s \
                        lease['reserved_nodes'] \
                        %s" %(slicerec_dict, return_slicerec_dictlist, \
                        lease['reserved_nodes'] ))
                
            logger.debug("SLABDRIVER.PY  \tGetSlices  RETURN \
                        return_slicerec_dictlist  %s" \
                        %(return_slicerec_dictlist))
                            
            return return_slicerec_dictlist
                
                
        else:
            #Get all slices from the senslab sfa database ,
            #put them in dict format 
            #query_slice_list = dbsession.query(RegRecord).all()           
            query_slice_list = dbsession.query(RegSlice).options(joinedload('reg_researchers')).all()          

            return_slicerec_dictlist = []
            for record in query_slice_list: 
                tmp = record.__dict__
                tmp['reg_researchers'] = tmp['reg_researchers'][0].__dict__
                #del tmp['reg_researchers']['_sa_instance_state']
                return_slicerec_dictlist.append(tmp)
                #return_slicerec_dictlist.append(record.__dict__)
                
            #Get all the jobs reserved nodes
            leases_list = self.GetReservedNodes()
            
               
            for fixed_slicerec_dict in return_slicerec_dictlist:
                slicerec_dict = {} 
                #Check if the slice belongs to a senslab user
                if fixed_slicerec_dict['peer_authority'] is None:
                    owner = fixed_slicerec_dict['hrn'].split(".")[1].split("_")[0] 
                else:
                    owner = None
                for lease in leases_list:   
                    if owner == lease['user']:
                        slicerec_dict['oar_job_id'] = lease['lease_id']

                        #for reserved_node in lease['reserved_nodes']:
                        logger.debug("SLABDRIVER.PY  \tGetSlices lease %s "\
                                                                 %(lease ))

                        slicerec_dict.update({'node_ids':lease['reserved_nodes']})
                        slicerec_dict.update({'list_node_ids':{'hostname':lease['reserved_nodes']}}) 
                        slicerec_dict.update(fixed_slicerec_dict)
                        #slicerec_dict.update({'hrn':\
                                    #str(fixed_slicerec_dict['slice_hrn'])})
                        #return_slicerec_dictlist.append(slicerec_dict)
                        fixed_slicerec_dict.update(slicerec_dict)
                        
            logger.debug("SLABDRIVER.PY  \tGetSlices RETURN \
                        return_slicerec_dictlist %s \slice_filter %s " \
                        %(return_slicerec_dictlist, slice_filter))

        return return_slicerec_dictlist
        


          
    ##
    # Convert SFA fields to PLC fields for use when registering up updating
    # registry record in the PLC database
    #
    # @param type type of record (user, slice, ...)
    # @param hrn human readable name
    # @param sfa_fields dictionary of SFA fields
    # @param slab_fields dictionary of PLC fields (output)
    @staticmethod
    def sfa_fields_to_slab_fields(sfa_type, hrn, record):


        slab_record = {}
        #for field in record:
        #    slab_record[field] = record[field]
 
        if sfa_type == "slice":
            #instantion used in get_slivers ? 
            if not "instantiation" in slab_record:
                slab_record["instantiation"] = "senslab-instantiated"
            #slab_record["hrn"] = hrn_to_pl_slicename(hrn)     
            #Unused hrn_to_pl_slicename because Slab's hrn already 
            #in the appropriate form SA 23/07/12
            slab_record["hrn"] = hrn 
            logger.debug("SLABDRIVER.PY sfa_fields_to_slab_fields \
                        slab_record %s  " %(slab_record['hrn']))
            if "url" in record:
                slab_record["url"] = record["url"]
            if "description" in record:
                slab_record["description"] = record["description"]
            if "expires" in record:
                slab_record["expires"] = int(record["expires"])
                
        #nodes added by OAR only and then imported to SFA
        #elif type == "node":
            #if not "hostname" in slab_record:
                #if not "hostname" in record:
                    #raise MissingSfaInfo("hostname")
                #slab_record["hostname"] = record["hostname"]
            #if not "model" in slab_record:
                #slab_record["model"] = "geni"
                
        #One authority only 
        #elif type == "authority":
            #slab_record["login_base"] = hrn_to_slab_login_base(hrn)

            #if not "name" in slab_record:
                #slab_record["name"] = hrn

            #if not "abbreviated_name" in slab_record:
                #slab_record["abbreviated_name"] = hrn

            #if not "enabled" in slab_record:
                #slab_record["enabled"] = True

            #if not "is_public" in slab_record:
                #slab_record["is_public"] = True

        return slab_record


   

     
        
     
     
     
     
     