#!/usr/bin/python
import sys
import os
import random
import string
import unittest
import sfa.util.xmlrpcprotocol as xmlrpcprotocol
from unittest import TestCase
from optparse import OptionParser
from sfa.util.xrn import get_authority
from sfa.util.config import *
from sfa.trust.certificate import *
from sfa.trust.credential import *
from sfa.trust.sfaticket import SfaTicket
from sfa.client import sfi

def random_string(size):
    return "".join(random.sample(string.letters, size))

class Client:
    registry = None
    aggregate = None
    sm = None
    cm = None
    key = None
    cert = None
    credential = None
    type = None            
    def __init__(self, options):
        try: self.config = config = Config(options.config_file)
        except:
            print "failed to read config_file %s" % options.config_file
            sys.exit(1)
        key_path = os.path.dirname(options.config_file)
        user_name = self.config.SFI_USER.split('.')[-1:][0]
        key_file = key_path + os.sep + user_name + '.pkey'
        cert_file = key_path + os.sep + user_name + '.cert'
        self.key = Keypair(filename=key_file)
        self.cert = Certificate(subject=self.config.SFI_USER)
        self.cert.set_pubkey(self.key)
        self.cert.set_issuer(self.key, self.config.SFI_USER)
        self.cert.sign()
        self.cert.save_to_file(cert_file)        
        SFI_AGGREGATE = config.SFI_SM.replace('12347', '12346')
        SFI_CM = 'http://' + options.cm_host + ':12346'
        self.registry = xmlrpcprotocol.server_proxy(config.SFI_REGISTRY, key_file, cert_file)
        self.aggregate = xmlrpcprotocol.server_proxy(SFI_AGGREGATE, key_file, cert_file)
        self.sm = xmlrpcprotocol.server_proxy(config.SFI_SM, key_file, cert_file)
        self.cm = xmlrpcprotocol.server_proxy(SFI_CM, key_file, cert_file)
        self.hrn = config.SFI_USER
        # XX defaulting to user, but this should be configurable so we can
        # test from components persepctive
        self.type = 'user'
        self.credential = self.GetCredential(self.hrn)
        
    def GetCredential(self, hrn = None, type = 'user'):
        if not hrn: hrn = self.hrn 
        if hrn == self.hrn:
            cert = self.cert.save_to_string(save_parents=True)
            request_hash = self.key.compute_hash([cert, 'user', hrn])
            credential = self.registry.get_self_credential(cert, type, hrn, request_hash)
            return credential
        else:
            if not self.credential:
                self.credential = self.GetCredential(self.hrn, 'user')
            return self.registry.GetCredential(self.credential, type, hrn)     

class BasicTestCase(unittest.TestCase):
    def __init__(self, testname, client, test_slice=None):
        unittest.TestCase.__init__(self, testname)
        self.client = client
        self.slice = test_slice
    
    def setUp(self):
        self.registry = self.client.registry
        self.aggregate = self.client.aggregate
        self.sm = self.client.sm
        self.cm = self.client.cm
        self.credential = self.client.credential
        self.hrn = self.client.hrn
        self.type = self.client.type  
                
