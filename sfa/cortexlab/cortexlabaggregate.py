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
from sfa.rspecs.elements.services import Services
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.lease import Lease
from sfa.rspecs.elements.granularity import Granularity
from sfa.rspecs.version_manager import VersionManager

from sfa.rspecs.elements.versions.iotlabv1Node import IotlabPosition, \
    IotlabNode, IotlabLocation, IotlabMobility

from sfa.util.sfalogging import logger
from sfa.util.xrn import Xrn


def cortexlab_xrn_to_hostname(xrn):
    """Returns a node's hostname from its xrn.
    :param xrn: The nodes xrn identifier.
    :type xrn: Xrn (from sfa.util.xrn)

    :returns: node's hostname.
    :rtype: string

    """
    return Xrn.unescape(Xrn(xrn=xrn, type='node').get_leaf())


def cortexlab_xrn_object(root_auth, hostname):
    """Creates a valid xrn object from the node's hostname and the authority
    of the SFA server.

    :param hostname: the node's hostname.
    :param root_auth: the SFA root authority.
    :type hostname: string
    :type root_auth: string

    :returns: the cortexlab node's xrn
    :rtype: Xrn

    """
    return Xrn('.'.join([root_auth, Xrn.escape(hostname)]), type='node')


class CortexlabAggregate:
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
        Get the slices and the associated leases if any, from the cortexlab
            testbed. One slice can have mutliple leases.
            For each slice, get the nodes in the  associated lease
            and create a sliver with the necessary info and insert it into the
            sliver dictionary, keyed on the node hostnames.
            Returns a dict of slivers based on the sliver's node_id.
            Called by get_rspec.


        :param slice_xrn: xrn of the slice
        :param login: user's login on cortexlab ldap

        :type slice_xrn: string
        :type login: string
        :returns: a list of slices dict and a list of Sliver object
        :rtype: (list, list)

        .. note: There is no real slivers in cortexlab, only leases. The goal
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
            logger.log_exc("CORTEXLABAGGREGATE \t \
                        get_slice_and_slivers No nodes in the slice \
                        - KeyError ")
            node_ids_list = []
            # continue

        for node in node_ids_list:
            sliver_xrn = Xrn(slice_urn, type='sliver', id=node)
            sliver_xrn.set_authority(self.driver.hrn)
            sliver = Sliver({'sliver_id': sliver_xrn.urn,
                            'name': sfa_slice['hrn'],
                            'type': 'cortexlab-node',
                            'tags': []})

            slivers[node] = sliver

        #Add default sliver attribute :
        #connection information for cortexlab, assuming it is the same ssh
        # connection process
         # look in ldap:
        ldap_username = self.find_ldap_username_from_slice(sfa_slice)

        if ldap_username is not None:
            ssh_access = None
            slivers['default_sliver'] = {'ssh': ssh_access,
                                             'login': ldap_username}


        logger.debug("CORTEXLABAGGREGATE api get_slice_and_slivers  slivers %s "
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
        slice_nodes_list = []
        if slices is not None:
            for one_slice in slices:
                try:
                    slice_nodes_list = one_slice['node_ids']
                     # if we are dealing with a slice that has no node just
                     # return an empty list. In cortexlab a slice can have multiple
                     # jobs scheduled, so it either has at least one lease or
                     # not at all.
                except KeyError:
                    return []

        # get the granularity in second for the reservation system
        grain = self.driver.testbed_shell.GetLeaseGranularity()

        nodes = self.driver.testbed_shell.GetNodes()

        nodes_dict = {}

        #if slices, this means we got to list all the nodes given to this slice
        # Make a list of all the nodes in the slice before getting their
        #attributes
        rspec_nodes = []

        logger.debug("CortexlabAggregate api get_nodes slices  %s "
                     % (slices))

        reserved_nodes = self.driver.testbed_shell.GetNodesCurrentlyInUse()
        logger.debug("CortexlabAggregate api get_nodes slice_nodes_list  %s "
                     % (slice_nodes_list))
        for node in nodes:
            nodes_dict[node['node_id']] = node
            if slice_nodes_list == [] or node['hostname'] in slice_nodes_list:

                rspec_node = Node()



                cortexlab_xrn = cortexlab_xrn_object(self.driver.testbed_shell.root_auth,
                                               node['hostname'])
                rspec_node['component_id'] = cortexlab_xrn.urn
                rspec_node['component_name'] = node['hostname']
                rspec_node['component_manager_id'] = \
                                hrn_to_urn(self.driver.testbed_shell.root_auth,
                                'authority+sa')

                # Iotlab's nodes are federated : there is only one authority
                # for all Iotlab sites, registered in SFA.
                # Removing the part including the site
                # in authority_id SA 27/07/12
                rspec_node['authority_id'] = rspec_node['component_manager_id']


                # boot state removed if you need it uncomment
                # rspec_node['boot_state'] = node['boot_state']
                # if node['hostname'] in reserved_nodes:
                #     rspec_node['boot_state'] = "Reserved"

                rspec_node['exclusive'] = 'true'
                rspec_node['hardware_types'] = [HardwareType({'name':
                                               'cortexlab-node'})]


                # Location, mobility and position removed. If you need it go check
                # get_nodes in iotlabaggregate.py

                # Granularity
                granularity = Granularity({'grain': grain})
                rspec_node['granularity'] = granularity
                rspec_node['tags'] = []
                if node['hostname'] in slivers:
                    # add sliver info
                    sliver = slivers[node['hostname']]
                    rspec_node['sliver_id'] = sliver['sliver_id']
                    rspec_node['client_id'] = node['hostname']
                    rspec_node['slivers'] = [sliver]

                    # slivers always provide the ssh service
                    login = Login({'authentication': 'ssh-keys',
                                   'hostname': node['hostname'], 'port': '22',
                                   'username': sliver['name']})
                    service = Services({'login': login})
                    rspec_node['services'] = [service]
                rspec_nodes.append(rspec_node)

        return (rspec_nodes)

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



        logger.debug("CortexlabAggregate  get_all_leases ldap_username %s "
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

                cortexlab_xrn = cortexlab_xrn_object(
                    self.driver.testbed_shell.root_auth, node)
                rspec_lease['component_id'] = cortexlab_xrn.urn
                #rspec_lease['component_id'] = hostname_to_urn(self.driver.hrn,\
                                        #site, node['hostname'])
                try:
                    rspec_lease['slice_id'] = lease['slice_id']
                except KeyError:
                    #No info on the slice used in cortexlab_xp table
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
        :param login: user'uid (ldap login) on cortexlab
        :type login: string
        :param version: can be set to sfa or cortexlab
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
        logger.debug("CortexlabAggregate \t get_rspec ***version %s \
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
            logger.debug("CortexlabAggregate \tget_rspec **** \
                    LDAP USERNAME %s \r\n" \
                    % (ldap_username))
        #at this point sliver may be empty if no cortexlab job
        #is running for this user/slice.
        rspec = RSpec(version=rspec_version, user_options=options)

        logger.debug("\r\n \r\n CortexlabAggregate \tget_rspec *** \
                      slice_xrn %s slices  %s\r\n \r\n"
                     % (slice_xrn, slices))

        if options is not None and 'list_leases' in options:
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
            if slice_xrn and slices is None:
              nodes = []
            logger.debug("\r\n")
            logger.debug("CortexlabAggregate \t lease_option %s \
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

                logger.debug("CortexlabAggregate \tget_rspec **** \
                        version type %s ldap_ user %s \r\n" \
                        % (version.type, ldap_username))
                if version.type == "Iotlab":
                    rspec.version.add_connection_information(
                        ldap_username, sites_set)

            default_sliver = slivers.get('default_sliver', [])
            if default_sliver and len(nodes) is not 0:
                #default_sliver_attribs = default_sliver.get('tags', [])
                logger.debug("CortexlabAggregate \tget_rspec **** \
                        default_sliver%s \r\n" % (default_sliver))
                for attrib in default_sliver:
                    rspec.version.add_default_sliver_attribute(
                        attrib, default_sliver[attrib])

        if lease_option in ['all','leases']:
            leases = self.get_all_leases(ldap_username)
            rspec.version.add_leases(leases)
            logger.debug("CortexlabAggregate \tget_rspec **** \
                       FINAL RSPEC %s \r\n" % (rspec.toxml()))
        return rspec.toxml()
