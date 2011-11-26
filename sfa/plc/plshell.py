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


    # use the 'capability' auth mechanism for higher performance when the PLC db is local    
    def __init__ ( self, config ) :
        url = config.SFA_PLC_URL
        # try to figure if the url is local
        hostname=urlparse(url).hostname
        is_local=False
        if hostname == 'localhost': is_local=True
        # otherwise compare IP addresses
        url_ip=socket.gethostbyname(hostname)
        local_ip=socket.gethostbyname(socket.gethostname())
        if url_ip==local_ip: is_local=True

        if is_local:
            try:
                # too bad this is not installed properly
                plcapi_path="/usr/share/plc_api"
                if plcapi_path not in sys.path: sys.path.append(plcapi_path)
                import PLC.Shell
                plc_direct_access=True
            except:
                plc_direct_access=False
        if is_local and plc_direct_access:
            logger.debug('plshell access - capability')
            self.plauth = { 'AuthMethod': 'capability',
                            'Username':   config.SFA_PLC_USER,
                            'AuthString': config.SFA_PLC_PASSWORD,
                            }
            self.proxy = PLC.Shell.Shell ()

        else:
            logger.debug('plshell access - xmlrpc')
            self.plauth = { 'AuthMethod': 'password',
                            'Username':   config.SFA_PLC_USER,
                            'AuthString': config.SFA_PLC_PASSWORD,
                            }
            self.proxy = xmlrpclib.Server(url, verbose = 0, allow_none = True)

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
