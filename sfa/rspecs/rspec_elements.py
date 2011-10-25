from sfa.util.enumeration import Enum

# recognized top level rspec elements
RSpecElements = Enum(NETWORK='NETWORK', 
                     COMPONENT_MANAGER='COMPONENT_MANAGER', 
                     SLIVER='SLIVER', 
                     SLIVER_TYPE='SLIVER_TYPE', 
                     NODE='NODE', 
                     INTERFACE='INTERFACE', 
                     INTERFACE_REF='INTERFACE_REF', 
                     LINK='LINK', 
                     LINK_TYPE='LINK_TYPE', 
                     SERVICE='SERVICE',
                     PROPERTY='PROPERTY'
                )

class RSpecElement:
    def __init__(self, element_type, path):
        if not element_type in RSpecElements:
            raise InvalidRSpecElement(element_type)
        self.type = element_type
        self.path = path
