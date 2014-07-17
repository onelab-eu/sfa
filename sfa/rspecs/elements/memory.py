# This is a simple illustrative example of how a memory amount could be exposed
# in the rspec like this <memory Gb="4"/>
# this is not intended for production though

from sfa.rspecs.elements.element import Element

class Memory(Element):
    
    fields = [
        'Gb',
    ]
