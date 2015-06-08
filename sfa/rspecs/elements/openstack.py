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
        'boot_image',
        'images',
        'addresses',
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

class OSZone(Element):
    fields = [
        'name',
    ]

class OSSecGroup(Element):
    fields = [
        'id',
        'name',
        'description',
        'rules'
    ]

class OSSecGroupRule(Element):
    fields = [
        'ip_protocol',
        'from_port',
        'to_port',
        'ip_range',
    ]

class OSSliverAddr(Element):
    fields = [
        'mac_address',
        'version',
        'address',
        'type',
    ]
