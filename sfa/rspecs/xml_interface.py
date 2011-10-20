#!/usr/bin/python 
from lxml import etree
from StringIO import StringIO
from datetime import datetime, timedelta
from sfa.util.xrn import *
from sfa.util.plxrn import hostname_to_urn
from sfa.util.faults import SfaNotImplemented, InvalidRSpec, InvalidRSpecElement

class XpathFilter:
    @staticmethod
    def xpath(filter={}):
        xpath = ""
        if filter:
            filter_list = []
            for (key, value) in filter.items():
                if key == 'text':
                    key = 'text()'
                else:
                    key = '@'+key
                if isinstance(value, str):
                    filter_list.append('%s="%s"' % (key, value))
                elif isinstance(value, list):
                    filter_list.append('contains("%s", %s)' % (' '.join(map(str, value)), key))
            if filter_list:
                xpath = ' and '.join(filter_list)
                xpath = '[' + xpath + ']'
        return xpath

class XMLInterface:
 
    def __init__(self, xml=""):
        self.header = None 
        self.template = None 
        self.xml = None
        self.namespaces = None
        if xml:
            self.parse_xml(xml)
        else:
            self.create()

    def create(self):
        """
        Create root element
        """
        self.parse_rspec(self.template)
    
    def parse_xml(self, xml):
        """
        parse rspec into etree
        """
        parser = etree.XMLParser(remove_blank_text=True)
        try:
            tree = etree.parse(xml, parser)
        except IOError:
            # 'rspec' file doesnt exist. 'rspec' is proably an xml string
            try:
                tree = etree.parse(StringIO(xml), parser)
            except Exception, e:
                raise InvalidRSpec(str(e))
        self.xml = tree.getroot()  

    def validate(self, schema):
        """
        Validate against rng schema
        """
        relaxng_doc = etree.parse(schema)
        relaxng = etree.RelaxNG(relaxng_doc)
        if not relaxng(self.xml):
            error = relaxng.error_log.last_error
            message = "%s (line %s)" % (error.message, error.line)
            raise InvalidRSpec(message)
        return True

    def xpath(self, xpath):
        return self.xml.xpath(xpath, namespaces=self.namespaces)

    def add_attribute(self, elem, name, value):
        """
        Add attribute to specified etree element    
        """
        opt = etree.SubElement(elem, name)
        opt.text = value

    def add_element(self, name, attrs={}, parent=None, text=""):
        """
        Generic wrapper around etree.SubElement(). Adds an element to 
        specified parent node. Adds element to root node is parent is 
        not specified. 
        """
        if parent == None:
            parent = self.xml
        element = etree.SubElement(parent, name)
        if text:
            element.text = text
        if isinstance(attrs, dict):
            for attr in attrs:
                element.set(attr, attrs[attr])  
        return element

    def remove_attribute(self, elem, name, value):
        """
        Removes an attribute from an element
        """
        if elem is not None:
            opts = elem.iterfind(name)
            if opts is not None:
                for opt in opts:
                    if opt.text == value:
                        elem.remove(opt)

    def remove_element(self, element_name, root_node = None):
        """
        Removes all occurences of an element from the tree. Start at 
        specified root_node if specified, otherwise start at tree's root.   
        """
        if not root_node:
            root_node = self.xml

        if not element_name.startswith('//'):
            element_name = '//' + element_name

        elements = root_node.xpath('%s ' % element_name, namespaces=self.namespaces)
        for element in elements:
            parent = element.getparent()
            parent.remove(element)

    def attributes_list(self, elem):
        # convert a list of attribute tags into list of tuples
        # (tagnme, text_value)
        opts = []
        if elem is not None:
            for e in elem:
                opts.append((e.tag, str(e.text).strip()))
        return opts

    def get_element_attributes(self, elem=None, depth=0):
        if elem == None:
            elem = self.root_node
        if not hasattr(elem, 'attrib'):
            # this is probably not an element node with attribute. could be just and an
            # attribute, return it
            return elem
        attrs = dict(elem.attrib)
        attrs['text'] = str(elem.text).strip()
        attrs['parent'] = elem.getparent()
        if isinstance(depth, int) and depth > 0:
            for child_elem in list(elem):
                key = str(child_elem.tag)
                if key not in attrs:
                    attrs[key] = [self.get_element_attributes(child_elem, depth-1)]
                else:
                    attrs[key].append(self.get_element_attributes(child_elem, depth-1))
        else:
            attrs['child_nodes'] = list(elem)
        return attrs

    def merge(self, in_xml):
        pass

    def cleanup(self):
        """
        Optional method which inheriting classes can choose to implent. 
        """
        pass 

    def __str__(self):
        return self.toxml()

    def toxml(self, cleanup=False):
        if cleanup:
            self.cleanup()
        return self.header + etree.tostring(self.xml, pretty_print=True)  
        
    def save(self, filename):
        f = open(filename, 'w')
        f.write(self.toxml())
        f.close()
 
if __name__ == '__main__':
    rspec = RSpec('/tmp/resources.rspec')
    print rspec

