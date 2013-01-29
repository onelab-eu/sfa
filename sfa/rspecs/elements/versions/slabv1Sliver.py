from sfa.rspecs.elements.element import Element
from sfa.rspecs.elements.sliver import Sliver

#from sfa.rspecs.elements.versions.pgv2DiskImage import PGv2DiskImage
import sys
class Slabv1Sliver:

    @staticmethod
    def add_slivers(xml, slivers):
        if not slivers:
            return 
        if not isinstance(slivers, list):
            slivers = [slivers]
        for sliver in slivers: 
            #sliver_elem = xml.add_element('sliver_type')
            sliver_elem = xml.add_element('sliver')
            if sliver.get('type'):
                sliver_elem.set('name', sliver['type'])
            if sliver.get('client_id'):
                sliver_elem.set('client_id', sliver['client_id'])
            #images = sliver.get('disk_images')
            #if images and isinstance(images, list):
                #Slabv1DiskImage.add_images(sliver_elem, images)      
            Slabv1Sliver.add_sliver_attributes(sliver_elem, sliver.get('tags', []))
    
    @staticmethod
    def add_sliver_attributes(xml, attributes):
        if attributes: 
            for attribute in attributes:
                if attribute['name'] == 'initscript':
                    xml.add_element('{%s}initscript' % xml.namespaces['planetlab'], name=attribute['value'])
                elif tag['tagname'] == 'flack_info':
                    attrib_elem = xml.add_element('{%s}info' % self.namespaces['flack'])
                    attrib_dict = eval(tag['value'])
                    for (key, value) in attrib_dict.items():
                        attrib_elem.set(key, value)                
    @staticmethod
    def get_slivers(xml, filter={}):
        xpath = './default:sliver | ./sliver'
     
        sliver_elems = xml.xpath(xpath)
        slivers = []
        for sliver_elem in sliver_elems: 
            sliver = Sliver(sliver_elem.attrib,sliver_elem)

            if 'component_id' in xml.attrib:     
                sliver['component_id'] = xml.attrib['component_id']
            if 'name' in sliver_elem.attrib:
                sliver['type'] = sliver_elem.attrib['name']
            #sliver['images'] = Slabv1DiskImage.get_images(sliver_elem)
                
            print>>sys.stderr, "\r\n \r\n SLABV1SLIVER.PY  \t\t\t  get_slivers sliver %s " %( sliver)
            slivers.append(sliver)
        return slivers

    @staticmethod
    def get_sliver_attributes(xml, filter={}):
        return []             