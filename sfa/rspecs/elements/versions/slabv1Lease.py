from sfa.util.sfalogging import logger
from sfa.util.xml import XpathFilter
from sfa.util.xrn import Xrn



#from sfa.rspecs.elements.versions.sfav1PLTag import SFAv1PLTag
#from sfa.rspecs.elements.versions.pgv2Services import PGv2Services
from sfa.rspecs.elements.lease import Lease



class Slabv1Lease:

    @staticmethod
    def add_leases(xml, leases):
        
        network_elems = xml.xpath('//network')
        if len(network_elems) > 0:
            network_elem = network_elems[0]
        elif len(leases) > 0:
            network_urn = Xrn(leases[0]['component_id']).get_authority_urn().split(':')[0]
            network_elem = xml.add_element('network', name = network_urn)
        else:
            network_elem = xml
         
        lease_elems = []       
        for lease in leases:
            lease_fields = ['lease_id', 'component_id', 'slice_id', 'start_time', 'duration']
            lease_elem = network_elem.add_instance('lease', lease, lease_fields)
            lease_elems.append(lease_elem)


    @staticmethod
    def get_leases(xml, filter={}):
        xpath = '//lease%s | //default:lease%s' % (XpathFilter.xpath(filter), XpathFilter.xpath(filter))
        lease_elems = xml.xpath(xpath)
        return Slabv1Lease.get_lease_objs(lease_elems)

    @staticmethod
    def get_lease_objs(lease_elems):
        leases = []
        for lease_elem in lease_elems:
            #get nodes
            node_elems = lease_elem.xpath('./default:node | ./node')
            for node_elem in node_elems:
                 lease = Lease(lease_elem.attrib, lease_elem)
                 lease['slice_id'] = lease_elem.attrib['slice_id']
                 lease['start_time'] = lease_elem.attrib['start_time']
                 lease['duration'] = lease_elem.attrib['duration']
                 lease['component_id'] = node_elem.attrib['component_id']
                 leases.append(lease)

        return leases
