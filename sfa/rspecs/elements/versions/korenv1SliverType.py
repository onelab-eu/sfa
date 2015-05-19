from sfa.rspecs.elements.element import Element
from sfa.rspecs.elements.openstack import *

#from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.elements.versions.pgv2DiskImage import PGv2DiskImage
from sfa.rspecs.elements.versions.plosv1FWRule import PLOSv1FWRule

class Korenv1SliverType:

    @staticmethod
    def add_slivers(xml, slivers):
        if not slivers:
            return 
        if not isinstance(slivers, list):
            slivers = [slivers]
        for sliver in slivers:
            sliver_elem = xml.add_element('{%s}sliver' % xml.namespaces['openstack'])
            attrs = ['component_id', 'sliver_id', 'sliver_type']
            for attr in attrs:
                if sliver.get(attr):
                    sliver_elem.set(attr, sliver[attr])
            
            flavor = sliver['flavor']
            if flavor and isinstance(flavor, dict):
                sub_sliver_elem = sliver_elem.add_instance('{%s}flavor' % xml.namespaces['openstack'], \
                                                           flavor, OSFlavor.fields)

            images = sliver['images']
            if images and isinstance(images, list):
                for image in images:
                    # Check if the minimum quotas requested is suitable or not
                    if image['minRam'] <= sub_sliver_elem.attrib['ram'] and \
                       image['minDisk'] <= sub_sliver_elem.attrib['storage']:
                        sub_sliver_elem.add_instance('{%s}image' % xml.namespaces['openstack'], \
                                                     image, OSImage.fields)
            """
            sliver_elem = xml.add_element('sliver_type')
            if sliver.get('type'):
                sliver_elem.set('name', sliver['type'])
            attrs = ['client_id', 'cpus', 'memory', 'storage']
            for attr in attrs:
                if sliver.get(attr):
                    sliver_elem.set(attr, sliver[attr])
            
            images = sliver.get('disk_image')
            if images and isinstance(images, list):
                PGv2DiskImage.add_images(sliver_elem, images)      
            fw_rules = sliver.get('fw_rules')
            if fw_rules and isinstance(fw_rules, list):
                PLOSv1FWRule.add_rules(sliver_elem, fw_rules)
            PGv2SliverType.add_sliver_attributes(sliver_elem, sliver.get('tags', []))
            """

    @staticmethod
    def get_os_slivers(xml, filter=None):
        if filter is None: filter={}
        xpath = './sliver | ./openstack:sliver'
        sliver_elems = xml.xpath(xpath)
        slivers = []
        for sliver_elem in sliver_elems:
            sliver = OSSliver(sliver_elem.attrib, sliver_elem)
            # cwkim: Get info. of the sliver
#            sliver['params'] = Korenv1SliverType.get_os_sliver_attributes(sliver_elem)
            slivers.append(sliver)
        return slivers
    
    @staticmethod
    def get_os_sliver_attributes(xml, filter=None):
        if filter is None: filter={}
        sliver_params = OSSliverParams()
        for sliver_param in xml.iter():
            tag = sliver_param.tag.split('}')[-1]
            elem = sliver_param.attrib
            if sliver_params.has_key(tag):
                sliver_params[tag] = elem
        return sliver_params

    @staticmethod
    def get_sliver_attributes(xml, filter=None):
        if filter is None: filter={}
        return []             
