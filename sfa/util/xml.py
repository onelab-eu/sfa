#!/usr/bin/python 
from lxml import etree
from StringIO import StringIO

from sfa.util.faults import InvalidXML

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

class XML:
 
    def __init__(self, xml=None):
        self.root = None
        self.namespaces = None
        self.default_namespace = None
        self.schema = None
        if isinstance(xml, basestring):
            self.parse_xml(xml)
        elif isinstance(xml, etree._ElementTree):
            self.root = xml.getroot()
        elif isinstance(xml, etree._Element):
            self.root = xml 

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
                raise InvalidXML(str(e))
        self.root = tree.getroot()
        # set namespaces map
        self.namespaces = dict(self.root.nsmap)
        if 'default' not in self.namespaces and None in self.namespaces: 
            # If the 'None' exist, then it's pointing to the default namespace. This makes 
            # it hard for us to write xpath queries for the default naemspace because lxml 
            # wont understand a None prefix. We will just associate the default namespeace 
            # with a key named 'default'.     
            self.namespaces['default'] = self.namespaces[None]
        else:
            self.namespaces['default'] = 'default' 

        # set schema 
        for key in self.root.attrib.keys():
            if key.endswith('schemaLocation'):
                # schema location should be at the end of the list
                schema_parts  = self.root.attrib[key].split(' ')
                self.schema = schema_parts[1]    
                namespace, schema  = schema_parts[0], schema_parts[1]
                break

    def parse_dict(self, d, root_tag_name='xml', element = None):
        if element is None: 
            if self.root is None:
                self.parse_xml('<%s/>' % root_tag_name)
            element = self.root

        if 'text' in d:
            text = d.pop('text')
            element.text = text

        # handle repeating fields
        for (key, value) in d.items():
            if isinstance(value, list):
                value = d.pop(key)
                for val in value:
                    if isinstance(val, dict):
                        child_element = etree.SubElement(element, key)
                        self.parse_dict(val, key, child_element)
                    elif isinstance(val, basestring):
                        child_element = etree.SubElement(element, key).text = val
                        
            elif isinstance(value, int):
                d[key] = unicode(d[key])  
            elif value is None:
                d.pop(key)

        # element.attrib.update will explode if DateTimes are in the
        # dcitionary.
        d=d.copy()
        for k in d.keys():
            if (type(d[k]) != str) and (type(d[k]) != unicode):
                del d[k]

        element.attrib.update(d)

    def validate(self, schema):
        """
        Validate against rng schema
        """
        relaxng_doc = etree.parse(schema)
        relaxng = etree.RelaxNG(relaxng_doc)
        if not relaxng(self.root):
            error = relaxng.error_log.last_error
            message = "%s (line %s)" % (error.message, error.line)
            raise InvalidXML(message)
        return True

    def xpath(self, xpath, namespaces=None):
        if not namespaces:
            namespaces = self.namespaces
        return self.root.xpath(xpath, namespaces=namespaces)

    def set(self, key, value):
        return self.root.set(key, value)

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
            parent = self.root
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
            root_node = self.root

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

    def __str__(self):
        return self.toxml()

    def toxml(self):
        return etree.tostring(self.root, encoding='UTF-8', pretty_print=True)  
    
    def todict(self, elem=None):
        if elem is None:
            elem = self.root
        d = {}
        d.update(elem.attrib)
        d['text'] = elem.text
        for child in elem.iterchildren():
            if child.tag not in d:
                d[child.tag] = []
            d[child.tag].append(self.todict(child))
        return d

    # XXX smbaker, for record.load_from_string
    def todict2(self, elem=None):
        if elem is None:
            elem = self.root
        d = {}
        d.update(elem.attrib)
        d['text'] = elem.text
        for child in elem.iterchildren():
            if child.tag not in d:
                d[child.tag] = []
            d[child.tag].append(self.todict2(child))

        if len(d)==1 and ("text" in d):
            d = d["text"]

        return d
        
    def save(self, filename):
        f = open(filename, 'w')
        f.write(self.toxml())
        f.close()

# no RSpec in scope 
#if __name__ == '__main__':
#    rspec = RSpec('/tmp/resources.rspec')
#    print rspec

