from lxml import etree

class Element:
    def __init__(self, root_node, namespaces = None):
        self.root_node = root_node
        self.namespaces = namespaces

    def xpath(self, xpath):
        return this.root_node.xpath(xpath, namespaces=self.namespaces) 

    def add_element(self, name, attrs={}, parent=None, text=""):
        """
        Generic wrapper around etree.SubElement(). Adds an element to
        specified parent node. Adds element to root node is parent is
        not specified.
        """
        if parent == None:
            parent = self.root_node
        element = etree.SubElement(parent, name)
        if text:
            element.text = text
        if isinstance(attrs, dict):
            for attr in attrs:
                element.set(attr, attrs[attr])
        return element

    def remove_element(self, element_name, root_node = None):
        """
        Removes all occurences of an element from the tree. Start at
        specified root_node if specified, otherwise start at tree's root.
        """
        if not root_node:
            root_node = self.root_node

        if not element_name.startswith('//'):
            element_name = '//' + element_name

        elements = root_node.xpath('%s ' % element_name, namespaces=self.namespaces)
        for element in elements:
            parent = element.getparent()
            parent.remove(element)

    
    def add_attribute(self, elem, name, value):
        """
        Add attribute to specified etree element
        """
        opt = etree.SubElement(elem, name)
        opt.text = value

    def remove_attribute(self, elem, name, value):
        """
        Removes an attribute from an element
        """
        if not elem == None:
            opts = elem.iterfind(name)
            if opts is not None:
                for opt in opts:
                    if opt.text == value:
                        elem.remove(opt)

    def get_attributes(self, elem=None, depth=None):
        if elem == None:
            elem = self.root_node
        attrs = dict(elem.attrib)
        attrs['text'] = str(elem.text).strip()
        if depth is None or isinstance(depth, int) and depth > 0: 
            for child_elem in list(elem):
                key = str(child_elem.tag)
                if key not in attrs:
                    attrs[key] = [self.get_attributes(child_elem, recursive)]
                else:
                    attrs[key].append(self.get_attributes(child_elem, recursive))
        return attrs
    
    def attributes_list(self, elem):
        # convert a list of attribute tags into list of tuples
        # (tagnme, text_value)
        opts = []
        if not elem == None:
            for e in elem:
                opts.append((e.tag, e.text))
        return opts

    
