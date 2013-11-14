"""
File used to handle issuing request to OAR and parse OAR's JSON responses.
Contains the following classes:
- JsonPage : handles multiple pages OAR answers.
- OARRestapi : handles issuing POST or GET requests to OAR.
- ParsingResourcesFull : dedicated to parsing OAR's answer to a get resources
full request.
- OARGETParser : handles parsing the Json answers to different GET requests.

"""
from httplib import HTTPConnection, HTTPException, NotConnected
import json
from sfa.util.config import Config
from sfa.util.sfalogging import logger
import os.path


class JsonPage:

    """Class used to manipulate json pages given by OAR.

    In case the json answer from a GET request is too big to fit in one json
    page, this class provides helper methods to retrieve all the pages and
    store them in a list before putting them into one single json dictionary,
    facilitating the parsing.

    """

    def __init__(self):
        """Defines attributes to manipulate and parse the json pages.

        """
        #All are boolean variables
        self.concatenate = False
        #Indicates end of data, no more pages to be loaded.
        self.end = False
        self.next_page = False
        #Next query address
        self.next_offset = None
        #Json page
        self.raw_json = None

    def FindNextPage(self):
        """
        Gets next data page from OAR when the query's results are too big to
        be transmitted in a single page. Uses the "links' item in the json
        returned to check if an additionnal page has to be loaded. Updates
        object attributes next_page, next_offset, and end.

        """
        if "links" in self.raw_json:
            for page in self.raw_json['links']:
                if page['rel'] == 'next':
                    self.concatenate = True
                    self.next_page = True
                    self.next_offset = "?" + page['href'].split("?")[1]
                    return

        if self.concatenate:
            self.end = True
            self.next_page = False
            self.next_offset = None

            return

        #Otherwise, no next page and no concatenate, must be a single page
        #Concatenate the single page and get out of here.
        else:
            self.next_page = False
            self.concatenate = True
            self.next_offset = None
            return

    @staticmethod
    def ConcatenateJsonPages(saved_json_list):
        """
        If the json answer is too big to be contained in a single page,
        all the pages have to be loaded and saved before being appended to the
        first page.

        :param saved_json_list: list of all the stored pages, including the
            first page.
        :type saved_json_list: list
        :returns: Returns a dictionary with all the pages saved in the
            saved_json_list. The key of the dictionary is 'items'.
        :rtype: dict


        .. seealso:: SendRequest
        .. warning:: Assumes the apilib is 0.2.10 (with the 'items' key in the
            raw json dictionary)

        """
        #reset items list

        tmp = {}
        tmp['items'] = []

        for page in saved_json_list:
            tmp['items'].extend(page['items'])
        return tmp

    def ResetNextPage(self):
        """
        Resets all the Json page attributes (next_page, next_offset,
        concatenate, end). Has to be done before getting another json answer
        so that the previous page status does not affect the new json load.

        """
        self.next_page = True
        self.next_offset = None
        self.concatenate = False
        self.end = False


