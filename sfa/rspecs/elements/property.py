from sfa.rspecs.elements.element import Element

class Property(Element):
    
    fields = {
        'source_id': None,
        'dest_id': None,
        'capacity': None,
        'latency': None,
        'packet_loss': None,
    }
       
