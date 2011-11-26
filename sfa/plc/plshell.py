import xmlrpclib

from sfa.util.sfalogging import logger

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
        self.url = config.SFA_PLC_URL
        # xxx attempt to use the 'capability' auth mechanism for higher performance
        # when the PLC db is local
        # xxx todo
        is_local = False
        if is_local:
            try:
                import PLC.Shell
                plc_direct_access=True
            except:
                plc_direct_access=False
        if is_local and plc_direct_access:
            logger.info('plshell - capability access')
            self.plauth = { 'AuthMethod': 'capability',
                            'UserName':   config.SFA_PLC_USER,
                            'AuthString': config.SFA_PLC_PASSWORD,
                            }
            self.proxy = PLC.Shell.Shell ()

        else:
            logger.info('plshell - xmlrpc access')
            self.plauth = { 'AuthMethod': 'password',
                            'Username':   config.SFA_PLC_USER,
                            'AuthString': config.SFA_PLC_PASSWORD,
                            }
            self.proxy = xmlrpclib.Server(self.url, verbose = 0, allow_none = True)

    def __getattr__(self, name):
        def func(*args, **kwds):
            actual_name=None
            if name in PlShell.direct_calls: actual_name=name
            if name in PlShell.alias_calls: actual_name=PlShell.alias_calls[name]
            if not actual_name:
                raise Exception, "Illegal method call %s for PL driver"%(name)
            result=getattr(self.proxy, actual_name)(self.plauth, *args, **kwds)
            logger.info('%s (%s) returned ... %s'%(name,actual_name,result))
            return result
        return func
