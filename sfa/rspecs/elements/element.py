class Element(dict):

    fields = {}

    def __init__(self, fields={}, element=None):
        self.element = element
        dict.__init__(self, self.fields) 
        self.update(fields)

