#
# SFA XML-RPC and SOAP interfaces
#

import string
import xmlrpclib

# SOAP support is optional
try:
    import SOAPpy
    from SOAPpy.Parser import parseSOAPRPC
    from SOAPpy.Types import faultType
    from SOAPpy.NS import NS
    from SOAPpy.SOAPBuilder import buildSOAP
except ImportError:
    SOAPpy = None

####################
#from sfa.util.faults import SfaNotImplemented, SfaAPIError, SfaInvalidAPIMethod, SfaFault
from sfa.util.faults import SfaInvalidAPIMethod, SfaAPIError, SfaFault
from sfa.util.sfalogging import logger

####################
# See "2.2 Characters" in the XML specification:
#
# #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD]
# avoiding
# [#x7F-#x84], [#x86-#x9F], [#xFDD0-#xFDDF]

invalid_xml_ascii = map(chr, range(0x0, 0x8) + [0xB, 0xC] + range(0xE, 0x1F))
xml_escape_table = string.maketrans("".join(invalid_xml_ascii), "?" * len(invalid_xml_ascii))

def xmlrpclib_escape(s, replace = string.replace):
    """
    xmlrpclib does not handle invalid 7-bit control characters. This
    function augments xmlrpclib.escape, which by default only replaces
    '&', '<', and '>' with entities.
    """

    # This is the standard xmlrpclib.escape function
    s = replace(s, "&", "&amp;")
    s = replace(s, "<", "&lt;")
    s = replace(s, ">", "&gt;",)

    # Replace invalid 7-bit control characters with '?'
    return s.translate(xml_escape_table)

def xmlrpclib_dump(self, value, write):
    """
    xmlrpclib cannot marshal instances of subclasses of built-in
    types. This function overrides xmlrpclib.Marshaller.__dump so that
    any value that is an instance of one of its acceptable types is
    marshalled as that type.

    xmlrpclib also cannot handle invalid 7-bit control characters. See
    above.
    """

    # Use our escape function
    args = [self, value, write]
    if isinstance(value, (str, unicode)):
        args.append(xmlrpclib_escape)

    try:
        # Try for an exact match first
        f = self.dispatch[type(value)]
    except KeyError:
        raise
        # Try for an isinstance() match
        for Type, f in self.dispatch.iteritems():
            if isinstance(value, Type):
                f(*args)
                return
        raise TypeError, "cannot marshal %s objects" % type(value)
    else:
        f(*args)

# You can't hide from me!
xmlrpclib.Marshaller._Marshaller__dump = xmlrpclib_dump

class XmlrpcApi:
    """
    The XmlrpcApi class implements a basic xmlrpc (or soap) service 
    """

    protocol = None
  
    def __init__ (self, encoding="utf-8", methods='sfa.methods'):

        self.encoding = encoding
        self.source = None 
        
        # flat list of method names
        self.methods_module = methods_module = __import__(methods, fromlist=[methods])
        self.methods = methods_module.all

        self.logger = logger
 
    def callable(self, method):
        """
        Return a new instance of the specified method.
        """
        # Look up method
        if method not in self.methods:
            raise SfaInvalidAPIMethod, method
        
        # Get new instance of method
        try:
            classname = method.split(".")[-1]
            module = __import__(self.methods_module.__name__ + "." + method, globals(), locals(), [classname])
            callablemethod = getattr(module, classname)(self)
            return getattr(module, classname)(self)
        except (ImportError, AttributeError):
            raise SfaInvalidAPIMethod, method

    def call(self, source, method, *args):
        """
        Call the named method from the specified source with the
        specified arguments.
        """
        function = self.callable(method)
        function.source = source
        self.source = source
        return function(*args)

    
    def handle(self, source, data, method_map):
        """
        Handle an XML-RPC or SOAP request from the specified source.
        """
        # Parse request into method name and arguments
        try:
            interface = xmlrpclib
            self.protocol = 'xmlrpclib'
            (args, method) = xmlrpclib.loads(data)
            if method_map.has_key(method):
                method = method_map[method]
            methodresponse = True
            
        except Exception, e:
            if SOAPpy is not None:
                self.protocol = 'soap'
                interface = SOAPpy
                (r, header, body, attrs) = parseSOAPRPC(data, header = 1, body = 1, attrs = 1)
                method = r._name
                args = r._aslist()
                # XXX Support named arguments
            else:
                raise e

        try:
            result = self.call(source, method, *args)
        except SfaFault, fault:
            result = fault
            self.logger.log_exc("XmlrpcApi.handle has caught Exception") 
        except Exception, fault:
            self.logger.log_exc("XmlrpcApi.handle has caught Exception")
            result = SfaAPIError(fault)


        # Return result
        response = self.prepare_response(result, method)
        return response
    
    def prepare_response(self, result, method=""):
        """
        convert result to a valid xmlrpc or soap response
        """   
 
        if self.protocol == 'xmlrpclib':
            if not isinstance(result, SfaFault):
                result = (result,)
            response = xmlrpclib.dumps(result, methodresponse = True, encoding = self.encoding, allow_none = 1)
        elif self.protocol == 'soap':
            if isinstance(result, Exception):
                result = faultParameter(NS.ENV_T + ":Server", "Method Failed", method)
                result._setDetail("Fault %d: %s" % (result.faultCode, result.faultString))
            else:
                response = buildSOAP(kw = {'%sResponse' % method: {'Result': result}}, encoding = self.encoding)
        else:
            if isinstance(result, Exception):
                raise result 
            
        return response

