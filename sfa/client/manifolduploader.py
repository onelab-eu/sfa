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
    def __init__ (self, url=None, platform=None, username=None, password=None, debug=False):
        self._url=url
        self._platform=platform
        self._username=username
        self._password=password
        self.debug=debug

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

    # does the job for one credential
    # expects the credential (string) and an optional filename (for messaging)
    # return True upon success and False otherwise
    def upload (self, delegated_credential, filename=None):
        url=self.url()
        platform=self.platform()
        username=self.username()
        password=self.password()
        auth = {'AuthMethod': 'password', 'Username': username, 'AuthString': password}

        try:
            manifold = xmlrpclib.Server(url, allow_none = 1)
            # the code for a V2 interface
            query= { 'action':       'update',
                     'fact_table':   'local:account',
                     'filters':      [ ['platform', '=', platform] ] ,
                     'params':       {'credential': delegated_credential, },
                     }
            try:
                retcod2=manifold.Update (auth, query)
            except Exception,e:
                # xxx we need a constant constant for UNKNOWN, how about using 1
                MANIFOLD_UNKNOWN=1
                retcod2={'code':MANIFOLD_UNKNOWN,'output':"%s"%e}
            if retcod2['code']==0:
                if filename: print filename,
                print 'v2 upload OK'
                return True
            #print delegated_credential, "upload failed,",retcod['output'], \
            #    "with code",retcod['code']
            # the code for V1
            try:
                retcod1=manifold.AddCredential(auth, delegated_credential, platform)
            except Exception,e:
                retcod1=e
            if retcod1==1:
                if filename: print filename,
                print 'v1 upload OK'
                return True
            # everything has failed, let's report
            if filename: print "Could not upload",filename
            else: print "Could not upload credential"
            print "  V2 Update returned code",retcod2['code'],"and error",retcod2['output']
            print "  V1 AddCredential returned code",retcod1,"(expected 1)"
            return False
        except Exception, e:
            if filename: print "Could not upload",filename,e
            else: print "Could not upload credential",e
            if self.debug:
                import traceback
                traceback.print_exc()

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
    parser.add_argument ('-d','--debug',dest='debug',action='store_true',default=False,
                         help='turn on debug mode')
    args = parser.parse_args ()
    
    uploader = ManifoldUploader (url=args.url, platform=args.platform,
                                 username=args.username, password=args.password,
                                 debug=args.debug)
    for filename in args.credential_files:
        with file(filename) as f:
            result=uploader.upload (f.read(),filename)
            if args.debug: print '... result',result

if __name__ == '__main__':
    main()
