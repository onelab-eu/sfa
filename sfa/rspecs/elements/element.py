class Element(dict):

    fields = {}

    def __init__(self, fields={}, element=None, keys=None):
        self.element = element
        dict.__init__(self, self.fields)
        if not keys:
            keys = fields.keys()
        for key in keys:
            if key in fields:
                self[key] = fields[key] 

    @staticmethod
    def get_elements(xml, xpath, element_class=None, fields=None):
        """
        Search the specifed xml node for elements that match the 
        specified xpath query. 
        Returns a list of objectes instanced by the specfied element_class.
        """
        if not element_class:
            element_class = Element
        if not fields:
           fields = element_class.fields.keys()
        elems = xml.xpath(xpath)
        objs = []
        for elem in elems:
            if not fields:
                obj = element_class(elem.attrib, elem)
            else:
                obj = element_class({}, elem)
                for field in fields:
                    if field in elem.attrib:
                        obj[field] = elem.attrib[field]    
            objs.append(obj)
        generic_elems = [element_class(elem.attrib, elem) for elem in elems]
        return objs


    @staticmethod
    def add_elements(xml, name, objs, fields=None):
        """
        Adds a child node to the specified xml node based on
        the specified name , element class and object.    
        """
        if not isinstance(objs, list):
            objs = [objs]
        elems = []
        for obj in objs:
            if not obj:
                continue
            if not fields:
                fields = obj.keys()
            elem = xml.add_element(name)
            for field in fields:
                if field in obj and obj[field]:
                    elem.set(field, obj[field])
            elems.append(elem)
        return elems
