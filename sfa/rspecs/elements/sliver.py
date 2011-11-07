from sfa.rspecs.elements.element import Element

class Sliver(Element):
    fields = {
        'client_id': None,
        'name': None,
        'tags': [],
        'slice_id': None,
    }
