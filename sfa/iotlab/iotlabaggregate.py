# -*- coding:utf-8 -*-
""" aggregate class management """

from sfa.util.xrn import Xrn, hrn_to_urn
from sfa.util.sfatime import utcparse, datetime_to_string
from sfa.util.sfalogging import logger
from sfa.rspecs.rspec import RSpec
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.lease import Lease
from sfa.rspecs.elements.granularity import Granularity
from sfa.rspecs.version_manager import VersionManager
from sfa.rspecs.elements.versions.iotlabv1Node import IotlabPosition
from sfa.rspecs.elements.versions.iotlabv1Node import IotlabNode
from sfa.rspecs.elements.versions.iotlabv1Node import IotlabLocation
from sfa.iotlab.iotlablease import LeaseTable
import time
import datetime

class IotLABAggregate(object):
    """
    SFA aggregate for Iot-LAB testbed
    """

    def __init__(self, driver):
        self.driver = driver


    def leases_to_rspec_leases(self, leases):
        """ Get leases attributes list"""
        rspec_leases = []
        for lease in leases:
            for node in lease['resources']:
                rspec_lease = Lease()
                rspec_lease['lease_id'] = lease['id']
                iotlab_xrn = Xrn('.'.join([self.driver.root_auth,
                              Xrn.escape(node)]),
                              type='node')
                rspec_lease['component_id'] = iotlab_xrn.urn
                rspec_lease['start_time'] = str(lease['date'])
                duration = int(lease['duration'])/60 # duration in minutes
                rspec_lease['duration'] = duration
                rspec_lease['slice_id'] = lease['slice_id']
                rspec_leases.append(rspec_lease)
        return rspec_leases


    def node_to_rspec_node(self, node):
        """ Get node attributes """
        rspec_node = IotlabNode()
        rspec_node['mobile'] = node['mobile']
        rspec_node['archi'] = node['archi']
        rspec_node['radio'] = (node['archi'].split(':'))[1]
        iotlab_xrn = Xrn('.'.join([self.driver.root_auth,
                              Xrn.escape(node['network_address'])]),
                              type='node')
        rspec_node['boot_state'] = 'true'
        rspec_node['component_id'] = iotlab_xrn.urn
        rspec_node['component_name'] = node['network_address']
        rspec_node['component_manager_id'] = \
                        hrn_to_urn(self.driver.root_auth,
                        'authority+sa')
        rspec_node['authority_id'] = rspec_node['component_manager_id']
        rspec_node['exclusive'] = 'true'
        rspec_node['hardware_types'] = [HardwareType({'name': \
                                        'iotlab-node'})]
        location = IotlabLocation({'country':'France', 'site': \
                                    node['site']})
        rspec_node['location'] = location
        position = IotlabPosition()
        for field in position:
            position[field] = node[field]
        granularity = Granularity({'grain': 30})
        rspec_node['granularity'] = granularity
        rspec_node['tags'] = []
        return rspec_node


    def sliver_to_rspec_node(self, sliver):
        """ Get node and sliver attributes """
        rspec_node = self.node_to_rspec_node(sliver)
        rspec_node['expires'] = datetime_to_string(utcparse(sliver['expires']))
        rspec_node['sliver_id'] = sliver['sliver_id']
        return rspec_node


    @classmethod
    def rspec_node_to_geni_sliver(cls, rspec_node):
        """ Get sliver status """
        geni_sliver = {'geni_sliver_urn': rspec_node['sliver_id'],
                       'geni_expires': rspec_node['expires'],
                       'geni_allocation_status' : 'geni_allocated',
                       'geni_operational_status': 'geni_pending_allocation',
                       'geni_error': '',
                       }
        return geni_sliver


    def list_resources(self, version=None, options=None):
        """
        list_resources method sends a RSpec with all Iot-LAB testbed nodes
        and leases (OAR job submission). For leases we get all OAR jobs with
        state Waiting or Running. If we have an entry in SFA database
        (lease table) with OAR job id this submission was launched by SFA
        driver, otherwise it was launched by Iot-LAB Webportal or CLI-tools

        :Example:
        <rspec>
        ...
        <node component_manager_id="urn:publicid:IDN+iotlab+authority+sa"
              component_id=
                  "urn:publicid:IDN+iotlab+node+m3-10.devgrenoble.iot-lab.info"
              exclusive="true" component_name="m3-10.devgrenoble.iot-lab.info">
            <hardware_type name="iotlab-node"/>
            <location country="France"/>
            <granularity grain="60"/>
            ...
        </node>
        ...
        <lease slice_id="urn:publicid:IDN+onelab:inria+slice+test_iotlab"
            start_time="1427792400" duration="30">
            <node component_id=
                "urn:publicid:IDN+iotlab+node+m3-10.grenoble.iot-lab.info"/>
        </lease>
        ...
        </rspec>
        """
        # pylint:disable=R0914,W0212
        logger.warning("iotlabaggregate list_resources")
        logger.warning("iotlabaggregate list_resources options %s" % options)
        if not options:
            options = {}

        version_manager = VersionManager()
        version = version_manager.get_version(version)
        rspec_version = version_manager._get_version(version.type,
                                                     version.version,
                                                     'ad')
        rspec = RSpec(version=rspec_version, user_options=options)

        nodes = self.driver.shell.get_nodes()
        reserved_nodes = self.driver.shell.get_reserved_nodes()
        if not 'error' in nodes and not 'error' in reserved_nodes:
            # convert nodes to rspec nodes
            rspec_nodes = []
            for node in nodes:
                rspec_node = self.node_to_rspec_node(nodes[node])
                rspec_nodes.append(rspec_node)
            rspec.version.add_nodes(rspec_nodes)

            leases = []
            db_leases = {}
            # find OAR jobs id for all slices in SFA database
            for lease in self.driver.api.dbsession().query(LeaseTable).all():
                db_leases[lease.job_id] = lease.slice_hrn

            for lease_id in reserved_nodes:
                # onelab slice = job submission from OneLAB
                if lease_id in db_leases:
                    reserved_nodes[lease_id]['slice_id'] = \
                        hrn_to_urn(db_leases[lease_id],
                                   'slice')
                # iotlab slice = job submission from Iot-LAB
                else:
                    reserved_nodes[lease_id]['slice_id'] = \
                        hrn_to_urn(self.driver.root_auth+'.'+
                                   reserved_nodes[lease_id]['owner']+"_slice",
                                   'slice')
                leases.append(reserved_nodes[lease_id])

            rspec_leases = self.leases_to_rspec_leases(leases)
            logger.warning("iotlabaggregate list_resources rspec_leases  %s" %
                           rspec_leases)
            rspec.version.add_leases(rspec_leases)
        return rspec.toxml()


    def get_slivers(self, urns, leases, nodes):
        """ Get slivers attributes list """
        logger.warning("iotlabaggregate get_slivers")
        logger.warning("iotlabaggregate get_slivers urns %s" % urns)
        slivers = []
        for lease in leases:
            for node in lease['resources']:
                sliver_node = nodes[node]
                sliver_hrn = '%s.%s-%s' % (self.driver.hrn,
                             lease['id'], node.split(".")[0])
                start_time = datetime.datetime.fromtimestamp(lease['date'])
                duration = datetime.timedelta(seconds=int(lease['duration']))
                sliver_node['expires'] = start_time + duration
                sliver_node['sliver_id'] = Xrn(sliver_hrn,
                                               type='sliver').urn
                slivers.append(sliver_node)
        return slivers


    def _delete_db_lease(self, job_id):
        """ Delete lease table row in SFA database """
        logger.warning("iotlabdriver _delete_db_lease lease job_id : %s"
                       % job_id)
        self.driver.api.dbsession().query(LeaseTable).filter(
            LeaseTable.job_id == job_id).delete()
        self.driver.api.dbsession().commit()


    def describe(self, urns, version=None, options=None):
        """
        describe method returns slice slivers (allocated resources) and leases
        (OAR job submission). We search in lease table of SFA database all OAR
        jobs id for this slice and match OAR jobs with state Waiting or Running.
        If OAR job id doesn't exist the experiment is terminated and we delete
        the database table entry. Otherwise we add slivers and leases in the
        response

        :returns:
            geni_slivers : a list of allocated slivers with information about
                           their allocation and operational state
            geni_urn : the URN of the slice in which the sliver has been
                       allocated
            geni_rspec:  a RSpec describing the allocated slivers and leases
        :rtype: dict

        :Example:
        <rspec>
        ...
        <node component_manager_id="urn:publicid:IDN+iotlab+authority+sa"
              component_id=
                  "urn:publicid:IDN+iotlab+node+m3-10.grenoble.iot-lab.info"
              client_id="m3-10.grenoble.iot-lab.info"
              sliver_id="urn:publicid:IDN+iotlab+sliver+9953-m3-10"
              exclusive="true" component_name="m3-10.grenoble.iot-lab.info">
            <hardware_type name="iotlab-node"/>
            <location country="France"/>
            <granularity grain="30"/>
            <sliver_type name="iotlab-exclusive"/>
        </node>
        <lease slice_id="urn:publicid:IDN+onelab:inria+slice+test_iotlab"
               start_time="1427792428" duration="29">
            <node component_id=
                "urn:publicid:IDN+iotlab+node+m3-10.grenoble.iot-lab.info"/>
        </lease>
        ...
        </rspec>

        """
        # pylint:disable=R0914,W0212
        logger.warning("iotlabaggregate describe")
        logger.warning("iotlabaggregate describe urns : %s" % urns)
        if not options:
            options = {}
        version_manager = VersionManager()
        version = version_manager.get_version(version)
        rspec_version = version_manager._get_version(version.type,
                                                     version.version,
                                                     'manifest')
        rspec = RSpec(version=rspec_version, user_options=options)
        xrn = Xrn(urns[0])
        geni_slivers = []

        nodes = self.driver.shell.get_nodes()
        reserved_nodes = self.driver.shell.get_reserved_nodes()
        if not 'error' in nodes and not 'error' in reserved_nodes:
            # find OAR jobs id for one slice in SFA database
            db_leases = [(lease.job_id, lease.slice_hrn)
                         for lease in self.driver.api.dbsession()
                         .query(LeaseTable)
                         .filter(LeaseTable.slice_hrn == xrn.hrn).all()]

            leases = []
            for job_id, slice_hrn in db_leases:
                # OAR job terminated, we delete entry in database
                if not job_id in reserved_nodes:
                    self._delete_db_lease(job_id)
                else:
                    # onelab slice = job submission from OneLAB
                    lease = reserved_nodes[job_id]
                    lease['slice_id'] = hrn_to_urn(slice_hrn, 'slice')
                    leases.append(lease)

            # get slivers
            slivers = self.get_slivers(urns, leases, nodes)
            if slivers:
                date = utcparse(slivers[0]['expires'])
                rspec_expires = datetime_to_string(date)
            else:
                rspec_expires = datetime_to_string(utcparse(time.time()))
            rspec.xml.set('expires', rspec_expires)

            rspec_nodes = []

            for sliver in slivers:
                rspec_node = self.sliver_to_rspec_node(sliver)
                rspec_nodes.append(rspec_node)
                geni_sliver = self.rspec_node_to_geni_sliver(rspec_node)
                geni_slivers.append(geni_sliver)
            logger.warning("iotlabaggregate describe geni_slivers %s" %
                           geni_slivers)
            rspec.version.add_nodes(rspec_nodes)

            rspec_leases = self.leases_to_rspec_leases(leases)
            logger.warning("iotlabaggregate describe rspec_leases %s" %
                           rspec_leases)
            rspec.version.add_leases(rspec_leases)

        return {'geni_urn': urns[0],
                'geni_rspec': rspec.toxml(),
                'geni_slivers': geni_slivers}

