import xmlrpclib

class PlShell:
    """
    A simple xmlrpc shell to a myplc instance
    This class can receive all PLCAPI calls to the underlying testbed
    For safety this is limited to a set of hard-coded calls
    """
    
    direct_calls = ['AddNode', 'AddPerson', 'AddPersonKey', 'AddPersonToSite',
                    'AddPersonToSlice', 'AddRoleToPerson', 'AddSite', 'AddSiteTag', 'AddSlice',
                    'AddSliceTag', 'AddSliceToNodes', 'BindObjectToPeer', 'DeleteKey',
                    'DeleteNode', 'DeletePerson', 'DeletePersonFromSlice', 'DeleteSite',
                    'DeleteSlice', 'DeleteSliceFromNodes', 'DeleteSliceTag', 'GetInitScripts',
                    'GetInterfaces', 'GetKeys', 'GetNodeTags', 'GetPeers',
                    'GetPersons', 'GetSlices', 'GetSliceTags', 'GetTagTypes',
                    'UnBindObjectFromPeer', 'UpdateNode', 'UpdatePerson', 'UpdateSite',
                    'UpdateSlice', 'UpdateSliceTag',
                    # also used as-is in importer
                    'GetSites','GetNodes',
                    ]
    # support for other names - this is experimental
    alias_calls = { 'get_authorities':'GetSites',
                    'get_nodes':'GetNodes',
                    }

    def __init__ ( self, config ) :
        self.plauth = {'Username': config.SFA_PLC_USER,
                       'AuthMethod': 'password',
                       'AuthString': config.SFA_PLC_PASSWORD}
        
        self.url = config.SFA_PLC_URL
        self.plauth = {'Username': 'root@test.onelab.eu',
                       'AuthMethod': 'password',
                       'AuthString': 'test++'}
        self.proxy_server = xmlrpclib.Server(self.url, verbose = 0, allow_none = True)

    def __getattr__(self, name):
        def func(*args, **kwds):
            actual_name=None
            if name in PlShell.direct_calls: actual_name=name
            if name in PlShell.alias_calls: actual_name=PlShell.alias_calls[name]
            if not actual_name:
                raise Exception, "Illegal method call %s for PL driver"%(name)
            return getattr(self.proxy_server, actual_name)(self.plauth, *args, **kwds)
        return func
