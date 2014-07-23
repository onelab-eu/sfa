"""
File providing methods to generate valid RSpecs for the Iotlab testbed.
Contains methods to get information on slice, slivers, nodes and leases,
formatting them and turn it into a RSpec.
"""
from sfa.util.sfatime import utcparse, datetime_to_string
from sfa.util.xrn import Xrn, hrn_to_urn, urn_to_hrn
from sfa.iotlab.iotlabxrn import IotlabXrn
from sfa.rspecs.rspec import RSpec
#from sfa.rspecs.elements.location import Location
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.login import Login
# from sfa.rspecs.elements.services import ServicesElement
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.lease import Lease
from sfa.rspecs.elements.granularity import Granularity
from sfa.rspecs.version_manager import VersionManager
from sfa.storage.model import SliverAllocation
from sfa.rspecs.elements.versions.iotlabv1Node import IotlabPosition, \
    IotlabNode, IotlabLocation
from sfa.iotlab.iotlabxrn import xrn_object
from sfa.util.sfalogging import logger
import time

class IotlabAggregate:
    """Aggregate manager class for Iotlab. """

    sites = {}
    nodes = {}
    api = None
    interfaces = {}
    links = {}
    node_tags = {}

    prepared = False

    user_options = {}

    def __init__(self, driver):
        self.driver = driver

    def get_slice_and_slivers(self, slice_xrn, login=None):
        """
        Get the slices and the associated leases if any from the iotlab
            testbed. One slice can have mutliple leases.
            For each slice, get the nodes in the  associated lease
            and create a sliver with the necessary info and insert it into the
            sliver dictionary, keyed on the node hostnames.
            Returns a dict of slivers based on the sliver's node_id.
            Called by get_rspec.


        :param slice_xrn: xrn of the slice
        :param login: user's login on iotlab ldap

        :type slice_xrn: string
        :type login: string
        :returns: a list of slices dict and a list of Sliver object
        :rtype: (list, list)

        .. note: There is no real slivers in iotlab, only leases. The goal
            is to be consistent with the SFA standard.

        """
        slivers = {}
        sfa_slice = None
        if slice_xrn is None:
            return (sfa_slice, slivers)
        slice_urn = hrn_to_urn(slice_xrn, 'slice')
        slice_hrn, _ = urn_to_hrn(slice_xrn)

        # GetSlices always returns a list, even if there is only one element
        slices = self.driver.GetSlices(slice_filter=str(slice_hrn),
                                        slice_filter_type='slice_hrn',
                                        login=login)

        logger.debug("IotlabAggregate api \tget_slice_and_slivers \
                      slice_hrn %s \r\n slices %s self.driver.hrn %s"
                     % (slice_hrn, slices, self.driver.hrn))
        if slices == []:
            return (sfa_slice, slivers)

        # sort slivers by node id , if there is a job
        #and therefore, node allocated to this slice
        # for sfa_slice in slices:
        sfa_slice = slices[0]
        try:
            node_ids_list = sfa_slice['node_ids']
        except KeyError:
            logger.log_exc("IOTLABAGGREGATE \t \
                        get_slice_and_slivers No nodes in the slice \
                        - KeyError ")
            node_ids_list = []
            # continue

        for node in node_ids_list:
            sliver_xrn = Xrn(slice_urn, type='sliver', id=node)
            sliver_xrn.set_authority(self.driver.hrn)
            sliver = Sliver({'sliver_id': sliver_xrn.urn,
                            'name': sfa_slice['hrn'],
                            'type': 'iotlab-node',
                            'tags': []})

            slivers[node] = sliver

        #Add default sliver attribute :
        #connection information for iotlab
        # if get_authority(sfa_slice['hrn']) == \
            # self.driver.testbed_shell.root_auth:
        #     tmp = sfa_slice['hrn'].split('.')
        #     ldap_username = tmp[1].split('_')[0]
        #     ssh_access = None
        #     slivers['default_sliver'] = {'ssh': ssh_access,
        #                                  'login': ldap_username}
        # look in ldap:
        ldap_username = self.find_ldap_username_from_slice(sfa_slice)

        if ldap_username is not None:
            ssh_access = None
            slivers['default_sliver'] = {'ssh': ssh_access,
                                             'login': ldap_username}


        logger.debug("IOTLABAGGREGATE api get_slice_and_slivers  slivers %s "
                     % (slivers))
        return (slices, slivers)

    def find_ldap_username_from_slice(self, sfa_slice):
        """
        Gets the ldap username of the user based on the information contained
        in ist sfa_slice record.

        :param sfa_slice: the user's slice record. Must contain the
            reg_researchers key.
        :type sfa_slice: dictionary
        :returns: ldap_username, the ldap user's login.
        :rtype: string

        """
        researchers = [sfa_slice['reg_researchers'][0].__dict__]
        # look in ldap:
        ldap_username = None
        ret =  self.driver.testbed_shell.GetPersons(researchers)
        if len(ret) != 0:
            ldap_username = ret[0]['uid']

        return ldap_username



    def get_nodes(self, options=None):
    # def node_to_rspec_node(self, node, sites, node_tags,
    #     grain=None, options={}):
        """Returns the nodes in the slice using the rspec format, with all the
        nodes' properties.

        Fetch the nodes ids in the slices dictionary and get all the nodes
        properties from OAR. Makes a rspec dicitonary out of this and returns
        it. If the slice does not have any job running or scheduled, that is
        it has no reserved nodes, then returns an empty list.

        :returns: An empty list if the slice has no reserved nodes, a rspec
            list with all the nodes and their properties (a dict per node)
            otherwise.
        :rtype: list

        .. seealso:: get_slice_and_slivers

        """

        # NT: the semantic of this function is not clear to me :
        # if slice is not defined, then all the nodes should be returned
        # if slice is defined, we should return only the nodes that
        # are part of this slice
        # but what is the role of the slivers parameter ?
        # So i assume that slice['node_ids'] will be the same as slivers for us
        filter_nodes = None
        if options:
            geni_available = options.get('geni_available')
            if geni_available == True:
                filter_nodes['boot_state'] = ['Alive']

        # slice_nodes_list = []
        # if slices is not None:
        #     for one_slice in slices:
        #         try:
        #             slice_nodes_list = one_slice['node_ids']
    #              # if we are dealing with a slice that has no node just
    #              # return an empty list. In iotlab a slice can have multiple
    #              # jobs scheduled, so it either has at least one lease or
    #              # not at all.
        #         except KeyError:
        #             return []

        # get the granularity in second for the reservation system
        # grain = self.driver.testbed_shell.GetLeaseGranularity()

        nodes = self.driver.testbed_shell.GetNodes(node_filter_dict =
                                                    filter_nodes)

        nodes_dict = {}

        #if slices, this means we got to list all the nodes given to this slice
        # Make a list of all the nodes in the slice before getting their
        #attributes
        # rspec_nodes = []

        # logger.debug("IOTLABAGGREGATE api get_nodes slices  %s "
                     # % (slices))

        # reserved_nodes = self.driver.testbed_shell.GetNodesCurrentlyInUse()
        # logger.debug("IOTLABAGGREGATE api get_nodes slice_nodes_list  %s "
                     # % (slice_nodes_list))
        for node in nodes:
            nodes_dict[node['node_id']] = node

        return nodes_dict

    def node_to_rspec_node(self, node):
        """ Creates a rspec node structure with the appropriate information
        based on the node information that can be found in the node dictionary.

        :param node: node data. this dict contains information about the node
            and must have the following keys : mobile, radio, archi, hostname,
            boot_state, site, x, y ,z (position).
        :type node: dictionary.

        :returns: node dictionary containing the following keys : mobile, archi,
            radio, component_id, component_name, component_manager_id,
            authority_id, boot_state, exclusive, hardware_types, location,
            position, granularity, tags.
        :rtype: dict

        """

        grain = self.driver.testbed_shell.GetLeaseGranularity()

        rspec_node = IotlabNode()
        # xxx how to retrieve site['login_base']
        #site_id=node['site_id']
        #site=sites_dict[site_id]

        rspec_node['mobile'] = node['mobile']
        rspec_node['archi'] = node['archi']
        rspec_node['radio'] = node['radio']

        iotlab_xrn = xrn_object(self.driver.testbed_shell.root_auth,
                                       node['hostname'])
        rspec_node['component_id'] = iotlab_xrn.urn
        rspec_node['component_name'] = node['hostname']
        rspec_node['component_manager_id'] = \
                        hrn_to_urn(self.driver.testbed_shell.root_auth,
                        'authority+sa')

        # Iotlab's nodes are federated : there is only one authority
        # for all Iotlab sites, registered in SFA.
        # Removing the part including the site
        # in authority_id SA 27/07/12
        rspec_node['authority_id'] = rspec_node['component_manager_id']

        # do not include boot state (<available> element)
        #in the manifest rspec


        rspec_node['boot_state'] = node['boot_state']
        # if node['hostname'] in reserved_nodes:
        #     rspec_node['boot_state'] = "Reserved"
        rspec_node['exclusive'] = 'true'
        rspec_node['hardware_types'] = [HardwareType({'name': \
                                        'iotlab-node'})]

        location = IotlabLocation({'country':'France', 'site': \
                                    node['site']})
        rspec_node['location'] = location


        position = IotlabPosition()
        for field in position :
            try:
                position[field] = node[field]
            except KeyError, error :
                logger.log_exc("IOTLABAGGREGATE\t get_nodes \
                                                position %s "% (error))

        rspec_node['position'] = position


        # Granularity
        granularity = Granularity({'grain': grain})
        rspec_node['granularity'] = granularity
        rspec_node['tags'] = []
        # if node['hostname'] in slivers:
        #     # add sliver info
        #     sliver = slivers[node['hostname']]
        #     rspec_node['sliver_id'] = sliver['sliver_id']
        #     rspec_node['client_id'] = node['hostname']
        #     rspec_node['slivers'] = [sliver]

        #     # slivers always provide the ssh service
        #     login = Login({'authentication': 'ssh-keys', \
        #             'hostname': node['hostname'], 'port':'22', \
        #             'username': sliver['name']})
        #     service = Services({'login': login})
        #     rspec_node['services'] = [service]

        return rspec_node


    def rspec_node_to_geni_sliver(self, rspec_node, sliver_allocations = None):
        """Makes a geni sliver structure from all the nodes allocated
        to slivers in the sliver_allocations dictionary. Returns the states
        of the sliver.

        :param rspec_node: Node information contained in a rspec data structure
            fashion.
        :type rspec_node: dictionary
        :param sliver_allocations:
        :type sliver_allocations: dictionary

        :returns: Dictionary with the following keys: geni_sliver_urn,
            geni_expires, geni_allocation_status, geni_operational_status,
            geni_error.

        :rtype: dictionary

        .. seealso:: node_to_rspec_node

        """
        if sliver_allocations is None: sliver_allocations={}
        if rspec_node['sliver_id'] in sliver_allocations:
            # set sliver allocation and operational status
            sliver_allocation = sliver_allocations[rspec_node['sliver_id']]
            if sliver_allocation:
                allocation_status = sliver_allocation.allocation_state
                if allocation_status == 'geni_allocated':
                    op_status =  'geni_pending_allocation'
                elif allocation_status == 'geni_provisioned':
                    op_status = 'geni_ready'
                else:
                    op_status = 'geni_unknown'
            else:
                allocation_status = 'geni_unallocated'
        else:
            allocation_status = 'geni_unallocated'
            op_status = 'geni_failed'
        # required fields
        geni_sliver = {'geni_sliver_urn': rspec_node['sliver_id'],
                       'geni_expires': rspec_node['expires'],
                       'geni_allocation_status' : allocation_status,
                       'geni_operational_status': op_status,
                       'geni_error': '',
                       }
        return geni_sliver


    def sliver_to_rspec_node(self, sliver, sliver_allocations):
        """Used by describe to format node information into a rspec compliant
        structure.

        Creates a node rspec compliant structure by calling node_to_rspec_node.
        Adds slivers, if any, to rspec node structure. Returns the updated
        rspec node struct.

        :param sliver: sliver dictionary. Contains keys: urn, slice_id, hostname
            and slice_name.
        :type sliver: dictionary
        :param sliver_allocations: dictionary of slivers
        :type sliver_allocations: dict

        :returns: Node dictionary with all necessary data.

        .. seealso:: node_to_rspec_node
        """
        rspec_node = self.node_to_rspec_node(sliver)
        rspec_node['expires'] = datetime_to_string(utcparse(sliver['expires']))
        # add sliver info
        logger.debug("IOTLABAGGREGATE api \t  sliver_to_rspec_node sliver \
                        %s \r\nsliver_allocations %s" % (sliver,
                            sliver_allocations))
        rspec_sliver = Sliver({'sliver_id': sliver['urn'],
                         'name': sliver['slice_id'],
                         'type': 'iotlab-exclusive',
                         'tags': []})
        rspec_node['sliver_id'] = rspec_sliver['sliver_id']

        if sliver['urn'] in sliver_allocations:
            rspec_node['client_id'] = sliver_allocations[
                                                    sliver['urn']].client_id
            if sliver_allocations[sliver['urn']].component_id:
                rspec_node['component_id'] = sliver_allocations[
                                                    sliver['urn']].component_id
        rspec_node['slivers'] = [rspec_sliver]

        # slivers always provide the ssh service
        login = Login({'authentication': 'ssh-keys',
                       'hostname': sliver['hostname'],
                       'port':'22',
                       'username': sliver['slice_name'],
                       'login': sliver['slice_name']
                      })
        return rspec_node


    def get_leases(self, slice=None, options=None):
        if options is None: options={}
        filter={}
        if slice:
           filter.update({'name':slice['slice_name']})
        #return_fields = ['lease_id', 'hostname', 'site_id', 'name', 't_from', 't_until']
        leases = self.driver.GetLeases(lease_filter_dict=filter)
        grain = self.driver.testbed_shell.GetLeaseGranularity()
  
        rspec_leases = []
        for lease in leases:
            #as many leases as there are nodes in the job
            for node in lease['reserved_nodes']:
                rspec_lease = Lease()
                rspec_lease['lease_id'] = lease['lease_id']
                #site = node['site_id']
                iotlab_xrn = xrn_object(self.driver.testbed_shell.root_auth,
                                               node)
                rspec_lease['component_id'] = iotlab_xrn.urn
                #rspec_lease['component_id'] = hostname_to_urn(self.driver.hrn,\
                                        #site, node['hostname'])
                try:
                    rspec_lease['slice_id'] = lease['slice_id']
                except KeyError:
                    #No info on the slice used in testbed_xp table
                    pass
                rspec_lease['start_time'] = lease['t_from']
                rspec_lease['duration'] = (lease['t_until'] - lease['t_from']) \
                     / grain
                rspec_leases.append(rspec_lease)
        return rspec_leases


    def get_all_leases(self, ldap_username):
        """
        Get list of lease dictionaries which all have the mandatory keys
        ('lease_id', 'hostname', 'site_id', 'name', 'start_time', 'duration').
        All the leases running or scheduled are returned.

        :param ldap_username: if ldap uid is not None, looks for the leases
            belonging to this user.
        :type ldap_username: string
        :returns: rspec lease dictionary with keys lease_id, component_id,
            slice_id, start_time, duration where the lease_id is the oar job id,
            component_id is the node's urn, slice_id is the slice urn,
            start_time is the timestamp starting time and duration is expressed
            in terms of the testbed's granularity.
        :rtype: dict

        .. note::There is no filtering of leases within a given time frame.
            All the running or scheduled leases are returned. options
            removed SA 15/05/2013


        """

        logger.debug("IOTLABAGGREGATE  get_all_leases ldap_username %s "
                     % (ldap_username))
        leases = self.driver.GetLeases(login=ldap_username)
        grain = self.driver.testbed_shell.GetLeaseGranularity()

        rspec_leases = []
        for lease in leases:
            #as many leases as there are nodes in the job
            for node in lease['reserved_nodes']:
                rspec_lease = Lease()
                rspec_lease['lease_id'] = lease['lease_id']
                #site = node['site_id']
                iotlab_xrn = xrn_object(self.driver.testbed_shell.root_auth,
                                               node)
                rspec_lease['component_id'] = iotlab_xrn.urn
                #rspec_lease['component_id'] = hostname_to_urn(self.driver.hrn,\
                                        #site, node['hostname'])
                try:
                    rspec_lease['slice_id'] = lease['slice_id']
                except KeyError:
                    #No info on the slice used in testbed_xp table
                    pass
                rspec_lease['start_time'] = lease['t_from']
                rspec_lease['duration'] = (lease['t_until'] - lease['t_from']) \
                     / grain
                rspec_leases.append(rspec_lease)
        return rspec_leases

    def get_rspec(self, slice_xrn=None, login=None, version=None,
                  options=None):
        """
        Returns xml rspec:
        - a full advertisement rspec with the testbed resources if slice_xrn is
        not specified.If a lease option is given, also returns the leases
        scheduled on the testbed.
        - a manifest Rspec with the leases and nodes in slice's leases if
        slice_xrn is not None.

        :param slice_xrn: srn of the slice
        :type slice_xrn: string
        :param login: user'uid (ldap login) on iotlab
        :type login: string
        :param version: can be set to sfa or iotlab
        :type version: RSpecVersion
        :param options: used to specify if the leases should also be included in
            the returned rspec.
        :type options: dict

        :returns: Xml Rspec.
        :rtype: XML


        """

        ldap_username = None
        rspec = None
        version_manager = VersionManager()
        version = version_manager.get_version(version)
        logger.debug("IotlabAggregate \t get_rspec ***version %s \
                    version.type %s  version.version %s options %s \r\n"
                     % (version, version.type, version.version, options))

        if slice_xrn is None:
            rspec_version = version_manager._get_version(version.type,
                                                         version.version, 'ad')

        else:
            rspec_version = version_manager._get_version(
                version.type, version.version, 'manifest')

        slices, slivers = self.get_slice_and_slivers(slice_xrn, login)
        if slice_xrn and slices is not None:
            #Get user associated with this slice
            #for one_slice in slices :
            ldap_username = self.find_ldap_username_from_slice(slices[0])
            # ldap_username = slices[0]['reg_researchers'][0].__dict__['hrn']
            #  # ldap_username = slices[0]['user']
            # tmp = ldap_username.split('.')
            # ldap_username = tmp[1]
            logger.debug("IotlabAggregate \tget_rspec **** \
                    LDAP USERNAME %s \r\n" \
                    % (ldap_username))
        #at this point sliver may be empty if no iotlab job
        #is running for this user/slice.
        rspec = RSpec(version=rspec_version, user_options=options)

        logger.debug("\r\n \r\n IotlabAggregate \tget_rspec *** \
                      slice_xrn %s slices  %s\r\n \r\n"
                     % (slice_xrn, slices))

        if options is not None:
            lease_option = options['list_leases']
        else:
            #If no options are specified, at least print the resources
            lease_option = 'all'
           #if slice_xrn :
               #lease_option = 'all'

        if lease_option in ['all', 'resources']:
        #if not options.get('list_leases') or options.get('list_leases')
        #and options['list_leases'] != 'leases':
            nodes = self.get_nodes()
            logger.debug("\r\n")
            logger.debug("IotlabAggregate \t lease_option %s \
                          get rspec  ******* nodes %s"
                         % (lease_option, nodes))

            sites_set = set([node['location']['site'] for node in nodes])

            #In case creating a job,  slice_xrn is not set to None
            rspec.version.add_nodes(nodes)
            if slice_xrn and slices is not None:
            #     #Get user associated with this slice
            #     #for one_slice in slices :
            #     ldap_username = slices[0]['reg_researchers']
            #      # ldap_username = slices[0]['user']
            #     tmp = ldap_username.split('.')
            #     ldap_username = tmp[1]
            #      # ldap_username = tmp[1].split('_')[0]

                logger.debug("IotlabAggregate \tget_rspec **** \
                        version type %s ldap_ user %s \r\n" \
                        % (version.type, ldap_username))
                if version.type == "Iotlab":
                    rspec.version.add_connection_information(
                        ldap_username, sites_set)

            default_sliver = slivers.get('default_sliver', [])
            if default_sliver and len(nodes) is not 0:
                #default_sliver_attribs = default_sliver.get('tags', [])
                logger.debug("IotlabAggregate \tget_rspec **** \
                        default_sliver%s \r\n" % (default_sliver))
                for attrib in default_sliver:
                    rspec.version.add_default_sliver_attribute(
                        attrib, default_sliver[attrib])

        if lease_option in ['all','leases']:
            leases = self.get_all_leases(ldap_username)
            rspec.version.add_leases(leases)
            logger.debug("IotlabAggregate \tget_rspec **** \
                       FINAL RSPEC %s \r\n" % (rspec.toxml()))
        return rspec.toxml()

    def get_slivers(self, urns, options=None):
        """Get slivers of the given slice urns. Slivers contains slice, node and
        user information.

        For Iotlab, returns the leases with sliver ids and their allocation
        status.

        :param urns: list of  slice urns.
        :type urns: list of strings
        :param options: unused
        :type options: unused

        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3/CommonConcepts#urns
        """

        if options is None: options={}
        slice_ids = set()
        node_ids = []
        for urn in urns:
            xrn = IotlabXrn(xrn=urn)
            if xrn.type == 'sliver':
                 # id: slice_id-node_id
                try:
                    sliver_id_parts = xrn.get_sliver_id_parts()
                    slice_id = int(sliver_id_parts[0])
                    node_id = int(sliver_id_parts[1])
                    slice_ids.add(slice_id)
                    node_ids.append(node_id)
                except ValueError:
                    pass
            else:
                slice_names = set()
                slice_names.add(xrn.hrn)


        logger.debug("IotlabAggregate \t get_slivers urns %s slice_ids %s \
                       node_ids %s\r\n" % (urns, slice_ids, node_ids))
        logger.debug("IotlabAggregate \t get_slivers xrn %s slice_names %s \
                       \r\n" % (xrn, slice_names))
        filter_sliver = {}
        if slice_names:
            filter_sliver['slice_hrn'] = list(slice_names)
            slice_hrn = filter_sliver['slice_hrn'][0]

            slice_filter_type = 'slice_hrn'

        # if slice_ids:
        #     filter['slice_id'] = list(slice_ids)
        # # get slices
        if slice_hrn:
            slices = self.driver.GetSlices(slice_hrn,
                slice_filter_type)
            leases = self.driver.GetLeases({'slice_hrn':slice_hrn})
        logger.debug("IotlabAggregate \t get_slivers \
                       slices %s leases %s\r\n" % (slices, leases ))
        if not slices:
            return []

        single_slice = slices[0]
        # get sliver users
        user = single_slice['reg_researchers'][0].__dict__
        logger.debug("IotlabAggregate \t get_slivers user %s \
                       \r\n" % (user))

        # construct user key info
        person = self.driver.testbed_shell.ldap.LdapFindUser(record=user)
        logger.debug("IotlabAggregate \t get_slivers person %s \
                       \r\n" % (person))
        # name = person['last_name']
        user['login'] = person['uid']
        user['user_urn'] = hrn_to_urn(user['hrn'], 'user')
        user['keys'] = person['pkey']


        try:
            node_ids = single_slice['node_ids']
            node_list = self.driver.testbed_shell.GetNodes(
                    {'hostname':single_slice['node_ids']})
            node_by_hostname = dict([(node['hostname'], node)
                                        for node in node_list])
        except KeyError:
            logger.warning("\t get_slivers No slivers in slice")
            # slice['node_ids'] = node_ids
        # nodes_dict = self.get_slice_nodes(slice, options)

        slivers = []
        for current_lease in leases:
            for hostname in current_lease['reserved_nodes']:
                node = {}
                node['slice_id'] = current_lease['slice_id']
                node['slice_hrn'] = current_lease['slice_hrn']
                slice_name = current_lease['slice_hrn'].split(".")[1]
                node['slice_name'] = slice_name
                index = current_lease['reserved_nodes'].index(hostname)
                node_id = current_lease['resource_ids'][index]
                # node['slice_name'] = user['login']
                # node.update(single_slice)
                more_info = node_by_hostname[hostname]
                node.update(more_info)
                # oar_job_id is the slice_id (lease_id)
                sliver_hrn = '%s.%s-%s' % (self.driver.hrn,
                            current_lease['lease_id'], node_id)
                node['node_id'] = node_id
                node['expires'] = current_lease['t_until']
                node['sliver_id'] = Xrn(sliver_hrn, type='sliver').urn
                node['urn'] = node['sliver_id']
                node['services_user'] = [user]

                slivers.append(node)
        return slivers

    def list_resources(self, version = None, options=None):
        """
        Returns an advertisement Rspec of available resources at this
        aggregate. This Rspec contains a resource listing along with their
        description, providing sufficient information for clients to be able to
        select among available resources.

        :param options: various options. The valid options are: {boolean
            geni_compressed <optional>; struct geni_rspec_version { string type;
            #case insensitive , string version; # case insensitive}} . The only
            mandatory options if options is specified is geni_rspec_version.
        :type options: dictionary

        :returns: On success, the value field of the return struct will contain
            a geni.rspec advertisment RSpec
        :rtype: Rspec advertisement in xml.

        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3/CommonConcepts#RSpecdatatype
        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3#ListResources
        """

        if options is None: options={}
        version_manager = VersionManager()
        version = version_manager.get_version(version)
        rspec_version = version_manager._get_version(version.type,
                                                    version.version, 'ad')
        rspec = RSpec(version=rspec_version, user_options=options)
        # variable ldap_username to be compliant with  get_all_leases
        # prototype. Now unused in geni-v3 since we are getting all the leases
        # here
        ldap_username = None
        if not options.get('list_leases') or options['list_leases'] != 'leases':
            # get nodes
            nodes_dict  = self.get_nodes(options)

            # no interfaces on iotlab nodes
            # convert nodes to rspec nodes
            rspec_nodes = []
            for node_id in nodes_dict:
                node = nodes_dict[node_id]
                rspec_node = self.node_to_rspec_node(node)
                rspec_nodes.append(rspec_node)
            rspec.version.add_nodes(rspec_nodes)

            # add links
            # links = self.get_links(sites, nodes_dict, interfaces)
            # rspec.version.add_links(links)

        if not options.get('list_leases') or options.get('list_leases') \
            and options['list_leases'] != 'resources':
            leases = self.get_all_leases(ldap_username)
            rspec.version.add_leases(leases)

        return rspec.toxml()


    def describe(self, urns, version=None, options=None):
        """
        Retrieve a manifest RSpec describing the resources contained by the
        named entities, e.g. a single slice or a set of the slivers in a slice.
        This listing and description should be sufficiently descriptive to allow
        experimenters to use the resources.

        :param urns: If a slice urn is supplied and there are no slivers in the
            given slice at this aggregate, then geni_rspec shall be a valid
            manifest RSpec, containing no node elements - no resources.
        :type urns: list  or strings
        :param options: various options. the valid options are: {boolean
            geni_compressed <optional>; struct geni_rspec_version { string type;
            #case insensitive , string version; # case insensitive}}
        :type options: dictionary

        :returns: On success returns the following dictionary {geni_rspec:
            <geni.rspec, a Manifest RSpec>, geni_urn: <string slice urn of the
            containing slice>, geni_slivers:{ geni_sliver_urn:
            <string sliver urn>, geni_expires:  <dateTime.rfc3339 allocation
            expiration string, as in geni_expires from SliversStatus>,
            geni_allocation_status: <string sliver state - e.g. geni_allocated
            or geni_provisioned >, geni_operational_status:
            <string sliver operational state>, geni_error: <optional string.
            The field may be omitted entirely but may not be null/None,
            explaining any failure for a sliver.>}

        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3#Describe
        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3/CommonConcepts#urns
        """
        if options is None: options={}
        version_manager = VersionManager()
        version = version_manager.get_version(version)
        rspec_version = version_manager._get_version(
                                    version.type, version.version, 'manifest')
        rspec = RSpec(version=rspec_version, user_options=options)

        # get slivers
        geni_slivers = []
        slivers = self.get_slivers(urns, options)
        if slivers:
            rspec_expires = datetime_to_string(utcparse(slivers[0]['expires']))
        else:
            rspec_expires = datetime_to_string(utcparse(time.time()))
        rspec.xml.set('expires',  rspec_expires)

        # lookup the sliver allocations
        geni_urn = urns[0]
        sliver_ids = [sliver['sliver_id'] for sliver in slivers]
        constraint = SliverAllocation.sliver_id.in_(sliver_ids)
        query = self.driver.api.dbsession().query(SliverAllocation)
        sliver_allocations = query.filter((constraint)).all()
        sliver_allocation_dict = {}
        for sliver_allocation in sliver_allocations:
            geni_urn = sliver_allocation.slice_urn
            sliver_allocation_dict[sliver_allocation.sliver_id] = \
                                                            sliver_allocation
        if not options.get('list_leases') or options['list_leases'] != 'leases':                                                    
            # add slivers
            nodes_dict = {}
            for sliver in slivers:
                nodes_dict[sliver['node_id']] = sliver
            rspec_nodes = []
            for sliver in slivers:
                rspec_node = self.sliver_to_rspec_node(sliver,
                                                        sliver_allocation_dict)
                rspec_nodes.append(rspec_node)
                geni_sliver = self.rspec_node_to_geni_sliver(rspec_node,
                                sliver_allocation_dict)
                geni_slivers.append(geni_sliver)
            rspec.version.add_nodes(rspec_nodes)

        if not options.get('list_leases') or options['list_leases'] == 'resources':
            if slivers:
                leases = self.get_leases(slivers[0])
                rspec.version.add_leases(leases)

        return {'geni_urn': geni_urn,
                'geni_rspec': rspec.toxml(),
                'geni_slivers': geni_slivers}
