from sfa.util.xrn import Xrn
from sfa.util.xml import XpathFilter
from sfa.util.sfatime import utcparse, datetime_to_string, datetime_to_epoch

from sfa.rspecs.elements.node import NodeElement
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.location import Location
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.disk_image import DiskImage
from sfa.rspecs.elements.interface import Interface
from sfa.rspecs.elements.bwlimit import BWlimit
from sfa.rspecs.elements.pltag import PLTag
from sfa.rspecs.elements.versions.pgv2Services import PGv2Services     
from sfa.rspecs.elements.versions.pgv2SliverType import PGv2SliverType     
from sfa.rspecs.elements.versions.pgv2Interface import PGv2Interface     
from sfa.rspecs.elements.lease import Lease


class PGv2Lease:
    @staticmethod
    def add_leases(xml, leases):
        # group the leases by slice and timeslots
        grouped_leases = []

        while leases:
             slice_id = leases[0]['slice_id']
             start_time = leases[0]['start_time']
             duration = leases[0]['duration']
             group = []

             for lease in leases:
                  if slice_id == lease['slice_id'] and start_time == lease['start_time'] and duration == lease['duration']:
                      group.append(lease)

             grouped_leases.append(group)

             for lease1 in group:
                  leases.remove(lease1)

        lease_elems = []
        for lease in grouped_leases:
            #lease[0]['start_time'] = datetime_to_string(utcparse(lease[0]['start_time']))

            lease_fields = ['slice_id', 'start_time', 'duration']
            lease_elem = xml.add_instance('lease', lease[0], lease_fields)
            lease_elems.append(lease_elem)

            # add nodes of this lease
            for node in lease:
                 lease_elem.add_instance('node', node, ['component_id'])


    @staticmethod
    def get_leases(xml, filter=None):
        if filter is None: filter={}
        xpath = '//lease%s | //default:lease%s' % (XpathFilter.xpath(filter), XpathFilter.xpath(filter))
        lease_elems = xml.xpath(xpath)
        return PGv2Lease.get_lease_objs(lease_elems)


    @staticmethod
    def get_lease_objs(lease_elems):
        leases = []
        for lease_elem in lease_elems:
            #get nodes
            node_elems = lease_elem.xpath('./default:node | ./node')
            for node_elem in node_elems:
                 lease = Lease(lease_elem.attrib, lease_elem)
                 lease['slice_id'] = lease_elem.attrib['slice_id']
                 #lease['start_time'] = datetime_to_epoch(utcparse(lease_elem.attrib['start_time']))
                 lease['start_time'] = lease_elem.attrib['start_time']
                 lease['duration'] = lease_elem.attrib['duration']
                 lease['component_id'] = node_elem.attrib['component_id']
                 leases.append(lease)

        return leases
