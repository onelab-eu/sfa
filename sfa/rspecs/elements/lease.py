from sfa.rspecs.elements.element import Element
 
class Lease(Element):
    
    fields = [
        'lease_id',
        'component_id',
        'slice_id'
        't_from',
        't_until',    
    ]
