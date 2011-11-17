class Element(dict):

    fields = {}

    def __init__(self, fields={}, element=None, keys=None):
        self.element = element
        dict.__init__(self, dict.fromkeys(self.fields))
        if not keys:
            keys = fields.keys()
        for key in keys:
            if key in fields:
                self[key] = fields[key] 

    def __getattr__(self, attr):
        if hasattr(self, attr):
            return getattr(self, attr)
        elif self.element is not None and hasattr(self.element, attr):
            return getattr(self.element, attr)
        raise AttributeError, "Element class has no attribute %s" % attr