# Registry tests
class RegistryTest(BasicTestCase):

    def setUp(self):
        """
        Make sure test records dont exsit
        """
        BasicTestCase.setUp(self)

    def testGetSelfCredential(self):
        cred = self.client.GetCredential()
        # this will raise an openssl error if the credential string isnt valid
        Credential(string=cred)

    def testRegister(self):
        authority = get_authority(self.hrn)
        auth_cred = self.client.GetCredential(authority, 'authority')
        auth_record = {'hrn': '.'.join([authority, random_string(10).lower()]),
                       'type': 'authority'}
        node_record = {'hrn': '.'.join([authority, random_string(10)]),
                       'type': 'node',
                       'hostname': random_string(6) + '.' + random_string(6)}
        slice_record = {'hrn': '.'.join([authority, random_string(10)]),
                        'type': 'slice', 'researcher': [self.hrn]}
        user_record = {'hrn': '.'.join([authority, random_string(10)]),
                       'type': 'user',
                       'email': random_string(6) +'@'+ random_string(5) +'.'+ random_string(3),
                       'first_name': random_string(7),
                       'last_name': random_string(7)}

        all_records = [auth_record, node_record, slice_record, user_record]
        for record in all_records:
            try:
                self.registry.Register(auth_cred, record)
                self.registry.Resolve(self.credential, record['hrn'])
            except:
                raise
            finally:
                try: self.registry.Remove(auth_cred, record['type'], record['hrn'])
                except: pass

    
    def testRegisterPeerObject(self):
        assert True
   
    def testUpdate(self):
        authority = get_authority(self.hrn)
        auth_cred = self.client.GetCredential(authority, 'authority')
        records = self.registry.Resolve(self.credential, self.hrn)
        if not records: assert False
        record = records[0]
        self.registry.update(auth_cred, record) 

    def testResolve(self):
        authority = get_authority(self.hrn)
        self.registry.Resolve(self.credential, self.hrn)
   
    def testRemove(self):
        authority = get_authority(self.hrn)
        auth_cred = self.client.GetCredential(authority, 'authority')
        record = {'hrn': ".".join([authority, random_string(10)]),
                       'type': 'slice'}
        self.registry.Register(auth_cred, record)
        self.registry.Remove(auth_cred, record['type'], record['hrn'])
        # should generate an exception
        try:
            self.registry.Resolve(self.credential,  record['hrn'])
            assert False
        except:       
            assert True
 
    def testRemovePeerObject(self):
        assert True

    def testList(self):
        authority = get_authority(self.client.hrn)
        self.registry.List(self.credential, authority)
             
    def testGetRegistries(self):
        self.registry.get_registries(self.credential)
    
    def testGetAggregates(self):
        self.registry.get_aggregates(self.credential)

    def testGetTrustedCerts(self):
        # this should fail unless we are a node
        callable = self.registry.get_trusted_certs
        server_exception = False 
        try:
            callable(self.credential)
        except xmlrpcprotocol.ServerException:
            server_exception = True
        finally:
            if self.type in ['user'] and not server_exception:
                assert False
            

class AggregateTest(BasicTestCase):
    def setUp(self):
        BasicTestCase.setUp(self)
        
    def testGetSlices(self):
        self.aggregate.ListSlices(self.credential)

    def testGetResources(self):
        # available resources
        agg_rspec = self.aggregate.get_resources(self.credential)
        # resources used by a slice
        slice_rspec = self.aggregate.get_resources(self.credential, self.slice['hrn'])
        # will raise an exception if the rspec isnt valid
        RSpec(xml=agg_rspec)
        RSpec(xml=slice_rspec)

    def testCreateSlice(self):
        # get availabel resources   
        rspec = self.aggregate.get_resources(self.credential)
        slice_credential = self.client.GetCredential(self.slice['hrn'], 'slice')
        self.aggregate.CreateSliver(slice_credential, self.slice['hrn'], rspec)

    def testDeleteSlice(self):
        slice_credential = self.client.GetCredential(self.slice['hrn'], 'slice')
        self.aggregate.DeleteSliver(slice_credential, self.slice['hrn'],"call-id-delete-slice")

    def testGetTicket(self):
        slice_credential = self.client.GetCredential(self.slice['hrn'], 'slice')
        rspec = self.aggregate.get_resources(self.credential)
        ticket = self.aggregate.GetTicket(slice_credential, self.slice['hrn'], rspec)
        # will raise an exception if the ticket inst valid
        SfaTicket(string=ticket)        

class SlicemgrTest(AggregateTest):
    def setUp(self):
        AggregateTest.setUp(self)
        
        # force calls to go through slice manager   
        self.aggregate = self.sm

        # get the slice credential
        

