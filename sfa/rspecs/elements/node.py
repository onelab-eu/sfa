from sfa.rspecs.elements.element import Element
 
class Node(Element):
    
    fields = {
        'component_id': None,
        'component_name': None,
        'component_manager_id': None,
        'authority_id': None,    
        'exclusive': None,
        'location': None,
        'bw_unallocated': None,
        'bw_limit': None,
        'boot_state': None,    
        'slivers': [],
        'hardware_type': [],
        'disk_image': [],
        'interfaces': [],
        'tags': [],
    }
                
      
