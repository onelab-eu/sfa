class Interface(dict):
    element = None
    fields = {'component_id': None,
              'role': None,
              'client_id': None,
              'ipv4': None,
    }    
    def __init__(self, fields={}, element=None):
        self.element = element
        dict.__init__(self, Interface.fields)
        self.update(fields)
        
    
