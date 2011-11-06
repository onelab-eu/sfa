from sfa.rspecs.elements.element import Element

class Login(Element):
    fields = {
        'authentication': None,
        'hostname': None,
        'port': None
    }
