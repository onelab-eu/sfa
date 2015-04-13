# -*- coding:utf-8 -*-
""" Shell driver management """

from sfa.util.sfalogging import logger
from iotlabcli import auth
from iotlabcli import rest
from iotlabcli import helpers
from iotlabcli import experiment
from urllib2 import HTTPError


class IotLABShell(object):
    """
    A REST client shell to the Iot-LAB testbed API instance
    """

    def __init__(self):
        user, passwd = auth.get_user_credentials()
        self.api = rest.Api(user, passwd)


    def get_nodes(self):
        """
        Get all OAR nodes
        :returns: nodes with OAR properties
        :rtype: dict

        :Example:
        {"items": [
            {"archi": "a8:at86rf231",
             "mobile": 0,
             "mobility_type": " ",
             "network_address": "a8-53.grenoble.iot-lab.info",
             "site": "paris",
             "state": "Alive",
             "uid": "9856",
             "x": "0.37",
             "y": "5.44",
             "z": "2.33"
            },
            {"archi= ...}
          ]
        {
        """
        logger.warning("iotlashell get_nodes")
        nodes_dict = {}
        try:
            nodes = experiment.info_experiment(self.api)
        except HTTPError as err:
            logger.warning("iotlashell get_nodes error %s" % err.reason)
            return {'error' : err.reason}
        for node in nodes['items']:
            nodes_dict[node['network_address']] = node
        return nodes_dict


    def get_users(self):
        """
        Get all LDAP users
        :returns: users with LDAP attributes
        :rtype: dict

        :Example:
        [{"firstName":"Frederic",
          "lastName":"Saint-marcel",
          "email":"frederic.saint-marcel@inria.fr",
          "structure":"INRIA",
          "city":"Grenoble",
          "country":"France",
          "login":"saintmar",
          sshPublicKeys":["ssh-rsa AAAAB3..."],
          "motivations":"test SFA",
          "validate":true,
          "admin":true,
          "createTimeStamp":"20120911115247Z"},
          {"firstName":"Julien",
           ...
          }
        ]
        """
        logger.warning("iotlashell get_users")
        users_dict = {}
        try:
            users = self.api.method('admin/users')
        except HTTPError as err:
            logger.warning("iotlashell get_users error %s" % err.reason)
            return {'error' : err.reason}
        for user in users:
            users_dict[user['email']] = user
        return users_dict


    def reserve_nodes(self, login, exp_name,
                      nodes_list, start_time, duration):
        """
        Submit a physical experiment (nodes list) and reservation date.
        """
        # pylint:disable=W0212,R0913,E1123
        logger.warning("iotlashell reserve_nodes")
        exp_file = helpers.FilesDict()
        _experiment = experiment._Experiment(exp_name, duration, start_time)
        _experiment.type = 'physical'
        _experiment.nodes = nodes_list
        exp_file['new_exp.json'] = helpers.json_dumps(_experiment)
        try:
            return self.api.method('admin/experiments?user=%s' % login,
                                   'post',
                                   files=exp_file)
        except HTTPError as err:
            logger.warning("iotlashell reserve_nodes error %s" % err.reason)
            return {'error' : err.reason}


    def get_reserved_nodes(self):
        """
        Get all OAR jobs with state Waiting or Running.

        :Example:
        {"total":"1907",
         "items":[
             {"id":9960,
              "resources": ["m3-16.devgrenoble.iot-lab.info",...],
              "duration":"36000",
              "name":"test_sniffer",
              "state":"Running",
              "owner":"saintmar",
              "nb_resources":10,
              "date":1427966468},
              {"id": ...}
         ]
        }
        """
        logger.warning("iotlashell get_reserved_nodes")
        reserved_nodes_dict = {}
        request = 'admin/experiments?state=Running,Waiting'
        try:
            experiments = self.api.method(request)
        except HTTPError as err:
            logger.warning("iotlashell get_reserved_nodes error %s" %
                           err.reason)
            return {'error' : err.reason}
        for exp in experiments['items']:
            # BUG IN OAR REST API : job with reservation didn't return
            # resources attribute list
            # we use another request for finding job resources
            exp_nodes = self.api.method('admin/experiments/%d' % exp['id'])
            exp['resources'] = exp_nodes['nodes']
            reserved_nodes_dict[exp['id']] = exp
        return reserved_nodes_dict


    def add_user(self, slice_user):
        """
        Add LDAP user
        """
        # pylint:disable=E1123
        logger.warning("iotlashell add_user")
        user = {"type" : "SA", # single account creation
                "city" : "To be defined",
                "country" : "To be defined",
                "motivations" : "SFA federation"}
        email = slice_user['email']
        user['email'] = email
        user['sshPublicKey'] = slice_user['keys'][0]
        # ex : onelab.inria
        user['structure'] = slice_user['slice_record']['authority']
        email = (email.split('@'))[0]
        user['firstName'] = email.split('.')[0]
        try:
            user['lastName'] = email.split('.')[1]
        except IndexError:
            user['lastName'] = email.split('.')[0]
        try:
            self.api.method('admin/users', 'post',
                        json=user)
        except HTTPError as err:
            logger.warning("iotlashell add_user error %s" % err.reason)
    