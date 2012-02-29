import xmlrpclib

from sfa.util.sfalogging import logger

class FdShell:
    """
    A simple xmlrpc shell to a federica API server
    This class can receive the XMLRPC calls to the federica testbed
    For safety this is limited to a set of hard-coded calls
    """
    
    direct_calls = [ 'listAvailableResources',
                     'listSliceResources',
                     'createSlice',
                     'deleteSlice',
                     'getRSpecVersion',
                     'listSlices',
                    ]

    def __init__ ( self, config ) :
        url=config.SFA_FEDERICA_URL
        # xxx not sure if java xmlrpc has support for None
        # self.proxy = xmlrpclib.Server(url, verbose = False, allow_none = True)
        # xxx turn on verbosity
        self.proxy = xmlrpclib.Server(url, verbose = True)

    # xxx get credentials from the config ?
    # right now basic auth data goes into the URL
    # so do *not* add any credential at that point
    def __getattr__(self, name):
        def func(*args, **kwds):
            if name not in FdShell.direct_calls:
                raise Exception, "Illegal method call %s for FEDERICA driver"%(name)
            logger.info("Issuing %s args=%s kwds=%s to federica"%\
                            (name,args,kwds))
#            result=getattr(self.proxy, "AggregateManager.%s"%name)(credential, *args, **kwds)
            result=getattr(self.proxy, "AggregateManager.%s"%name)(*args, **kwds)
            logger.debug('FdShell %s (%s) returned ... '%(name,name))
            return result
        return func

