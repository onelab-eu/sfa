"""
File used to handle all the nodes querying:
* get nodes list along with their properties with get_all_nodes

* get sites and their properties with get_sites.

* get nodes involved in leases sorted by lease id, with get_reserved_nodes.

* create a lease (schedule an experiment) with schedule_experiment.

* delete a lease with delete_experiment.

"""

class CortexlabQueryNodes:
    def __init__(self):

        pass

    def get_all_nodes(self, node_filter_dict=None, return_fields_list=None):
        """
        Get all the nodes and their properties. Called by GetNodes.
        Filtering on nodes properties can be done here or in GetNodes.
        Search for specific nodes if some filters are specified. Returns all
        the nodes properties if return_fields_list is None.


        :param node_filter_dict: dictionary of lists with node properties. For
            instance, if you want to look for a specific node with its hrn,
            the node_filter_dict should be {'hrn': [hrn_of_the_node]}
        :type node_filter_dict: dict
        :param return_fields_list: list of specific fields the user wants to be
            returned.
        :type return_fields_list: list
        :returns: list of dictionaries with node properties
        :rtype: list

        TODO: Define which properties have to be listed here. Useful ones:
        node architecture, radio type, position (x,y,z)
        """
        node_dict_list = None
        # Get the nodes here, eventually filter here
        # See iotlabapi.py GetNodes to get the filtering (node_filter_dict and
        # return_fields_list ) part, if necessary
        # Format used in iotlab
        node_dict_list = [
        {'hrn': 'iotlab.wsn430-11.devlille.iot-lab.info',
        'archi': 'wsn430', 'mobile': 'True',
        'hostname': 'wsn430-11.devlille.iot-lab.info',
         'site': 'devlille', 'mobility_type': 'None',
         'boot_state': 'Suspected',
         'node_id': 'wsn430-11.devlille.iot-lab.info',
         'radio': 'cc2420', 'posx': '2.3', 'posy': '2.3',
         'node_number': 11, 'posz': '1'},
         {'hrn': 'iotlab.wsn430-10.devlille.iot-lab.info',
         'archi': 'wsn430', 'mobile': 'True',
         'hostname': 'wsn430-10.devlille.iot-lab.info',
         'site': 'devlille', 'mobility_type': 'None',
         'boot_state': 'Alive', 'node_id': 'wsn430-10.devlille.iot-lab.info',
         'radio': 'cc2420', 'posx': '1.3', 'posy': '2.3', 'node_number': 10,
         'posz': '1'},
         {'hrn': 'iotlab.wsn430-1.devlille.iot-lab.info',
         'archi': 'wsn430', 'mobile': 'False',
         'hostname': 'wsn430-1.devlille.iot-lab.info',
         'site': 'devlille', 'mobility_type': 'None',
         'boot_state': 'Alive', 'node_id': 'wsn430-1.devlille.iot-lab.info',
         'radio': 'cc2420', 'posx': '0.3', 'posy': '0.3', 'node_number': 1,
         'posz': '1'} ]
        return node_dict_list




    def get_sites(self, site_filter_name_list=None, return_fields_list=None):

        """Get the different cortexlab sites and for each sites, the nodes
        hostnames on this site.

       	:param site_filter_name_list: used to specify specific sites
        :param return_fields_list: fields that has to be returned
        :type site_filter_name_list: list
        :type return_fields_list: list
        :rtype: list of dictionaries
        """
        site_dict_list = None
        site_dict_list = [
        {'address_ids': [], 'slice_ids': [], 'name': 'iotlab',
        'node_ids': [u'wsn430-11.devlille.iot-lab.info',
        u'wsn430-10.devlille.iot-lab.info', u'wsn430-1.devlille.iot-lab.info'],
        'url': 'https://portal.senslab.info', 'person_ids': [],
        'site_tag_ids': [], 'enabled': True, 'site': 'devlille',
        'longitude': '- 2.10336', 'pcu_ids': [], 'max_slivers': None,
        'max_slices': None, 'ext_consortium_id': None, 'date_created': None,
        'latitude': '48.83726', 'is_public': True, 'peer_site_id': None,
        'peer_id': None, 'abbreviated_name': 'iotlab'}]
        # list of dict with mandatory keys  ['name', 'node_ids', 'longitude',
        # 'site' ]. Value for key node_ids is a hostname list.
        # See iotlabapi.py GetSites to get the filtering
        return site_dict_list


    def get_reserved_nodes(self, username):
        """Get list of leases. Get the leases for the username if specified,
        otherwise get all the leases.
        :param username: user's LDAP login
        :type username: string
        :returns: list of reservations dict
        :rtype: list of dictionaries

        """
        reserved_nodes_list_dict = None

        reserved_nodes_list_dict = [{'lease_id': 1658,
        'reserved_nodes': [ 'wsn430-11.devlille.iot-lab.info'], 'state':
        'Waiting', 'user': 'avakian', 'resource_ids': [11],
        't_from': 1412938800, 't_until': 1412942640}]

        return reserved_nodes_list_dict

    def schedule_experiment(self, lease_dict):
        """Schedule/ run an experiment based on the information provided in the
        lease dictionary.

        :param lease_dict: contains  lease_start_time, lease_duration,
            added_nodes, slice_name , slice_user, grain:
        :type lease_dict: dictionary
        :rtype: dict
        """
        answer = {}
        answer['id'] = None #experiment id
        answer['msg'] = None #message in case of error


        answer['id'] = 1659

        # Launch the experiment here

        return answer

    def delete_experiment(self, experiment_id, username):
        """
        Delete the experiment designated by its experiment id and its
        user.
        TODO: If the username is not necessary to delete the lease, then you can
        remove it from the parameters, given that you propagate the changes

        :param experiment_id: experiment identifier
        :type experiment_id : integer
        :param username: user's LDAP login
        :type experiment_id: integer
        :type username: string
        :returns: dict with delete status {'status': True of False}
        :rtype: dict
        """
        # Delete the experiment here. Ret['status'] should be True or False
        # depending if the delete was effective or not.
        ret = {}
        ret['status'] = None
        return ret
