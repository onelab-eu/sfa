from sfa.rspecs.elements.element import Element
from sfa.rspecs.elements.openstack import *
from sfa.util.sfalogging import logger

#from sfa.rspecs.elements.sliver import Sliver
#from sfa.rspecs.elements.versions.pgv2DiskImage import PGv2DiskImage
#from sfa.rspecs.elements.versions.plosv1FWRule import PLOSv1FWRule

class Korenv1SliverType:

    @staticmethod
    def add_os_slivers(xml, slivers):
        if not slivers:
            return 
        if not isinstance(slivers, list):
            slivers = [slivers]
        for sliver in slivers:
            sliver_elem = xml.add_element('{%s}sliver' % xml.namespaces['openstack'])
            attrs = ['component_id', 'sliver_id', 'sliver_name', 'sliver_type']
            for attr in attrs:
                if sliver.get(attr):
                    sliver_elem.set(attr, sliver[attr])
           
            availability_zone = sliver['availability_zone']
            if availability_zone and isinstance(availability_zone, dict):
                sliver_elem.add_instance('{%s}availability_zone' % xml.namespaces['openstack'], \
                                         availability_zone, OSZone.fields)

            security_groups = sliver['security_groups']
            if security_groups and isinstance(security_groups, list):
                for security_group in security_groups:
                    if security_group.get('rules'):
                        rules = security_group.pop('rules')
                    group_sliver_elem = sliver_elem.add_instance('{%s}security_group' % xml.namespaces['openstack'], \
                                                                 security_group, OSSecGroup.fields)
                    if rules and isinstance(rules, list):
                        for rule in rules:
                            group_sliver_elem.add_instance('{%s}rule' % xml.namespaces['openstack'], \
                                                           rule, OSSecGroupRule.fields)

            flavor = sliver['flavor']
            if flavor and isinstance(flavor, dict):
                flavor_sliver_elem = sliver_elem.add_instance('{%s}flavor' % xml.namespaces['openstack'], \
                                                              flavor, OSFlavor.fields)
                boot_image = sliver.get('boot_image')
                if boot_image and isinstance(boot_image, dict):
                    flavor_sliver_elem.add_instance('{%s}image' % xml.namespaces['openstack'], \
                                                    boot_image, OSImage.fields)    

            images = sliver['images']
            if images and isinstance(images, list):
                for image in images:
                    # Check if the minimum quotas requested is suitable or not
                    if image['minRam'] <= flavor_sliver_elem.attrib['ram'] and \
                       image['minDisk'] <= flavor_sliver_elem.attrib['storage']:
                        flavor_sliver_elem.add_instance('{%s}image' % xml.namespaces['openstack'], \
                                                        image, OSImage.fields)

            addresses = sliver['addresses']
            if addresses and isinstance(addresses, list):
                for address in addresses:
                    # Check if the type of the address
                    if address.get('private'):
                        sliver_elem.add_instance('{%s}address' % xml.namespaces['openstack'], \
                                                 address.get('private'), OSSliverAddr.fields)
                    elif address.get('public'):
                        sliver_elem.add_instance('{%s}address' % xml.namespaces['openstack'], \
                                                 address.get('public'), OSSliverAddr.fields)

                        
    @staticmethod
    def get_os_slivers(xml, filter=None):
        if filter is None: filter={}
        xpath = './openstack:sliver'
        sliver_elems = xml.xpath(xpath)
        slivers = []
        for sliver_elem in sliver_elems:
            sliver = OSSliver(sliver_elem.attrib, sliver_elem)
            # Get the information of the requested sliver
            sliver_with_fields = Korenv1SliverType.get_os_sliver_attributes(sliver_elem)
            for k,v in sliver.items():
                if sliver[k] == None:
                    sliver[k] = sliver_with_fields[k]
            slivers.append(sliver)
        return slivers
    
    @staticmethod
    def get_os_sliver_attributes(xml, filter=None):
        if filter is None: filter={}
        xpath = './openstack:*'
        sliver_attrib_elems = xml.xpath(xpath)
        sliver = OSSliver()
        c = 0
        for sliver_attrib_elem in sliver_attrib_elems:
            tag = sliver_attrib_elem.tag.split('}')[-1]

            if tag == 'availability_zone':
                sliver['availability_zone'] = OSZone(sliver_attrib_elem.attrib, sliver_attrib_elem)

            elif tag == 'security_group':
                sliver['security_groups']=[] 
                sliver['security_groups'].append( OSSecGroup(sliver_attrib_elem.attrib, sliver_attrib_elem) )
                sub_tags = sliver_attrib_elem.xpath('./openstack:rule')
                rules=[]
                if sub_tags and isinstance(sub_tags, list):
                    for sub_tag in sub_tags:
                        rules.append(OSSecGroupRule(sub_tag.attrib, sub_tag))
                    sliver['security_groups'][c]['rules'] = rules
                c += 1

            elif tag == 'flavor':
                sliver['flavor'] = OSFlavor(sliver_attrib_elem.attrib, sliver_attrib_elem)
                sub_tags = sliver_attrib_elem.xpath('./openstack:image')
                if sub_tags and isinstance(sub_tags, list):
                    sliver['boot_image'] = OSImage(sub_tags[0].attrib, sub_tags[0])
            
            elif tag == 'address':
                pass

            else:
               logger.error("You should include essential information of Openstack sliver") 
        return sliver
