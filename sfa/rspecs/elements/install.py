from sfa.rspecs.elements.element import Element
 
class Install(Element):
    fields = {
        'file_type': None,
        'url': None,
        'install_path': None,
    }
