#!/usr/bin/python 
from lxml import etree
from StringIO import StringIO
from datetime import datetime, timedelta
from sfa.util.xrn import *
from sfa.util.plxrn import hostname_to_urn
from sfa.util.config import Config  
from sfa.util.faults import SfaNotImplemented, InvalidRSpec

class RSpec:
    header = '<?xml version="1.0"?>\n'
    template = """<RSpec></RSpec>"""
    config = Config()
    xml = None
    type = None
    version = None
    namespaces = None    
    user_options = {}
  
    def __init__(self, rspec="", namespaces={}, user_options={}):
	self.user_options = user_options
        if rspec:
            self.parse_rspec(rspec, namespaces)
        else:
            self.create()

    def create(self, type="advertisement"):
        """
        Create root element
        """
        # eg. 2011-03-23T19:53:28Z 
        date_format = '%Y-%m-%dT%H:%M:%SZ'
        now = datetime.utcnow()
        generated_ts = now.strftime(date_format)
        expires_ts = (now + timedelta(hours=1)).strftime(date_format) 
        self.parse_rspec(self.template, self.namespaces)
        self.xml.set('valid_until', expires_ts)
        self.xml.set('generated', generated_ts)
    
    def parse_rspec(self, rspec, namespaces={}):
        """
        parse rspec into etree
        """
        parser = etree.XMLParser(remove_blank_text=True)
        try:
            tree = etree.parse(rspec, parser)
        except IOError:
            # 'rspec' file doesnt exist. 'rspec' is proably an xml string
            try:
                tree = etree.parse(StringIO(rspec), parser)
            except:
                raise InvalidRSpec('Must specify a xml file or xml string. Received: ' + rspec )

        self.xml = tree.getroot()  
        if namespaces:
           self.namespaces = namespaces

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

    def merge(self, in_rspec):
        pass

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
        

    def __str__(self):
        return self.toxml()

    def toxml(self):
        return self.header + etree.tostring(self.xml, pretty_print=True)  
        
    def save(self, filename):
        f = open(filename, 'w')
        f.write(self.toxml())
        f.close()
 
if __name__ == '__main__':
    rspec = RSpec()
    print rspec
