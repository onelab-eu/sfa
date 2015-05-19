from sfa.rspecs.elements.element import Element

class OSSliver(Element):
    fields = [ 
        'sliver_id',
        'sliver_name',
        'sliver_type',
        'component_id',
        'availability_zone',
        'security_groups',
        'flavor',
        'images',
        'tags',
    ]

class OSFlavor(Element):
    fields = [ 
        'name',
        'id',
        'vcpus',
        'ram',
        'storage',
        'swap',
        'OS-FLV-DISABLED:disabled',
        'OS-FLV-ACCESS:is_public',
    ]

class OSImage(Element):
    fields = [ 
        'name',
        'minDisk',
        'minRam',
        'imgSize',
        'status',
    ]
