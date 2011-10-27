class Interface(dict):
    fields = {'component_id': None,
              'role': None,
              'client_id': None,
              'ipv4': None 
    }    
    def __init__(self, fields={}):
        dict.__init__(self, Interface.fields)
        self.update(fields)
        
    
