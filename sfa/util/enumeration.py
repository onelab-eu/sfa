
class Enum(set):
    def __init__(self, *args, **kwds):
        set.__init__(self)
        enums = dict(zip(args, [object() for i in range(len(args))]), **kwds)
        for (key, value) in enums.items():
            setattr(self, key, value)
            self.add(eval('self.%s' % key))


#def Enum2(*args, **kwds):
#    enums = dict(zip(sequential, range(len(sequential))), **named)
#    return type('Enum', (), enums)