class OARrestapi:
    """Class used to connect to the OAR server and to send GET and POST
    requests.

    """

    # classes attributes

    OAR_REQUEST_POST_URI_DICT = {'POST_job': {'uri': '/oarapi/jobs.json'},
                                 'DELETE_jobs_id':
                                 {'uri': '/oarapi/jobs/id.json'},
                                 }

    POST_FORMAT = {'json': {'content': "application/json", 'object': json}}

    #OARpostdatareqfields = {'resource' :"/nodes=", 'command':"sleep", \
                            #'workdir':"/home/", 'walltime':""}

    def __init__(self, config_file='/etc/sfa/oar_config.py'):
        self.oarserver = {}
        self.oarserver['uri'] = None
        self.oarserver['postformat'] = 'json'

        try:
            execfile(config_file, self.__dict__)

            self.config_file = config_file
            # path to configuration data
            self.config_path = os.path.dirname(config_file)

        except IOError:
            raise IOError, "Could not find or load the configuration file: %s" \
                % config_file
        #logger.setLevelDebug()
        self.oarserver['ip'] = self.OAR_IP
        self.oarserver['port'] = self.OAR_PORT
        self.jobstates = ['Terminated', 'Hold', 'Waiting', 'toLaunch',
                          'toError', 'toAckReservation', 'Launching',
                          'Finishing', 'Running', 'Suspended', 'Resuming',
                          'Error']

        self.parser = OARGETParser(self)


    def GETRequestToOARRestAPI(self, request, strval=None,
                               next_page=None, username=None):

        """Makes a GET request to OAR.

        Fetch the uri associated with the resquest stored in
        OARrequests_uri_dict, adds the username if needed and if available, adds
        strval to the request uri if needed, connects to OAR and issues the GET
        request. Gets the json reply.

        :param request: One of the known get requests that are keys in the
            OARrequests_uri_dict.
        :param strval: used when a job id has to be specified.
        :param next_page: used to tell OAR to send the next page for this
            Get request. Is appended to the GET uri.
        :param username: used when a username has to be specified, when looking
            for jobs scheduled by a particular user  for instance.

        :type request: string
        :type strval: integer
        :type next_page: boolean
        :type username: string
        :returns: a json dictionary if OAR successfully processed the GET
            request.

        .. seealso:: OARrequests_uri_dict
        """
        self.oarserver['uri'] = \
            OARGETParser.OARrequests_uri_dict[request]['uri']
        #Get job details with username
        if 'owner' in OARGETParser.OARrequests_uri_dict[request] and username:
            self.oarserver['uri'] += \
                OARGETParser.OARrequests_uri_dict[request]['owner'] + username
        headers = {}
        data = json.dumps({})
        logger.debug("OARrestapi \tGETRequestToOARRestAPI %s" % (request))
        if strval:
            self.oarserver['uri'] = self.oarserver['uri'].\
                replace("id", str(strval))

        if next_page:
            self.oarserver['uri'] += next_page

        if username:
            headers['X-REMOTE_IDENT'] = username

        logger.debug("OARrestapi: \t  GETRequestToOARRestAPI  \
                        self.oarserver['uri'] %s strval %s"
                     % (self.oarserver['uri'], strval))
        try:
            #seems that it does not work if we don't add this
            headers['content-length'] = '0'

            conn = HTTPConnection(self.oarserver['ip'],
                                  self.oarserver['port'])
            conn.request("GET", self.oarserver['uri'], data, headers)
            resp = conn.getresponse()
            body = resp.read()
        except Exception as error:
            logger.log_exc("GET_OAR_SRVR : Connection error: %s "
                % (error))
            raise Exception ("GET_OAR_SRVR : Connection error %s " %(error))

        finally:
            conn.close()

        # except HTTPException, error:
        #     logger.log_exc("GET_OAR_SRVR : Problem with OAR server : %s "
        #                    % (error))
            #raise ServerError("GET_OAR_SRVR : Could not reach OARserver")
        if resp.status >= 400:
            raise ValueError ("Response Error %s, %s" %(resp.status,
                resp.reason))
        try:
            js_dict = json.loads(body)
            #print "\r\n \t\t\t js_dict keys" , js_dict.keys(), " \r\n", js_dict
            return js_dict

        except ValueError, error:
            logger.log_exc("Failed to parse Server Response: %s ERROR %s"
                           % (body, error))
            #raise ServerError("Failed to parse Server Response:" + js)


    def POSTRequestToOARRestAPI(self, request, datadict, username=None):
        """ Used to post a job on OAR , along with data associated
        with the job.

        """

        #first check that all params for are OK
        try:
            self.oarserver['uri'] = \
                self.OAR_REQUEST_POST_URI_DICT[request]['uri']

        except KeyError:
            logger.log_exc("OARrestapi \tPOSTRequestToOARRestAPI request not \
                             valid")
            return
        if datadict and 'strval' in datadict:
            self.oarserver['uri'] = self.oarserver['uri'].replace("id", \
                                                str(datadict['strval']))
            del datadict['strval']

        data = json.dumps(datadict)
        headers = {'X-REMOTE_IDENT':username, \
                'content-type': self.POST_FORMAT['json']['content'], \
                'content-length':str(len(data))}
        try :

            conn = HTTPConnection(self.oarserver['ip'], \
                                        self.oarserver['port'])
            conn.request("POST", self.oarserver['uri'], data, headers)
            resp = conn.getresponse()
            body = resp.read()

        except NotConnected:
            logger.log_exc("POSTRequestToOARRestAPI NotConnected ERROR: \
                            data %s \r\n \t\n \t\t headers %s uri %s" \
                            %(data,headers,self.oarserver['uri']))
        except Exception as error:
            logger.log_exc("POST_OAR_SERVER : Connection error: %s "
                % (error))
            raise Exception ("POST_OAR_SERVER : Connection error %s " %(error))

        finally:
            conn.close()

        if resp.status >= 400:
            raise ValueError ("Response Error %s, %s" %(resp.status,
                resp.reason))


        try:
            answer = json.loads(body)
            logger.debug("POSTRequestToOARRestAPI : answer %s" % (answer))
            return answer

        except ValueError, error:
            logger.log_exc("Failed to parse Server Response: error %s  \
                            %s" %(error))
            #raise ServerError("Failed to parse Server Response:" + answer)


