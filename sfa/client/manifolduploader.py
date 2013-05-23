#!/usr/bin/env python
#
# inspired from tophat/bin/uploadcredential.py
#
# the purpose here is to let people upload their delegated credentials
# to a manifold/myslice infrastructure, without the need for having to
# install a separate tool; so duplicating this code is suboptimal in
# terms of code sharing but acceptable for hopefully easier use
#
# As of April 2013, manifold is moving from old-fashioned API known as
# v1, that offers an AddCredential API call, towards a new API v2 that
# manages credentials with the same set of Get/Update calls as other
# objects
# 
# Since this code targets the future we favour v2, however in case
# this won't work the v1 way is attempted too
#

## this for now points at demo.myslice.info, but sounds like a
## better default for the long run
DEFAULT_URL = "http://myslice.onelab.eu:7080"
DEFAULT_PLATFORM = 'ple'

import xmlrpclib
import getpass

class ManifoldUploader:
    """A utility class for uploading delegated credentials to a manifold/MySlice infrastructure"""

    # platform is a name internal to the manifold deployment, 
    # that maps to a testbed, like e.g. 'ple'
    def __init__ (self, logger, url=None, platform=None, username=None, password=None, ):
        self._url=url
        self._platform=platform
        self._username=username
        self._password=password
        self.logger=logger
        self._proxy=None

    def username (self):
        if not self._username:
            self._username=raw_input("Enter your manifold username: ")
        return self._username

    def password (self):
        if not self._password:
            username=self.username()
            self._password=getpass.getpass("Enter password for manifold user %s: "%username)
        return self._password

    def platform (self):
        if not self._platform:
            self._platform=raw_input("Enter your manifold platform [%s]: "%DEFAULT_PLATFORM)
            if self._platform.strip()=="": self._platform = DEFAULT_PLATFORM
        return self._platform

    def url (self):
        if not self._url:
            self._url=raw_input("Enter the URL for your manifold API [%s]: "%DEFAULT_URL)
            if self._url.strip()=="": self._url = DEFAULT_URL
        return self._url

    def prompt_all(self):
        self.username(); self.password(); self.platform(); self.url()

    def proxy (self):
        if not self._proxy:
            url=self.url()
            self.logger.debug("Connecting manifold url %s"%url)
            self._proxy = xmlrpclib.ServerProxy(url, allow_none = True)
        return self._proxy

    # does the job for one credential
    # expects the credential (string) and an optional message for reporting
    # return True upon success and False otherwise
    def upload (self, delegated_credential, message=None):
        platform=self.platform()
        username=self.username()
        password=self.password()
        auth = {'AuthMethod': 'password', 'Username': username, 'AuthString': password}
        if not message: message=""

        try:
            # looks like the current implementation of manifold server
            # won't be happy with several calls issued in the same session
#            manifold=self.proxy()
            url=self.url()
            self.logger.debug("Connecting manifold url %s"%url)
            manifold = xmlrpclib.ServerProxy(url, allow_none = True)
            # the code for a V2 interface
            query= { 'action':     'update',
                     'object':     'local:account',
                     'filters':    [ ['platform', '=', platform] ] ,
                     'params':     {'credential': delegated_credential, },
                     }
            try:
                self.logger.debug("Trying v2 method Update@%s %s"%(platform,message))
                retcod2=manifold.Update (auth, query)
            except Exception,e:
                # xxx we need a constant constant for UNKNOWN, how about using 1
                MANIFOLD_UNKNOWN=1
                retcod2={'code':MANIFOLD_UNKNOWN,'description':"%s"%e}
            if retcod2['code']==0:
                info=""
                if message: info += message+" "
                info += 'v2 upload OK'
                self.logger.info(info)
                return True
            #print delegated_credential, "upload failed,",retcod['description'], \
            #    "with code",retcod['code']
            # the code for V1
            try:
                self.logger.debug("Trying v1 method AddCredential@%s %s"%(platform,message))
                retcod1=manifold.AddCredential(auth, delegated_credential, platform)
            except Exception,e:
                retcod1=e
            if retcod1==1:
                info=""
                if message: info += message+" "
                info += 'v1 upload OK'
                self.logger.info(message)
                return True
            # everything has failed, let's report
            if message: self.logger.error("Could not upload %s"%message)
            else: self.logger.error("Could not upload credential")
            if 'code' in retcod2 and 'description' in retcod2:
                self.logger.info("  V2 Update returned code %s and error >>%s<<"%(retcod2['code'],retcod2['description']))
                self.logger.debug("****** full retcod2")
                for (k,v) in retcod2.items(): self.logger.debug("**** %s: %s"%(k,v))
            else:
                self.logger.info("  V2 Update returned %s"%retcod2)
            self.logger.info("  V1 AddCredential returned code %s (expected 1)"%retcod1)
            return False
        except Exception, e:
            if message: self.logger.error("Could not upload %s %s"%(message,e))
            else:        self.logger.error("Could not upload credential %s"%e)
            if self.logger.debugEnabled():
                import traceback
                traceback.print_exc()
            return False

### this is mainly for unit testing this class but can come in handy as well
def main ():
    from argparse import ArgumentParser
    parser = ArgumentParser (description="manifoldupoader simple tester.")
    parser.add_argument ('credential_files',metavar='FILE',type=str,nargs='+',
                         help="the filenames to upload")
    parser.add_argument ('-u','--url',dest='url', action='store',default=None,
                         help='the URL of the manifold API')
    parser.add_argument ('-p','--platform',dest='platform',action='store',default=None,
                         help='the manifold platform name')
    parser.add_argument ('-U','--user',dest='username',action='store',default=None,
                         help='the manifold username')
    parser.add_argument ('-P','--password',dest='password',action='store',default=None,
                         help='the manifold password')
    parser.add_argument ('-v','--verbose',dest='verbose',action='count',default=0,
                         help='more and more verbose')
    args = parser.parse_args ()
    
    from sfa.util.sfalogging import sfi_logger
    sfi_logger.enable_console()
    sfi_logger.setLevelFromOptVerbose(args.verbose)
    uploader = ManifoldUploader (url=args.url, platform=args.platform,
                                 username=args.username, password=args.password,
                                 logger=sfi_logger)

    for filename in args.credential_files:
        with file(filename) as f:
            result=uploader.upload (f.read(),filename)
            sfi_logger.info('... result=%s'%result)

if __name__ == '__main__':
    main()
