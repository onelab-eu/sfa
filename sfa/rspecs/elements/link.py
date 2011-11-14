from sfa.rspecs.elements.element import Element    

class Link(Element):
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
    }
