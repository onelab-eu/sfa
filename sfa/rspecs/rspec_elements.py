from sfa.util.enumeration import Enum

# recognized top level rspec elements
RSpecElements = Enum(NETWORK='NETWORK', 
                     COMPONENT_MANAGER='COMPONENT_MANAGER', 
                     SLIVER='SLIVER', 
                     NODE='NODE', 
                     INTERFACE='INTERFACE', 
                     LINK='LINK', 
                     SERVICE='SERVICE'
                )

class RSpecElement:
    def __init__(self, element_type, path):
        if not element_type in RSpecElements:
            raise InvalidRSpecElement(element_type)
        self.type = element_type
        self.name = name
        self.path = path