class ParsingResourcesFull():
    """
    Class dedicated to parse the json response from a GET_resources_full from
    OAR.

    """
    def __init__(self):
        """
        Set the parsing dictionary. Works like a switch case, if the key is
        found in the dictionary, then the associated function is called.
        This is used in ParseNodes to create an usable dictionary from
        the Json returned by OAR when issuing a GET resources full request.

        .. seealso:: ParseNodes

        """
        self.resources_fulljson_dict = {
        'network_address': self.AddNodeNetworkAddr,
        'site':  self.AddNodeSite,
        # 'radio':  self.AddNodeRadio,
        'mobile':  self.AddMobility,
        'x':  self.AddPosX,
        'y':  self.AddPosY,
        'z': self.AddPosZ,
        'archi': self.AddHardwareType,
        'state': self.AddBootState,
        'id': self.AddOarNodeId,
        'mobility_type': self.AddMobilityType,
        }



    def AddOarNodeId(self, tuplelist, value):
        """Adds Oar internal node id to the nodes' attributes.

        Appends tuple ('oar_id', node_id) to the tuplelist. Used by ParseNodes.

        .. seealso:: ParseNodes

        """

        tuplelist.append(('oar_id', int(value)))


    def AddNodeNetworkAddr(self, dictnode, value):
        """First parsing function to be called to parse the json returned by OAR
        answering a GET_resources (/oarapi/resources.json) request.

        When a new node is found in the json, this function is responsible for
        creating a new entry in the dictionary for storing information on this
        specific node. The key is the node network address, which is also the
        node's hostname.
        The value associated with the key is a tuple list.It contains all
        the nodes attributes. The tuplelist will later be turned into a dict.

        :param dictnode: should be set to the OARGETParser atribute
            node_dictlist. It will store the information on the nodes.
        :param value: the node_id is the network_address in the raw json.
        :type value: string
        :type dictnode: dictionary

        .. seealso: ParseResources, ParseNodes
        """

        node_id = value
        dictnode[node_id] = [('node_id', node_id),('hostname', node_id) ]

        return node_id

    def AddNodeSite(self, tuplelist, value):
        """Add the site's node to the dictionary.


        :param tuplelist: tuple list on which to add the node's site.
            Contains the other node attributes as well.
        :param value: value to add to the tuple list, in this case the node's
            site.
        :type tuplelist: list
        :type value: string

        .. seealso:: AddNodeNetworkAddr

        """
        tuplelist.append(('site', str(value)))

    # def AddNodeRadio(tuplelist, value):
    #     """Add thenode's radio chipset type to the tuple list.

    #     :param tuplelist: tuple list on which to add the node's mobility
                # status. The tuplelist is the value associated with the node's
                # id in the OARGETParser
    #          's dictionary node_dictlist.
    #     :param value: name of the radio chipset on the node.
    #     :type tuplelist: list
    #     :type value: string

    #     .. seealso:: AddNodeNetworkAddr

    #     """
    #     tuplelist.append(('radio', str(value)))

    def AddMobilityType(self, tuplelist, value):
        """Adds  which kind of mobility it is, train or roomba robot.

        :param tuplelist: tuple list on which to add the node's mobility status.
            The tuplelist is the value associated with the node's id in the
            OARGETParser's dictionary node_dictlist.
        :param value: tells if a node is a mobile node or not. The value is
            found in the json.

        :type tuplelist: list
        :type value: integer

        """
        tuplelist.append(('mobility_type', str(value)))


    def AddMobility(self, tuplelist, value):
        """Add if the node is a mobile node or not to the tuple list.

        :param tuplelist: tuple list on which to add the node's mobility status.
            The tuplelist is the value associated with the node's id in the
            OARGETParser's dictionary node_dictlist.
        :param value: tells if a node is a mobile node or not. The value is found
            in the json.

        :type tuplelist: list
        :type value: integer

        .. seealso:: AddNodeNetworkAddr

        """
        if value is 0:
            tuplelist.append(('mobile', 'False'))
        else:
            tuplelist.append(('mobile', 'True'))


    def AddPosX(self, tuplelist, value):
        """Add the node's position on the x axis.

        :param tuplelist: tuple list on which to add the node's position . The
            tuplelist is the value associated with the node's id in the
            OARGETParser's dictionary node_dictlist.
        :param value: the position x.

        :type tuplelist: list
        :type value: integer

         .. seealso:: AddNodeNetworkAddr

        """
        tuplelist.append(('posx', value ))



    def AddPosY(self, tuplelist, value):
        """Add the node's position on the y axis.

        :param tuplelist: tuple list on which to add the node's position . The
            tuplelist is the value associated with the node's id in the
            OARGETParser's dictionary node_dictlist.
        :param value: the position y.

        :type tuplelist: list
        :type value: integer

         .. seealso:: AddNodeNetworkAddr

        """
        tuplelist.append(('posy', value))



    def AddPosZ(self, tuplelist, value):
        """Add the node's position on the z axis.

        :param tuplelist: tuple list on which to add the node's position . The
            tuplelist is the value associated with the node's id in the
            OARGETParser's dictionary node_dictlist.
        :param value: the position z.

        :type tuplelist: list
        :type value: integer

         .. seealso:: AddNodeNetworkAddr

        """

        tuplelist.append(('posz', value))



    def AddBootState(tself, tuplelist, value):
        """Add the node's state, Alive or Suspected.

        :param tuplelist: tuple list on which to add the node's state . The
            tuplelist is the value associated with the node's id in the
            OARGETParser 's dictionary node_dictlist.
        :param value: node's state.

        :type tuplelist: list
        :type value: string

         .. seealso:: AddNodeNetworkAddr

        """
        tuplelist.append(('boot_state', str(value)))


    def AddHardwareType(self, tuplelist, value):
        """Add the node's hardware model and radio chipset type to the tuple
        list.

        :param tuplelist: tuple list on which to add the node's architecture
            and radio chipset type.
        :param value: hardware type: radio chipset. The value contains both the
            architecture and the radio chipset, separated by a colon.
        :type tuplelist: list
        :type value: string

        .. seealso:: AddNodeNetworkAddr

        """

        value_list = value.split(':')
        tuplelist.append(('archi', value_list[0]))
        tuplelist.append(('radio', value_list[1]))


