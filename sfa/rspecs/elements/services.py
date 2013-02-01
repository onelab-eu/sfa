from sfa.rspecs.elements.element import Element

class ServicesElement(Element):

    fields = [
        'install',
        'execute',
        'login',
        'services_user',
    ]

