# -*- coding:utf-8 -*-
""" driver class management """

from sfa.util.sfalogging import logger
from sfa.util.xrn import Xrn, urn_to_hrn
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.rspec import RSpec
from sfa.managers.driver import Driver
from sfa.iotlab.iotlabshell import IotLABShell
from sfa.iotlab.iotlabaggregate import IotLABAggregate
from sfa.iotlab.iotlablease import LeaseTable

class IotLabDriver(Driver):
    """
    SFA driver for Iot-LAB testbed
    """

    def __init__(self, api):
        Driver.__init__(self, api)
        config = api.config
        self.api = api
        self.root_auth = config.SFA_REGISTRY_ROOT_AUTH
        self.shell = IotLABShell()
        # need by sfa driver
        self.cache = None

    def check_sliver_credentials(self, creds, urns):
        """ Not used and need by SFA """
        pass

    ########################################
    ########## registry oriented
    ########################################

    ##########
    def register(self, sfa_record, hrn, pub_key):
        logger.warning("iotlabdriver register : not implemented")
        return -1


    ##########
    def update(self, old_sfa_record, new_sfa_record, hrn, new_key):
        logger.warning("iotlabdriver update : not implemented")
        return True


    ##########
    def remove(self, sfa_record):
        logger.warning("iotlabdriver remove : not implemented")
        return True


    ########################################
    ########## aggregate oriented
    ########################################

    def provision(self, urns, options=None):
        logger.warning("iotlabdriver provision : not implemented")
        version_manager = VersionManager()
        opt = options['geni_rspec_version']
        rspec_version = version_manager.get_version(opt)
        return self.describe(urns, rspec_version, options=options)


    def delete(self, urns, options=None):
        logger.warning("iotlabdriver delete : not implemented")
        geni_slivers = []
        return geni_slivers


    def aggregate_version(self):
        logger.warning("iotlabdriver aggregate_version")
        version_manager = VersionManager()
        ad_rspec_versions = []
        request_rspec_versions = []
        for rspec_version in version_manager.versions:
            if rspec_version.content_type in ['*', 'ad']:
                ad_rspec_versions.append(rspec_version.to_dict())
            if rspec_version.content_type in ['*', 'request']:
                request_rspec_versions.append(rspec_version.to_dict())
        return {
            'testbed': self.hrn,
            'geni_request_rspec_versions': request_rspec_versions,
            'geni_ad_rspec_versions': ad_rspec_versions}


    def list_resources(self, version=None, options=None):
        logger.warning("iotlabdriver list_resources")
        if not options:
            options = {}
        aggregate = IotLABAggregate(self)
        rspec = aggregate.list_resources(version=version, options=options)
        return rspec


    def describe(self, urns, version, options=None):
        logger.warning("iotlabdriver describe")
        if not options:
            options = {}
        aggregate = IotLABAggregate(self)
        return aggregate.describe(urns, version=version, options=options)


    def status(self, urns, options=None):
        logger.warning("iotlabdriver status")
        aggregate = IotLABAggregate(self)
        desc = aggregate.describe(urns, version='GENI 3')
        status = {'geni_urn': desc['geni_urn'],
                  'geni_slivers': desc['geni_slivers']}
        return status


    def _get_users(self):
        """ Get all users """
        ret = self.shell.get_users()
        if 'error' in ret:
            return None
        return ret


    def _get_user_login(self, caller_user):
        """ Get user login with email """
        email = caller_user['email']
        # ensure user exist in LDAP tree
        users = self._get_users()
        if users and not email in users:
            self.shell.add_user(caller_user)
            users = self._get_users()
        if users and email in users:
            return users[email]['login']
        else:
            return None


    @classmethod
    def _get_experiment(cls, rspec):
        """
        Find in RSpec leases the experiment start time, duration and nodes list.

        :Example:
        <rspec>
        ...
        <lease slice_id="urn:publicid:IDN+onelab:inria+slice+test_iotlab"
                start_time="1427792400" duration="30">
            <node component_id=
                "urn:publicid:IDN+iotlab+node+m3-10.grenoble.iot-lab.info"/>
        </lease>
        <lease slice_id="urn:publicid:IDN+onelab:inria+slice+test_iotlab"
                start_time="1427792600" duration="50">
            <node component_id=
                "urn:publicid:IDN+iotlab+node+m3-15.grenoble.iot-lab.info"/>
        </lease>
        ...
        </rspec>
        """
        leases = rspec.version.get_leases()
        start_time = min([int(lease['start_time'])
                         for lease in leases])
        end_time = max([int(lease['start_time']) +
                       int(lease['duration'])*60
                       for lease in leases])
        nodes_list = [Xrn.unescape(Xrn(lease['component_id'].strip(),
                      type='node').get_leaf())
                      for lease in leases]
        # uniq hostnames
        nodes_list = list(set(nodes_list))
        from math import floor
        duration = floor((end_time - start_time)/60) # minutes
        return nodes_list, start_time, duration


    def _save_db_lease(self, job_id, slice_hrn):
        """ Save lease table row in SFA database """
        lease_row = LeaseTable(job_id,
                               slice_hrn)
        logger.warning("iotlabdriver _save_db_lease lease row : %s" %
                       lease_row)
        self.api.dbsession().add(lease_row)
        self.api.dbsession().commit()


    def allocate(self, urn, rspec_string, expiration, options=None):
        """
        Allocate method submit an experiment on Iot-LAB testbed with :
            * user : get the slice user which launch request (caller_hrn)
            * reservation : get the start time and duration in RSpec leases
            * nodes : get the nodes list in RSpec leases
        If we have a request success on Iot-LAB testbed we store in SFA
        database the assocation OAR scheduler job id and slice hrn

        :param urn : slice urn
        :param rspec_string : RSpec received
        :param options : options with slice users (geni_users)
        """
        # pylint:disable=R0914

        logger.warning("iotlabdriver allocate")
        xrn = Xrn(urn)
        aggregate = IotLABAggregate(self)
        # parse rspec
        rspec = RSpec(rspec_string)

        caller_hrn = options.get('actual_caller_hrn', [])
        geni_users = options.get('geni_users', [])
        caller_user = [user for user in geni_users if
                       urn_to_hrn(user['urn'])[0] == caller_hrn][0]
        logger.warning("iotlabdriver allocate caller : %s" %
                       caller_user['email'])

        login = self._get_user_login(caller_user)
        # only if we have a user
        if login:
            nodes_list, start_time, duration = \
                self._get_experiment(rspec)
            logger.warning("iotlabdriver allocate submit OAR job :"
                           " %s %s %s %s" %
                           (xrn.hrn, start_time, duration, nodes_list))
            # [0-9A-Za-z_] with onelab.inria.test_iotlab
            exp_name = '_'.join((xrn.hrn).split('.'))
            # submit OAR job
            ret = self.shell.reserve_nodes(login,
                                           exp_name,
                                           nodes_list,
                                           start_time,
                                           duration)

            # in case of job submission success save slice and lease job
            # id association in database
            if 'id' in ret:
                self._save_db_lease(int(ret['id']),
                                    xrn.hrn)

        return aggregate.describe([xrn.get_urn()], version=rspec.version)