class OARGETParser:
    """Class providing parsing methods associated to specific GET requests.

    """

    def __init__(self, srv):
        self.version_json_dict = {
            'api_version': None, 'apilib_version': None,
            'api_timezone': None, 'api_timestamp': None, 'oar_version': None}
        self.config = Config()
        self.interface_hrn = self.config.SFA_INTERFACE_HRN
        self.timezone_json_dict = {
            'timezone': None, 'api_timestamp': None, }
        #self.jobs_json_dict = {
            #'total' : None, 'links' : [],\
            #'offset':None , 'items' : [], }
        #self.jobs_table_json_dict = self.jobs_json_dict
        #self.jobs_details_json_dict = self.jobs_json_dict
        self.server = srv
        self.node_dictlist = {}

        self.json_page = JsonPage()
        self.parsing_resourcesfull = ParsingResourcesFull()
        self.site_dict = {}
        self.jobs_list = []
        self.SendRequest("GET_version")


    def ParseVersion(self):
        """Parses the OAR answer to the GET_version ( /oarapi/version.json.)

        Finds the OAR apilib version currently used. Has an impact on the json
        structure returned by OAR, so the version has to be known before trying
        to parse the jsons returned after a get request has been issued.
        Updates the attribute version_json_dict.

        """

        if 'oar_version' in self.json_page.raw_json:
            self.version_json_dict.update(
                api_version=self.json_page.raw_json['api_version'],
                apilib_version=self.json_page.raw_json['apilib_version'],
                api_timezone=self.json_page.raw_json['api_timezone'],
                api_timestamp=self.json_page.raw_json['api_timestamp'],
                oar_version=self.json_page.raw_json['oar_version'])
        else:
            self.version_json_dict.update(
                api_version=self.json_page.raw_json['api'],
                apilib_version=self.json_page.raw_json['apilib'],
                api_timezone=self.json_page.raw_json['api_timezone'],
                api_timestamp=self.json_page.raw_json['api_timestamp'],
                oar_version=self.json_page.raw_json['oar'])

        print self.version_json_dict['apilib_version']


    def ParseTimezone(self):
        """Get the timezone used by OAR.

        Get the timezone from the answer to the GET_timezone request.
        :return: api_timestamp and api timezone.
        :rype: integer, integer

        .. warning:: unused.
        """
        api_timestamp = self.json_page.raw_json['api_timestamp']
        api_tz = self.json_page.raw_json['timezone']
        return api_timestamp, api_tz

    def ParseJobs(self):
        """Called when a GET_jobs request has been issued to OAR.

        Corresponds to /oarapi/jobs.json uri. Currently returns the raw json
        information dict.
        :returns: json_page.raw_json
        :rtype: dictionary

        .. warning:: Does not actually parse the information in the json. SA
            15/07/13.

        """
        self.jobs_list = []
        print " ParseJobs "
        return self.json_page.raw_json

    def ParseJobsTable(self):
        """In case we need to use the job table in the future.

        Associated with the GET_jobs_table : '/oarapi/jobs/table.json uri.
        .. warning:: NOT USED. DOES NOTHING.
        """
        print "ParseJobsTable"

    def ParseJobsDetails(self):
        """Currently only returns the same json in self.json_page.raw_json.

        .. todo:: actually parse the json
        .. warning:: currently, this function is not used a lot, so I have no
            idea what could  be useful to parse, returning the full json. NT
        """

        #logger.debug("ParseJobsDetails %s " %(self.json_page.raw_json))
        return self.json_page.raw_json


    def ParseJobsIds(self):
        """Associated with the GET_jobs_id OAR request.

        Parses the json dict (OAR answer) to the GET_jobs_id request
        /oarapi/jobs/id.json.


        :returns: dictionary whose keys are listed in the local variable
            job_resources and values that are in the json dictionary returned
            by OAR with the job information.
        :rtype: dict

        """
        job_resources = ['wanted_resources', 'name', 'id', 'start_time',
                         'state', 'owner', 'walltime', 'message']

        # Unused variable providing the contents of the json dict returned from
        # get job resources full request
        job_resources_full = [
            'launching_directory', 'links',
            'resubmit_job_id', 'owner', 'events', 'message',
            'scheduled_start', 'id', 'array_id', 'exit_code',
            'properties', 'state', 'array_index', 'walltime',
            'type', 'initial_request', 'stop_time', 'project',
            'start_time',  'dependencies', 'api_timestamp', 'submission_time',
            'reservation', 'stdout_file', 'types', 'cpuset_name',
            'name', 'wanted_resources', 'queue', 'stderr_file', 'command']


        job_info = self.json_page.raw_json
        #logger.debug("OARESTAPI ParseJobsIds %s" %(self.json_page.raw_json))
        values = []
        try:
            for k in job_resources:
                values.append(job_info[k])
            return dict(zip(job_resources, values))

        except KeyError:
            logger.log_exc("ParseJobsIds KeyError ")


    def ParseJobsIdResources(self):
        """ Parses the json produced by the request
        /oarapi/jobs/id/resources.json.
        Returns a list of oar node ids that are scheduled for the
        given job id.

        """
        job_resources = []
        for resource in self.json_page.raw_json['items']:
            job_resources.append(resource['id'])

        return job_resources

    def ParseResources(self):
        """ Parses the json produced by a get_resources request on oar."""

        #logger.debug("OARESTAPI \tParseResources " )
        #resources are listed inside the 'items' list from the json
        self.json_page.raw_json = self.json_page.raw_json['items']
        self.ParseNodes()

    def ParseReservedNodes(self):
        """  Returns an array containing the list of the jobs scheduled
        with the reserved nodes if available.

        :returns: list of job dicts, each dict containing the following keys:
            t_from, t_until, resources_ids (of the reserved nodes for this job).
            If the information is not available, default values will be set for
            these keys. The other keys are : state, lease_id and user.
        :rtype: list

        """

        #resources are listed inside the 'items' list from the json
        reservation_list = []
        job = {}
        #Parse resources info
        for json_element in self.json_page.raw_json['items']:
            #In case it is a real reservation (not asap case)
            if json_element['scheduled_start']:
                job['t_from'] = json_element['scheduled_start']
                job['t_until'] = int(json_element['scheduled_start']) + \
                    int(json_element['walltime'])
                #Get resources id list for the job
                job['resource_ids'] = [node_dict['id'] for node_dict
                                       in json_element['resources']]
            else:
                job['t_from'] = "As soon as possible"
                job['t_until'] = "As soon as possible"
                job['resource_ids'] = ["Undefined"]

            job['state'] = json_element['state']
            job['lease_id'] = json_element['id']

            job['user'] = json_element['owner']
            #logger.debug("OARRestapi \tParseReservedNodes job %s" %(job))
            reservation_list.append(job)
            #reset dict
            job = {}
        return reservation_list

    def ParseRunningJobs(self):
        """ Gets the list of nodes currently in use from the attributes of the
        running jobs.

        :returns: list of hostnames, the nodes that are currently involved in
            running jobs.
        :rtype: list


        """
        logger.debug("OARESTAPI \tParseRunningJobs_________________ ")
        #resources are listed inside the 'items' list from the json
        nodes = []
        for job in self.json_page.raw_json['items']:
            for node in job['nodes']:
                nodes.append(node['network_address'])
        return nodes

    def ChangeRawJsonDependingOnApilibVersion(self):
        """
        Check if the OAR apilib version is different from 0.2.10, in which case
        the Json answer is also dict instead as a plain list.

        .. warning:: the whole code is assuming the json contains a 'items' key
        .. seealso:: ConcatenateJsonPages, ParseJobs, ParseReservedNodes,
            ParseJobsIdResources, ParseResources, ParseRunningJobs
        .. todo:: Clean the whole code. Either suppose the  apilib will always
            provide the 'items' key, or handle different options.
        """

        if self.version_json_dict['apilib_version'] != "0.2.10":
            self.json_page.raw_json = self.json_page.raw_json['items']

    def ParseDeleteJobs(self):
        """ No need to parse anything in this function.A POST
        is done to delete the job.

        """
        return

    def ParseResourcesFull(self):
        """ This method is responsible for parsing all the attributes
        of all the nodes returned by OAR when issuing a get resources full.
        The information from the nodes and the sites are separated.
        Updates the node_dictlist so that the dictionnary of the platform's
        nodes is available afterwards.

        :returns: node_dictlist, a list of dictionaries about the nodes and
            their properties.
        :rtype: list

        """
        logger.debug("OARRESTAPI ParseResourcesFull___________ ")
        #print self.json_page.raw_json[1]
        #resources are listed inside the 'items' list from the json
        self.ChangeRawJsonDependingOnApilibVersion()
        self.ParseNodes()
        self.ParseSites()
        return self.node_dictlist

    def ParseResourcesFullSites(self):
        """ Called by GetSites which is unused.
        Originally used to get information from the sites, with for each site
        the list of nodes it has, along with their properties.

        :return: site_dict, dictionary of sites
        :rtype: dict

        .. warning:: unused
        .. seealso:: GetSites (IotlabShell)

        """
        self.ChangeRawJsonDependingOnApilibVersion()
        self.ParseNodes()
        self.ParseSites()
        return self.site_dict


    def ParseNodes(self):
        """ Parse nodes properties from OAR
        Put them into a dictionary with key = node id and value is a dictionary
        of the node properties and properties'values.

        """
        node_id = None
        _resources_fulljson_dict = \
            self.parsing_resourcesfull.resources_fulljson_dict
        keys = _resources_fulljson_dict.keys()
        keys.sort()

        for dictline in self.json_page.raw_json:
            node_id = None
            # dictionary is empty and/or a new node has to be inserted
            node_id = _resources_fulljson_dict['network_address'](
                self.node_dictlist, dictline['network_address'])
            for k in keys:
                if k in dictline:
                    if k == 'network_address':
                        continue

                    _resources_fulljson_dict[k](
                        self.node_dictlist[node_id], dictline[k])

            #The last property has been inserted in the property tuple list,
            #reset node_id
            #Turn the property tuple list (=dict value) into a dictionary
            self.node_dictlist[node_id] = dict(self.node_dictlist[node_id])
            node_id = None

    @staticmethod
    def iotlab_hostname_to_hrn(root_auth,  hostname):
        """
        Transforms a node hostname into a SFA hrn.

        :param root_auth: Name of the root authority of the SFA server. In
            our case, it is set to iotlab.
        :param hostname: node's hotname, given by OAR.
        :type root_auth: string
        :type hostname: string
        :returns: inserts the root_auth and '.' before the hostname.
        :rtype: string

        """
        return root_auth + '.' + hostname

    def ParseSites(self):
        """ Returns a list of dictionnaries containing the sites' attributes."""

        nodes_per_site = {}
        config = Config()
        #logger.debug(" OARrestapi.py \tParseSites  self.node_dictlist %s"\
                                                        #%(self.node_dictlist))
        # Create a list of nodes per site_id
        for node_id in self.node_dictlist:
            node = self.node_dictlist[node_id]

            if node['site'] not in nodes_per_site:
                nodes_per_site[node['site']] = []
                nodes_per_site[node['site']].append(node['node_id'])
            else:
                if node['node_id'] not in nodes_per_site[node['site']]:
                    nodes_per_site[node['site']].append(node['node_id'])

        #Create a site dictionary whose key is site_login_base
        # (name of the site) and value is a dictionary of properties,
        # including the list of the node_ids
        for node_id in self.node_dictlist:
            node = self.node_dictlist[node_id]
            node.update({'hrn': self.iotlab_hostname_to_hrn(self.interface_hrn,
                                                            node['hostname'])})
            self.node_dictlist.update({node_id: node})

            if node['site'] not in self.site_dict:
                self.site_dict[node['site']] = {
                    'site': node['site'],
                    'node_ids': nodes_per_site[node['site']],
                    'latitude': "48.83726",
                    'longitude': "- 2.10336",
                    'name': config.SFA_REGISTRY_ROOT_AUTH,
                    'pcu_ids': [], 'max_slices': None,
                    'ext_consortium_id': None,
                    'max_slivers': None, 'is_public': True,
                    'peer_site_id': None,
                    'abbreviated_name': "iotlab", 'address_ids': [],
                    'url': "https://portal.senslab.info", 'person_ids': [],
                    'site_tag_ids': [], 'enabled': True,  'slice_ids': [],
                    'date_created': None, 'peer_id': None
                }

    OARrequests_uri_dict = {
        'GET_version':
        {'uri': '/oarapi/version.json', 'parse_func': ParseVersion},

        'GET_timezone':
        {'uri': '/oarapi/timezone.json', 'parse_func': ParseTimezone},

        'GET_jobs':
        {'uri': '/oarapi/jobs.json', 'parse_func': ParseJobs},

        'GET_jobs_id':
        {'uri': '/oarapi/jobs/id.json', 'parse_func': ParseJobsIds},

        'GET_jobs_id_resources':
        {'uri': '/oarapi/jobs/id/resources.json',
        'parse_func': ParseJobsIdResources},

        'GET_jobs_table':
        {'uri': '/oarapi/jobs/table.json', 'parse_func': ParseJobsTable},

        'GET_jobs_details':
        {'uri': '/oarapi/jobs/details.json', 'parse_func': ParseJobsDetails},

        'GET_reserved_nodes':
        {'uri':
        '/oarapi/jobs/details.json?state=Running,Waiting,Launching',
        'owner': '&user=', 'parse_func': ParseReservedNodes},

        'GET_running_jobs':
        {'uri': '/oarapi/jobs/details.json?state=Running',
        'parse_func': ParseRunningJobs},

        'GET_resources_full':
        {'uri': '/oarapi/resources/full.json',
        'parse_func': ParseResourcesFull},

        'GET_sites':
        {'uri': '/oarapi/resources/full.json',
        'parse_func': ParseResourcesFullSites},

        'GET_resources':
        {'uri': '/oarapi/resources.json', 'parse_func': ParseResources},

        'DELETE_jobs_id':
        {'uri': '/oarapi/jobs/id.json', 'parse_func': ParseDeleteJobs}}


    def SendRequest(self, request, strval=None, username=None):
        """ Connects to OAR , sends the valid GET requests and uses
        the appropriate json parsing functions.

        :returns: calls to the appropriate parsing function, associated with the
            GET request
        :rtype: depends on the parsing function called.

        .. seealso:: OARrequests_uri_dict
        """
        save_json = None

        self.json_page.ResetNextPage()
        save_json = []

        if request in self.OARrequests_uri_dict:
            while self.json_page.next_page:
                self.json_page.raw_json = self.server.GETRequestToOARRestAPI(
                    request,
                    strval,
                    self.json_page.next_offset,
                    username)
                self.json_page.FindNextPage()
                if self.json_page.concatenate:
                    save_json.append(self.json_page.raw_json)

            if self.json_page.concatenate and self.json_page.end:
                self.json_page.raw_json = \
                    self.json_page.ConcatenateJsonPages(save_json)

            return self.OARrequests_uri_dict[request]['parse_func'](self)
        else:
            logger.error("OARRESTAPI OARGetParse __init__ : ERROR_REQUEST "
                         % (request))