class ComponentTest(BasicTestCase):
    def setUp(self):
        BasicTestCase.setUp(self)
        self.slice_cred = self.client.GetCredential(self.slice['hrn'], 'slice')

    def testStartSlice(self):
        self.cm.start_slice(self.slice_cred, self.slice['hrn'])

    def testStopSlice(self):
        self.cm.stop_slice(self.slice_cred, self.slice['hrn'])

    def testDeleteSlice(self):
        self.cm.DeleteSliver(self.slice_cred, self.slice['hrn'],"call-id-delete-slice-cm")

    def testRestartSlice(self):
        self.cm.restart_slice(self.slice_cred, self.slice['hrn'])

    def testGetSlices(self):
        self.cm.ListSlices(self.slice_cred, self.slice['hrn'])

    def testRedeemTicket(self):
        rspec = self.aggregate.get_resources(self.credential)
        ticket = self.aggregate.GetTicket(slice_cred, self.slice['hrn'], rspec)
        self.cm.redeem_ticket(slice_cred, ticket)


def test_names(testcase):
    return [name for name in dir(testcase) if name.startswith('test')]

def CreateSliver(client):
    # register a slice that will be used for some test
    authority = get_authority(client.hrn)
    auth_cred = client.GetCredential(authority, 'authority')
    slice_record = {'hrn': ".".join([authority, random_string(10)]),
                    'type': 'slice', 'researcher': [client.hrn]}
    client.registry.Register(auth_cred, slice_record)
    return  slice_record
 
def DeleteSliver(client, slice):
    authority = get_authority(client.hrn)
    auth_cred = client.GetCredential(authority, 'authority')
    if slice:
        client.registry.Remove(auth_cred, 'slice', slice['hrn'])
    
if __name__ == '__main__':

    args = sys.argv
    prog_name = args[0]
    default_config_dir = os.path.expanduser('~/.sfi/sfi_config')
    default_cm = "echo.cs.princeton.edu"
    parser = OptionParser(usage="%(prog_name)s [options]" % locals())
    parser.add_option('-f', '--config_file', dest='config_file', default=default_config_dir,
                      help='config file. default is %s' % default_config_dir)
    parser.add_option('-r', '--registry', dest='registry', action='store_true',
                      default=False, help='run registry tests')
    parser.add_option('-a', '--aggregate', dest='aggregate', action='store_true',
                      default=False, help='run aggregate tests')
    parser.add_option('-s', '--slicemgr', dest='slicemgr', action='store_true',
                      default=False, help='run slicemgr tests')
    parser.add_option('-c', '--component', dest='component', action='store_true',
                      default=False, help='run component tests')
    parser.add_option('-d', '--cm_host', dest='cm_host', default=default_cm, 
                      help='dns name of component to test. default is %s' % default_cm)
    parser.add_option('-A', '--all', dest='all', action='store_true',
                      default=False, help='run component tests')
    
    options, args = parser.parse_args()
    suite = unittest.TestSuite()
    client = Client(options)
    test_slice = {}
    
    # create the test slice if necessary
    if options.all or options.slicemgr or options.aggregate \
       or options.component:
        test_slice = CreateSliver(client)

    if options.registry or options.all:
        for name in test_names(RegistryTest):
            suite.addTest(RegistryTest(name, client))

    if options.aggregate or options.all: 
        for name in test_names(AggregateTest):
            suite.addTest(AggregateTest(name, client, test_slice))

    if options.slicemgr or options.all: 
        for name in test_names(SlicemgrTest):
            suite.addTest(SlicemgrTest(name, client, test_slice))

    if options.component or options.all: 
        for name in test_names(ComponentTest):
            suite.addTest(ComponentTest(name, client, test_slice))
    
    # run tests 
    unittest.TextTestRunner(verbosity=2).run(suite)

    # remove teset slice
    DeleteSliver(client, test_slice)
