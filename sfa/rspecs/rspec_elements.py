from sfa.util.enumeration import Enum

# recognized top level rspec elements
RSpecElements = Enum('NETWORK', 'NODE', 'SLIVER', 'INTERFACE', 'LINK', 'VLINK')

class RSpecElement:
    def __init__(self, element_type, name, path):
        if not element_type in RSpecElements:
            raise InvalidRSpecElement(element_type)
        self.type = element_type
        self.name = name
        self.path = path
