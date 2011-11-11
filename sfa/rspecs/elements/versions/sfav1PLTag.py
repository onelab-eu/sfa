from sfa.rspecs.elements.element import Element  
from sfa.rspecs.elements.pltag import PLTag

class SFAv1PLTag:
    @staticmethod
    def add_pl_tags(xml, pl_tags):
        for pl_tag in pl_tags:
            pl_tag_elem = xml.add_element(pl_tag['name'])
            pl_tag_elem.set_text(pl_tag['value'])
              
    @staticmethod
    def get_pl_tags(xml, ignore=[]):
        pl_tags = []
        for elem in xml.iterchildren():
            if elem.tag not in ignore:
                pl_tag = PLTag({'name': elem.tag, 'value': elem.text})
                pl_tags.appen(pl_tag)    
        return pl_tags

