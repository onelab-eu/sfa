from sfa.rspecs.elements.interface import Interface

class Link(dict):
    
    fields = {
        'client_id': None, 
        'component_id': None,
        'component_name': None,
        'component_manager': None,
        'type': None,
        'interface1': None,
        'interface2': None,
        'capacity': None,
        'latency': None,
        'packet_loss': None,
        'description': None,
        '_element': None
    }
    
    def __init__(self, fields={}):
        dict.__init__(self, Link.fields)
        self.update(fields)

