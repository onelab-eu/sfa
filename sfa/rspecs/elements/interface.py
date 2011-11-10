from sfa.rspecs.elements.element import Element

class Interface(Element):
    fields = {'component_id': None,
              'role': None,
              'client_id': None,
              'ipv4': None,
              'bwlimit': None,
              'node_id': None,
              'interface_id': None,
              'mac_address': None,  
    }    
