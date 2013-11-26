"""
File providing methods to generate valid RSpecs for the Iotlab testbed.
Contains methods to get information on slice, slivers, nodes and leases,
formatting them and turn it into a RSpec.
"""
from sfa.util.xrn import hrn_to_urn, urn_to_hrn, get_authority

from sfa.rspecs.rspec import RSpec
#from sfa.rspecs.elements.location import Location
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.login import Login
from sfa.rspecs.elements.services import ServicesElement
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.lease import Lease
from sfa.rspecs.elements.granularity import Granularity
from sfa.rspecs.version_manager import VersionManager

from sfa.rspecs.elements.versions.iotlabv1Node import IotlabPosition, \
    IotlabNode, IotlabLocation

from sfa.util.sfalogging import logger
from sfa.util.xrn import Xrn





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
        slice_name = slice_hrn

        # GetSlices always returns a list, even if there is only one element
        slices = self.driver.testbed_shell.GetSlices(slice_filter=str(slice_name),
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
        # if get_authority(sfa_slice['hrn']) == self.driver.testbed_shell.root_auth:
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
        researchers = [sfa_slice['reg_researchers'][0].__dict__]
        # look in ldap:
        ldap_username = None
        ret =  self.driver.testbed_shell.GetPersons(researchers)
        if len(ret) != 0:
            ldap_username = ret[0]['uid']

        return ldap_username



    def get_nodes(self, slices=None, slivers=[], options=None):
    # def node_to_rspec_node(self, node, sites, node_tags,
    #     grain=None, options={}):
        """Returns the nodes in the slice using the rspec format, with all the
        nodes' properties.

        Fetch the nodes ids in the slices dictionary and get all the nodes
        properties from OAR. Makes a rspec dicitonary out of this and returns
        it. If the slice does not have any job running or scheduled, that is
        it has no reserved nodes, then returns an empty list.

        :param slices: list of slices (record dictionaries)
        :param slivers: the list of slivers in all the slices
        :type slices: list of dicts
        :type slivers: list of Sliver object (dictionaries)
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

        nodes = self.driver.testbed_shell.GetNodes()

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
            # if slice_nodes_list == [] or node['hostname'] in slice_nodes_list:

            #     rspec_node = IotlabNode()
            #     # xxx how to retrieve site['login_base']
            #     #site_id=node['site_id']
            #     #site=sites_dict[site_id]

            #     rspec_node['mobile'] = node['mobile']
            #     rspec_node['archi'] = node['archi']
            #     rspec_node['radio'] = node['radio']

            #     iotlab_xrn = xrn_object(self.driver.testbed_shell.root_auth,
            #                                    node['hostname'])
            #     rspec_node['component_id'] = iotlab_xrn.urn
            #     rspec_node['component_name'] = node['hostname']
            #     rspec_node['component_manager_id'] = \
            #                     hrn_to_urn(self.driver.testbed_shell.root_auth,
            #                     'authority+sa')

            #     # Iotlab's nodes are federated : there is only one authority
            #     # for all Iotlab sites, registered in SFA.
            #     # Removing the part including the site
            #     # in authority_id SA 27/07/12
            #     rspec_node['authority_id'] = rspec_node['component_manager_id']

            #     # do not include boot state (<available> element)
            #     #in the manifest rspec


            #     rspec_node['boot_state'] = node['boot_state']
            #     if node['hostname'] in reserved_nodes:
            #         rspec_node['boot_state'] = "Reserved"
            #     rspec_node['exclusive'] = 'true'
            #     rspec_node['hardware_types'] = [HardwareType({'name': \
            #                                     'iotlab-node'})]


            #     location = IotlabLocation({'country':'France', 'site': \
            #                                 node['site']})
            #     rspec_node['location'] = location


            #     position = IotlabPosition()
            #     for field in position :
            #         try:
            #             position[field] = node[field]
            #         except KeyError, error :
            #             logger.log_exc("IOTLABAGGREGATE\t get_nodes \
            #                                             position %s "% (error))

            #     rspec_node['position'] = position
            #     #rspec_node['interfaces'] = []

            #     # Granularity
            #     granularity = Granularity({'grain': grain})
            #     rspec_node['granularity'] = granularity
            #     rspec_node['tags'] = []
            #     if node['hostname'] in slivers:
            #         # add sliver info
            #         sliver = slivers[node['hostname']]
            #         rspec_node['sliver_id'] = sliver['sliver_id']
            #         rspec_node['client_id'] = node['hostname']
            #         rspec_node['slivers'] = [sliver]

            #         # slivers always provide the ssh service
            #         login = Login({'authentication': 'ssh-keys', \
            #                 'hostname': node['hostname'], 'port':'22', \
            #                 'username': sliver['name']})
            #         service = Services({'login': login})
            #         rspec_node['services'] = [service]
            #     rspec_nodes.append(rspec_node)

        # return (rspec_nodes)
        return nodes_dict

    def node_to_rspec_node(self, node, grain):
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

    def get_all_leases(self, ldap_username):
        """

        Get list of lease dictionaries which all have the mandatory keys
        ('lease_id', 'hostname', 'site_id', 'name', 'start_time', 'duration').
        All the leases running or scheduled are returned.

        :param ldap_username: if ldap uid is not None, looks for the leases
        belonging to this user.
        :type ldap_username: string
        :returns: rspec lease dictionary with keys lease_id, component_id,
            slice_id, start_time, duration.
        :rtype: dict

        .. note::There is no filtering of leases within a given time frame.
            All the running or scheduled leases are returned. options
            removed SA 15/05/2013


        """

        #now = int(time.time())
        #lease_filter = {'clip': now }

        #if slice_record:
            #lease_filter.update({'name': slice_record['name']})

        #leases = self.driver.testbed_shell.GetLeases(lease_filter)

        logger.debug("IOTLABAGGREGATE  get_all_leases ldap_username %s "
                     % (ldap_username))
        leases = self.driver.testbed_shell.GetLeases(login=ldap_username)
        grain = self.driver.testbed_shell.GetLeaseGranularity()
        # site_ids = []
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

        ldap_username= None
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
            nodes = self.get_nodes(slices, slivers)
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


    def list_resources(self, version = None, options={}):

        version_manager = VersionManager()
        version = version_manager.get_version(version)
        rspec_version = version_manager._get_version(version.type, version.version, 'ad')
        rspec = RSpec(version=rspec_version, user_options=options)

        if not options.get('list_leases') or options['list_leases'] != 'leases':
            # get nodes
            nodes_dict  = self.get_nodes(options)
            # site_ids = []
            # interface_ids = []
            # tag_ids = []
            # nodes_dict = {}
            # for node in nodes:
            #     site_ids.append(node['site_id'])
            #     interface_ids.extend(node['interface_ids'])
            #     tag_ids.extend(node['node_tag_ids'])
            #     nodes_dict[node['node_id']] = node
            # sites = self.get_sites({'site_id': site_ids})
            # interfaces = self.get_interfaces({'interface_id':interface_ids})
            # node_tags = self.get_node_tags({'node_tag_id': tag_ids})
            # pl_initscripts = self.get_pl_initscripts()
            # convert nodes to rspec nodes
            grain = self.driver.testbed_shell.GetLeaseGranularity()
            rspec_nodes = []
            for node_id in nodes_dict:
                node = nodes_dict[node_id]
                # rspec_node = self.node_to_rspec_node(node, sites, interfaces, node_tags, pl_initscripts)
                rspec_node = self.node_to_rspec_node(node, grain)
                rspec_nodes.append(rspec_node)
            rspec.version.add_nodes(rspec_nodes)

            # add links
            # links = self.get_links(sites, nodes_dict, interfaces)
            # rspec.version.add_links(links)

        if not options.get('list_leases') or options.get('list_leases') and options['list_leases'] != 'resources':
           leases = self.get_all_leases()
           rspec.version.add_leases(leases)

        return rspec.toxml()


    def describe(self, urns, version=None, options={}):
        version_manager = VersionManager()
        version = version_manager.get_version(version)
        rspec_version = version_manager._get_version(version.type,
                                                     version.version, 'manifest')
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
        sliver_allocations = self.driver.api.dbsession().query(SliverAllocation).filter(constraint)
        sliver_allocation_dict = {}
        for sliver_allocation in sliver_allocations:
            geni_urn = sliver_allocation.slice_urn
            sliver_allocation_dict[sliver_allocation.sliver_id] = sliver_allocation

        # add slivers
        nodes_dict = {}
        for sliver in slivers:
            nodes_dict[sliver['node_id']] = sliver
        rspec_nodes = []
        for sliver in slivers:
            rspec_node = self.sliver_to_rspec_node(sliver, sliver_allocation_dict)
            rspec_nodes.append(rspec_node)
            geni_sliver = self.rspec_node_to_geni_sliver(rspec_node, sliver_allocation_dict)
            geni_slivers.append(geni_sliver)
        rspec.version.add_nodes(rspec_nodes)

        return {'geni_urn': geni_urn,
                'geni_rspec': rspec.toxml(),
                'geni_slivers': geni_slivers}