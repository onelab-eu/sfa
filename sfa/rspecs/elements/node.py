from sfa.rspecs.elements.element import Element
 
class Node(Element):
    
    fields = {
        'component_id': None,
        'component_name': None,
        'component_manager_id': None,
        'client_id': None,
        'sliver_id': None,
        'authority_id': None,    
        'exclusive': None,
        'location': None,
        'bw_unallocated': None,
        'bw_limit': None,
        'boot_state': None,    
        'slivers': [],
        'hardware_types': [],
        'disk_images': [],
        'interfaces': [],
        'services': [],
        'tags': [],
        'pl_initscripts': [],
    }
                
      
