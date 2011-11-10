class Element(dict):

    fields = {}

    def __init__(self, fields={}, element=None):
        self.element = element
        dict.__init__(self, self.fields) 
        self.update(fields)

    @staticmethod
    def get(element_class, xml, xpath, namespaces=None):
        elems = xml.xpath(xpath, namespaces)
        generic_elems = [element_class(elem.attrib, elem) for elem in elems]
        return generic_elems


    @staticmethod
    def add(xml, element_class, name, obj):
        elem = xml.add_element(name)
        for field in element_class.fields:
            if field in obj and obj[field]:
                elem.set(field, obj[field])
        return elem
