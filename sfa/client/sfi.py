#! /usr/bin/env python

# sfi -- slice-based facility interface

import sys
sys.path.append('.')
import os, os.path
import tempfile
import traceback
import socket
import random
import datetime
from lxml import etree
from StringIO import StringIO
from types import StringTypes, ListType
from optparse import OptionParser
from sfa.trust.certificate import Keypair, Certificate
from sfa.trust.credential import Credential
from sfa.util.sfaticket import SfaTicket
from sfa.util.record import *
from sfa.util.namespace import *
from sfa.util.xmlrpcprotocol import ServerException
import sfa.util.xmlrpcprotocol as xmlrpcprotocol
from sfa.util.config import Config
import zlib

AGGREGATE_PORT=12346
CM_PORT=12346

# utility methods here
# display methods
def display_rspec(rspec, format='rspec'):
    if format in ['dns']:
        tree = etree.parse(StringIO(rspec))
        root = tree.getroot()
        result = root.xpath("./network/site/node/hostname/text()")
    elif format in ['ip']:
        # The IP address is not yet part of the new RSpec
        # so this doesn't do anything yet.
        tree = etree.parse(StringIO(rspec))
        root = tree.getroot()
        result = root.xpath("./network/site/node/ipv4/text()")
    else:
        result = rspec

    print result
    return

def display_list(results):
    for result in results:
        print result


def display_records(recordList, dump=False):
    ''' Print all fields in the record'''
    for record in recordList:
        display_record(record, dump)

def display_record(record, dump=False):
    if dump:
        record.dump()
    else:
        info = record.getdict()
        print "%s (%s)" % (info['hrn'], info['type'])
    return


def filter_records(type, records):
    filtered_records = []
    for record in records:
        if (record['type'] == type) or (type == "all"):
            filtered_records.append(record)
    return filtered_records


# save methods
def save_rspec_to_file(rspec, filename):
    if not filename.endswith(".rspec"):
        filename = filename + ".rspec"

    f = open(filename, 'w')
    f.write(rspec)
    f.close()
    return

def save_records_to_file(filename, recordList):
    index = 0
    for record in recordList:
        if index > 0:
            save_record_to_file(filename + "." + str(index), record)
        else:
            save_record_to_file(filename, record)
        index = index + 1

def save_record_to_file(filename, record):
    if record['type'] in ['user']:
        record = UserRecord(dict=record)
    elif record['type'] in ['slice']:
        record = SliceRecord(dict=record)
    elif record['type'] in ['node']:
        record = NodeRecord(dict=record)
    elif record['type'] in ['authority', 'ma', 'sa']:
        record = AuthorityRecord(dict=record)
    else:
        record = SfaRecord(dict=record)
    str = record.save_to_string()
    file(filename, "w").write(str)
    return


# load methods
def load_record_from_file(filename):
    str = file(filename, "r").read()
    record = SfaRecord(string=str)
    return record



class Sfi:

    geni_am = None
    slicemgr = None
    registry = None
    user = None
    authority = None
    options = None
    hashrequest = False
   
    def create_cmd_parser(self, command, additional_cmdargs=None):
        cmdargs = {"gid": "",
                  "list": "name",
                  "show": "name",
                  "remove": "name",
                  "add": "record",
                  "update": "record",
                  "aggregates": "[name]",
                  "registries": "[name]",
                  "slices": "",
                  "resources": "[name]",
                  "create": "name rspec",
                  "get_trusted_certs": "cred",
                  "get_ticket": "name rspec",
                  "redeem_ticket": "ticket",
                  "delete": "name",
                  "reset": "name",
                  "start": "name",
                  "stop": "name",
                  "delegate": "name",
                  "GetVersion": "name",
                  "ListResources": "name",
                  "CreateSliver": "name",
                  "get_geni_aggregates": "name",
                  "DeleteSliver": "name",
                  "SliverStatus": "name",
                  "RenewSliver": "name",
                  "Shutdown": "name"
                 }

        if additional_cmdargs:
            cmdargs.update(additional_cmdargs)

        if command not in cmdargs:
            print "Invalid command\n"
            print "Commands: ",
            for key in cmdargs.keys():
                print key + ",",
            print ""
            sys.exit(2)

        parser = OptionParser(usage="sfi [sfi_options] %s [options] %s" \
                                     % (command, cmdargs[command]))

        if command in ("resources"):
            parser.add_option("-f", "--format", dest="format", type="choice",
                             help="display format ([xml]|dns|ip)", default="xml",
                             choices=("xml", "dns", "ip"))
                                
        if command in ("resources", "slices", "create", "delete", "start", "stop", "get_ticket"):
            parser.add_option("-a", "--aggregate", dest="aggregate",
                             default=None, help="aggregate host")
            parser.add_option("-p", "--port", dest="port",
                             default=AGGREGATE_PORT, help="aggregate port")

        if command in ("start", "stop", "reset", "delete", "slices"):
            parser.add_option("-c", "--component", dest="component", default=None,
                             help="component hrn")
            
        if command in ("list", "show", "remove"):
            parser.add_option("-t", "--type", dest="type", type="choice",
                            help="type filter ([all]|user|slice|sa|ma|node|aggregate)",
                            choices=("all", "user", "slice", "sa", "ma", "node", "aggregate"),
                            default="all")

        if command in ("resources", "show", "list"):
           parser.add_option("-o", "--output", dest="file",
                            help="output XML to file", metavar="FILE", default=None)
        
        if command in ("show", "list"):
           parser.add_option("-f", "--format", dest="format", type="choice",
                             help="display format ([text]|xml)", default="text",
                             choices=("text", "xml"))

        if command in ("delegate"):
           parser.add_option("-u", "--user",
                            action="store_true", dest="delegate_user", default=False,
                            help="delegate user credential")
           parser.add_option("-s", "--slice", dest="delegate_slice",
                            help="delegate slice credential", metavar="HRN", default=None)
        
        return parser

        
    def create_parser(self):

        # Generate command line parser
        parser = OptionParser(usage="sfi [options] command [command_options] [command_args]",
                             description="Commands: gid,list,show,remove,add,update,nodes,slices,resources,create,delete,start,stop,reset")
        parser.add_option("-g", "--geni_am", dest="geni_am",
                          help="geni am", metavar="URL", default=None)
        parser.add_option("-r", "--registry", dest="registry",
                         help="root registry", metavar="URL", default=None)
        parser.add_option("-s", "--slicemgr", dest="sm",
                         help="slice manager", metavar="URL", default=None)
        default_sfi_dir = os.path.expanduser("~/.sfi/")
        parser.add_option("-d", "--dir", dest="sfi_dir",
                         help="config & working directory - default is " + default_sfi_dir,
                         metavar="PATH", default=default_sfi_dir)
        parser.add_option("-u", "--user", dest="user",
                         help="user name", metavar="HRN", default=None)
        parser.add_option("-a", "--auth", dest="auth",
                         help="authority name", metavar="HRN", default=None)
        parser.add_option("-v", "--verbose",
                         action="store_true", dest="verbose", default=False,
                         help="verbose mode")
        parser.add_option("-D", "--debug",
                          action="store_true", dest="debug", default=False,
                          help="Debug (xml-rpc) protocol messages")
        parser.add_option("-p", "--protocol",
                         dest="protocol", default="xmlrpc",
                         help="RPC protocol (xmlrpc or soap)")
        parser.add_option("-k", "--hashrequest",
                         action="store_true", dest="hashrequest", default=False,
                         help="Create a hash of the request that will be authenticated on the server")
        parser.disable_interspersed_args()

        return parser
        
 
    #
    # Establish Connection to SliceMgr and Registry Servers
    #
    def set_servers(self):
       config_file = self.options.sfi_dir + os.sep + "sfi_config"
       try:
          config = Config (config_file)
       except:
          print "Failed to read configuration file", config_file
          print "Make sure to remove the export clauses and to add quotes"
          if not self.options.verbose:
             print "Re-run with -v for more details"
          else:
             traceback.print_exc()
          sys.exit(1)
    
       errors = 0
       # Set SliceMgr URL
       if (self.options.sm is not None):
          sm_url = self.options.sm
       elif hasattr(config, "SFI_SM"):
          sm_url = config.SFI_SM
       else:
          print "You need to set e.g. SFI_SM='http://your.slicemanager.url:12347/' in %s" % config_file
          errors += 1 
    
       # Set Registry URL
       if (self.options.registry is not None):
          reg_url = self.options.registry
       elif hasattr(config, "SFI_REGISTRY"):
          reg_url = config.SFI_REGISTRY
       else:
          print "You need to set e.g. SFI_REGISTRY='http://your.registry.url:12345/' in %s" % config_file
          errors += 1 
          

       if (self.options.geni_am is not None):
           geni_am_url = self.options.geni_am
       elif hasattr(config, "SFI_GENI_AM"):
           geni_am_url = config.SFI_GENI_AM
           
       # Set user HRN
       if (self.options.user is not None):
          self.user = self.options.user
       elif hasattr(config, "SFI_USER"):
          self.user = config.SFI_USER
       else:
          print "You need to set e.g. SFI_USER='plc.princeton.username' in %s" % config_file
          errors += 1 
    
       # Set authority HRN
       if (self.options.auth is not None):
          self.authority = self.options.auth
       elif hasattr(config, "SFI_AUTH"):
          self.authority = config.SFI_AUTH
       else:
          print "You need to set e.g. SFI_AUTH='plc.princeton' in %s" % config_file
          errors += 1 
    
       if errors:
          sys.exit(1)
    
       if self.options.verbose :
          print "Contacting Slice Manager at:", sm_url
          print "Contacting Registry at:", reg_url
    
       # Get key and certificate
       key_file = self.get_key_file()
       cert_file = self.get_cert_file(key_file)
       self.key = Keypair(filename=key_file) 
       self.key_file = key_file
       self.cert_file = cert_file
       self.cert = Certificate(filename=cert_file) 
       # Establish connection to server(s)
       self.registry = xmlrpcprotocol.get_server(reg_url, key_file, cert_file, self.options.debug)  
       self.slicemgr = xmlrpcprotocol.get_server(sm_url, key_file, cert_file, self.options.debug)
       self.geni_am = xmlrpcprotocol.get_server(geni_am_url, key_file, cert_file, self.options.debug)

       return
    
    #
    # Get various credential and spec files
    #
    # Establishes limiting conventions
    #   - conflates MAs and SAs
    #   - assumes last token in slice name is unique
    #
    # Bootstraps credentials
    #   - bootstrap user credential from self-signed certificate
    #   - bootstrap authority credential from user credential
    #   - bootstrap slice credential from user credential
    #
    
    
    def get_key_file(self):
       file = os.path.join(self.options.sfi_dir, self.user.replace(self.authority + '.', '') + ".pkey")
       #file = os.path.join(self.options.sfi_dir, get_leaf(self.user) + ".pkey")
       if (os.path.isfile(file)):
          return file
       else:
          print "Key file", file, "does not exist"
          sys.exit(-1)
       return
    
    def get_cert_file(self, key_file):
    
       #file = os.path.join(self.options.sfi_dir, get_leaf(self.user) + ".cert")
       file = os.path.join(self.options.sfi_dir, self.user.replace(self.authority + '.', '') + ".cert")
       if (os.path.isfile(file)):
          return file
       else:
          k = Keypair(filename=key_file)
          cert = Certificate(subject=self.user)
          cert.set_pubkey(k)
          cert.set_issuer(k, self.user)
          cert.sign()
          if self.options.verbose :
             print "Writing self-signed certificate to", file
          cert.save_to_file(file)
          return file
   
    def get_gid(self):
        #file = os.path.join(self.options.sfi_dir, get_leaf(self.user) + ".gid")
        file = os.path.join(self.options.sfi_dir, self.user.replace(self.authority + '.', '') + ".gid")
        if (os.path.isfile(file)):
            gid = GID(filename=file)
            return gid
        else:
            cert_str = self.cert.save_to_string(save_parents=True)
            gid_str = self.registry.get_gid(cert_str, self.user, "user")
            gid = GID(string=gid_str)
            if self.options.verbose:
                print "Writing user gid to", file
            gid.save_to_file(file, save_parents=True)
            return gid       

    def get_cached_credential(self, file):
        """
        Return a cached credential only if it hasn't expired.
        """
        if (os.path.isfile(file)):
            credential = Credential(filename=file)
            # make sure it isnt expired 
            if not credential.get_lifetime or \
               datetime.datetime.today() < credential.get_lifefime():
                return credential
        return None 
 
    def get_user_cred(self):
        #file = os.path.join(self.options.sfi_dir, get_leaf(self.user) + ".cred")
        file = os.path.join(self.options.sfi_dir, self.user.replace(self.authority + '.', '') + ".cred")

        user_cred = self.get_cached_credential(file)
        if user_cred:
            return user_cred
        else:
            # bootstrap user credential
            cert_string = self.cert.save_to_string(save_parents=True)
            user_name = self.user.replace(self.authority + ".", '')
            if user_name.count(".") > 0:
                user_name = user_name.replace(".", '_')
                self.user = self.authority + "." + user_name

            user_cred = self.registry.get_self_credential(cert_string, "user", self.user)
            if user_cred:
               cred = Credential(string=user_cred)
               cred.save_to_file(file, save_parents=True)
               if self.options.verbose:
                    print "Writing user credential to", file
               return cred
            else:
               print "Failed to get user credential"
               sys.exit(-1)
  
    def get_auth_cred(self):
        if not self.authority:
            print "no authority specified. Use -a or set SF_AUTH"
            sys.exit(-1)
    
        file = os.path.join(self.options.sfi_dir, get_leaf("authority") + ".cred")
        auth_cred = self.get_cached_credential(file)
        if auth_cred:
            return auth_cred
        else:
            # bootstrap authority credential from user credential
            user_cred = self.get_user_cred().save_to_string(save_parents=True)
            auth_cred = self.registry.get_credential(user_cred, "authority", self.authority)
            if auth_cred:
                cred = Credential(string=auth_cred)
                cred.save_to_file(file, save_parents=True)
                if self.options.verbose:
                    print "Writing authority credential to", file
                return cred
            else:
                print "Failed to get authority credential"
                sys.exit(-1)
    
    def get_slice_cred(self, name):
        file = os.path.join(self.options.sfi_dir, "slice_" + get_leaf(name) + ".cred")
        slice_cred = self.get_cached_credential(file)
        if slice_cred:
            return slice_cred
        else:
            # bootstrap slice credential from user credential
            user_cred = self.get_user_cred().save_to_string(save_parents=True)
            arg_list = [user_cred, "slice", name]
            slice_cred_str = self.registry.get_credential(user_cred, "slice", name)
            if slice_cred_str:
                slice_cred = Credential(string=slice_cred_str)
                slice_cred.save_to_file(file, save_parents=True)
                if self.options.verbose:
                    print "Writing slice credential to", file
                return slice_cred
            else:
                print "Failed to get slice credential"
                sys.exit(-1)
    
    def delegate_cred(self, cred, hrn, type='authority'):
        # the gid and hrn of the object we are delegating
        user_cred = Credential(string=cred)
        object_gid = user_cred.get_gid_object()
        object_hrn = object_gid.get_hrn()
        #cred.set_delegate(True)
        #if not cred.get_delegate():
        #    raise Exception, "Error: Object credential %(object_hrn)s does not have delegate bit set" % locals()
           
    
        records = self.registry.resolve(cred, hrn)
        records = filter_records(type, records)
        
        if not records:
            raise Exception, "Error: Didn't find a %(type)s record for %(hrn)s" % locals()
    
        # the gid of the user who will be delegated too
        record = SfaRecord(dict=records[0])
        delegee_gid = record.get_gid_object()
        delegee_hrn = delegee_gid.get_hrn()
        
        # the key and hrn of the user who will be delegating
        user_key = Keypair(filename=self.get_key_file())
        user_hrn = user_cred.get_gid_caller().get_hrn()
    
        dcred = Credential(subject=object_hrn + " delegated to " + delegee_hrn)
        dcred.set_gid_caller(delegee_gid)
        dcred.set_gid_object(object_gid)
        dcred.set_privileges(user_cred.get_privileges())
        dcred.get_privileges().delegate_all_privileges(True)
        

        # Save the issuer's gid to a file
        fname = self.options.sfi_dir + os.sep + "gid_%d" % random.randint(0, 999999999)
        f = open(fname, "w")
        f.write(user_cred.get_gid_caller().save_to_string())
        f.close()
        dcred.set_issuer_keys(self.get_key_file(), fname)
        os.remove(fname)
        
        dcred.set_parent(user_cred)
        dcred.encode()
        dcred.sign()
    
        return dcred.save_to_string(save_parents=True)
    
    def get_rspec_file(self, rspec):
       if (os.path.isabs(rspec)):
          file = rspec
       else:
          file = os.path.join(self.options.sfi_dir, rspec)
       if (os.path.isfile(file)):
          return file
       else:
          print "No such rspec file", rspec
          sys.exit(1)
    
    def get_record_file(self, record):
       if (os.path.isabs(record)):
          file = record
       else:
          file = os.path.join(self.options.sfi_dir, record)
       if (os.path.isfile(file)):
          return file
       else:
          print "No such registry record file", record
          sys.exit(1)
    
    def load_publickey_string(self, fn):
       f = file(fn, "r")
       key_string = f.read()
    
       # if the filename is a private key file, then extract the public key
       if "PRIVATE KEY" in key_string:
           outfn = tempfile.mktemp()
           cmd = "openssl rsa -in " + fn + " -pubout -outform PEM -out " + outfn
           os.system(cmd)
           f = file(outfn, "r")
           key_string = f.read()
           os.remove(outfn)
    
       return key_string

    def get_component_server_from_hrn(self, hrn):
        # direct connection to the nodes component manager interface
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        records = self.registry.resolve(user_cred, hrn)
        records = filter_records('node', records)
        if not records:
            print "No such component:", opts.component
        record = records[0]
  
        return self.get_server(record['hostname'], CM_PORT, self.key_file, \
                               self.cert_file, self.options.debug)
 
    def get_server(self, host, port, keyfile, certfile, debug):
        """
        Return an instnace of an xmlrpc server connection    
        """
        url = "http://%s:%s" % (host, port)
        return xmlrpcprotocol.get_server(url, keyfile, certfile, debug)
 
    #==========================================================================
    # Following functions implement the commands
    #
    # Registry-related commands
    #==========================================================================
  
    def dispatch(self, command, cmd_opts, cmd_args):
        getattr(self, command)(cmd_opts, cmd_args)
 
    def gid(self, opts, args):
        gid = self.get_gid()
        print "GID: %s" % (gid.save_to_string(save_parents=True))
        return   
 
    # list entires in named authority registry
    def list(self, opts, args):
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        hrn = args[0]
        try:
            list = self.registry.list(user_cred, hrn)
        except IndexError:
            raise Exception, "Not enough parameters for the 'list' command"
          
        # filter on person, slice, site, node, etc.  
        # THis really should be in the self.filter_records funct def comment...
        list = filter_records(opts.type, list)
        for record in list:
            print "%s (%s)" % (record['hrn'], record['type'])     
        if opts.file:
            file = opts.file
            if not file.startswith(os.sep):
                file = os.path.join(self.options.sfi_dir, file)
            save_records_to_file(file, list)
        return
    
    # show named registry record
    def show(self, opts, args):
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        hrn = args[0]
        records = self.registry.resolve(user_cred, hrn)
        records = filter_records(opts.type, records)
        if not records:
            print "No record of type", opts.type
        for record in records:
            if record['type'] in ['user']:
                record = UserRecord(dict=record)
            elif record['type'] in ['slice']:
                record = SliceRecord(dict=record)
            elif record['type'] in ['node']:
                record = NodeRecord(dict=record)
            elif record['type'] in ['authority', 'ma', 'sa']:
                record = AuthorityRecord(dict=record)
            else:
                record = SfaRecord(dict=record)
            if (opts.format == "text"): 
                record.dump()  
            else:
                print record.save_to_string() 
       
        if opts.file:
            file = opts.file
            if not file.startswith(os.sep):
                file = os.path.join(self.options.sfi_dir, file)
            save_records_to_file(file, records)
        return
    
    def delegate(self, opts, args):
       user_cred = self.get_user_cred()
       if opts.delegate_user:
           object_cred = user_cred
       elif opts.delegate_slice:
           object_cred = self.get_slice_cred(opts.delegate_slice)
       else:
           print "Must specify either --user or --slice <hrn>"
           return
    
       # the gid and hrn of the object we are delegating
       object_gid = object_cred.get_gid_object()
       object_hrn = object_gid.get_hrn()
    
       if not object_cred.get_privileges().get_all_delegate():
           print "Error: Object credential", object_hrn, "does not have delegate bit set"
           return
    
       records = self.registry.resolve(user_cred.save_to_string(save_parents=True), args[0])
       records = filter_records("user", records)
    
       if not records:
           print "Error: Didn't find a user record for", args[0]
           return
    
       # the gid of the user who will be delegated to
       delegee_gid = GID(string=records[0]['gid'])
       delegee_hrn = delegee_gid.get_hrn()
   
       # the key and hrn of the user who will be delegating
       user_key = Keypair(filename=self.get_key_file())
       user_hrn = user_cred.get_gid_caller().get_hrn()
       subject_string = "%s delegated to %s" % (object_hrn, delegee_hrn)
       dcred = Credential(subject=subject_string)
       dcred.set_gid_caller(delegee_gid)
       dcred.set_gid_object(object_gid)
       privs = object_cred.get_privileges()
       dcred.set_privileges(object_cred.get_privileges())
       dcred.get_privileges().delegate_all_privileges(True)
       dcred.set_pubkey(object_gid.get_pubkey())
       dcred.set_issuer(user_key, user_hrn)
       dcred.set_parent(object_cred)
       dcred.encode()
       dcred.sign()
    
       if opts.delegate_user:
           dest_fn = os.path.join(self.options.sfi_dir, get_leaf(delegee_hrn) + "_" 
                                  + get_leaf(object_hrn) + ".cred")
       elif opts.delegate_slice:
           dest_fn = os.path_join(self.options.sfi_dir, get_leaf(delegee_hrn) + "_slice_" 
                                  + get_leaf(object_hrn) + ".cred")
    
       dcred.save_to_file(dest_fn, save_parents=True)
    
       print "delegated credential for", object_hrn, "to", delegee_hrn, "and wrote to", dest_fn
    
    # removed named registry record
    #   - have to first retrieve the record to be removed
    def remove(self, opts, args):
        auth_cred = self.get_auth_cred().save_to_string(save_parents=True)
        hrn = args[0]
        type = opts.type 
        if type in ['all']:
            type = '*'
        return self.registry.remove(auth_cred, type, hrn)
    
    # add named registry record
    def add(self, opts, args):
        auth_cred = self.get_auth_cred().save_to_string(save_parents=True)
        record_filepath = args[0]
        rec_file = self.get_record_file(record_filepath)
        record = load_record_from_file(rec_file).as_dict()
        return self.registry.register(auth_cred, record)
    
    # update named registry entry
    def update(self, opts, args):
        user_cred = self.get_user_cred()
        rec_file = self.get_record_file(args[0])
        record = load_record_from_file(rec_file)
        if record['type'] == "user":
            if record.get_name() == user_cred.get_gid_object().get_hrn():
                cred = user_cred.save_to_string(save_parents=True)
            else:
                cred = self.get_auth_cred().save_to_string(save_parents=True)
        elif record['type'] in ["slice"]:
            try:
                cred = self.get_slice_cred(record.get_name()).save_to_string(save_parents=True)
            except ServerException, e:
               # XXX smbaker -- once we have better error return codes, update this
               # to do something better than a string compare
               if "Permission error" in e.args[0]:
                   cred = self.get_auth_cred().save_to_string(save_parents=True)
               else:
                   raise
        elif record.get_type() in ["authority"]:
            cred = self.get_auth_cred().save_to_string(save_parents=True)
        elif record.get_type() == 'node':
            cred = self.get_auth_cred().save_to_string(save_parents=True)
        else:
            raise "unknown record type" + record.get_type()
        record = record.as_dict()
        return self.registry.update(cred, record)
  
    def get_trusted_certs(self, opts, args):
        """
        return the trusted certs at this interface 
        """ 
        trusted_certs = self.registry.get_trusted_certs()
        for trusted_cert in trusted_certs:
            cert = Certificate(string=trusted_cert)
            print cert.get_subject()
        return 

    def aggregates(self, opts, args):
        """
        return a list of details about known aggregates
        """
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        hrn = None
        if args:
            hrn = args[0]

        result = self.registry.get_aggregates(user_cred, hrn)
        display_list(result)
        return 

    def get_geni_aggregates(self, opts, args):
        """
        return a list of details about known aggregates
        """
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        hrn = None
        if args:
            hrn = args[0]

        result = self.registry.get_geni_aggregates(user_cred, hrn)
        display_list(result)
        return 


    def registries(self, opts, args):
        """
        return a list of details about known registries
        """
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        hrn = None
        if args:
            hrn = args[0]
        result = self.registry.get_registries(user_cred, hrn)
        display_list(result)
        return

 
    # ==================================================================
    # Slice-related commands
    # ==================================================================
    

    # list instantiated slices
    def slices(self, opts, args):
        """
        list instantiated slices
        """
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        server = self.slicemgr
        if opts.aggregate:
            server = self.get_server(opts.aggregate, opts.port, self.key_file, \
                                     self.cert_file, self.options.debug)
        # direct connection to the nodes component manager interface
        if opts.component:
            server = self.get_component_server_from_hrn(opts.component)
        results = server.get_slices(user_cred)
        display_list(results)
        return
    
    # show rspec for named slice
    def resources(self, opts, args):
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        server = self.slicemgr
        if opts.aggregate:
            server = self.get_server(opts.aggregate, opts.port, self.key_file, \
                                     self.cert_file, self.options.debug)
        if args:
            cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
            hrn = args[0]
        else:
            cred = user_cred
            hrn = None

        result = server.get_resources(cred, hrn)
        format = opts.format
       
        display_rspec(result, format)
        if (opts.file is not None):
            file = opts.file
            if not file.startswith(os.sep):
                file = os.path.join(self.options.sfi_dir, file)
            save_rspec_to_file(result, file)
        return
    
    # created named slice with given rspec
    def create(self, opts, args):
        slice_hrn = args[0]
        user_cred = self.get_user_cred()
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        rspec_file = self.get_rspec_file(args[1])
        rspec = open(rspec_file).read()
        server = self.slicemgr

        if opts.aggregate:
            server = self.get_server(opts.aggregate, opts.port, self.key_file, \
                                     self.cert_file, self.options.debug)

        return server.create_slice(slice_cred, slice_hrn, rspec)

    # get a ticket for the specified slice
    def get_ticket(self, opts, args):
        slice_hrn, rspec_path = args[0], args[1]
        user_cred = self.get_user_cred()
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        rspec_file = self.get_rspec_file(rspec_path) 
        rspec = open(rspec_file).read()
        server = self.slicemgr
        if opts.aggregate:
            server = self.get_server(opts.aggregate, opts.port, self.key_file, \
                                     self.cert_file, self.options.debug)
        ticket_string = server.get_ticket(slice_cred, slice_hrn, rspec)
        file = os.path.join(self.options.sfi_dir, get_leaf(slice_hrn) + ".ticket")
        print "writing ticket to ", file        
        ticket = SfaTicket(string=ticket_string)
        ticket.save_to_file(filename=file, save_parents=True)

    def redeem_ticket(self, opts, args):
        ticket_file = args[0]
        
        # get slice hrn from the ticket
        # use this to get the right slice credential 
        ticket = SfaTicket(filename=ticket_file)
        ticket.decode()
        slice_hrn = ticket.gidObject.get_hrn()
        #slice_hrn = ticket.attributes['slivers'][0]['hrn']
        user_cred = self.get_user_cred()
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        
        # get a list of node hostnames from the RSpec 
        tree = etree.parse(StringIO(ticket.rspec))
        root = tree.getroot()
        hostnames = root.xpath("./network/site/node/hostname/text()")
        
        # create an xmlrpc connection to the component manager at each of these
        # components and gall redeem_ticket
        connections = {}
        for hostname in hostnames:
            try:
                print "Calling redeem_ticket at %(hostname)s " % locals(),
                server = self.get_server(hostname, CM_PORT, self.key_file, \
                                         self.cert_file, self.options.debug)
                server.redeem_ticket(slice_cred, ticket.save_to_string(save_parents=True))
                print "Success"
            except socket.gaierror:
                print "Failed:",
                print "Componet Manager not accepting requests" 
            except Exception, e:
                print "Failed:", e.message
        return
 
    # delete named slice
    def delete(self, opts, args):
        slice_hrn = args[0]
        server = self.slicemgr
        if opts.aggregate:
            server = self.get_server(opts.aggregate, opts.port, self.key_file, \
                                     self.cert_file, self.options.debug)
        # direct connection to the nodes component manager interface
        if opts.component:
            server = self.get_component_server_from_hrn(opts.component)
        slice_cred = self.get_slice_cred(slice_hrn).save_to_string(save_parents=True)
        return server.delete_slice(slice_cred, slice_hrn)
    
    # start named slice
    def start(self, opts, args):
        slice_hrn = args[0]
        server = self.slicemgr
        # direct connection to an aggregagte
        if opts.aggregate:
            server = self.get_server(opts.aggregate, opts.port, self.key_file, \
                                     self.cert_file, self.options.debug)
        if opts.component:
            server = self.get_component_server_from_hrn(opts.component)
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        return server.start_slice(slice_cred, slice_hrn)
    
    # stop named slice
    def stop(self, opts, args):
        slice_hrn = args[0]
        server = self.slicemgr
        # direct connection to an aggregate
        if opts.aggregate:
            server = self.get_server(opts.aggregate, opts.port, self.key_file, \
                                     self.cert_file, self.options.debug)
        # direct connection to the nodes component manager interface
        if opts.component:
            server = self.get_component_server_from_hrn(opts.component)
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        return server.stop_slice(slice_cred, slice_hrn)
    
    # reset named slice
    def reset(self, opts, args):
        slice_hrn = args[0]
        server = self.slicemgr
        # direct connection to the nodes component manager interface
        if opts.component:
            server = self.get_component_server_from_hrn(opts.component)
        slice_cred = self.get_slice_cred(args[0]).save_to_string(save_parents=True)
        return server.reset_slice(slice_cred, slice_hrn)


    # =====================================================================
    # GENI AM related calls
    # =====================================================================

    def GetVersion(self, opts, args):
        server = self.geni_am
        print server.GetVersion()

    def ListResources(self, opts, args):
        user_cred = self.get_user_cred().save_to_string(save_parents=True)
        server = self.geni_am
        call_options = {'geni_compressed': True}
        xrn = None
        cred = user_cred
        if args:
            xrn = args[0]
            cred = self.get_slice_cred(xrn).save_to_string(save_parents=True)

        if xrn:
            call_options['geni_slice_urn'] = xrn
            
        rspec = server.ListResources([cred], call_options)
        rspec = zlib.decompress(rspec.decode('base64'))
        print rspec
        
    def CreateSliver(self, opts, args):
        slice_xrn = args[0]
        slice_cred = self.get_slice_cred(slice_xrn).save_to_string(save_parents=True)
        rspec_file = self.get_rspec_file(args[1])
        rspec = open(rspec_file).read()
        server = self.geni_am
        return server.CreateSliver(slice_xrn, [slice_cred], rspec, [])
    
    def DeleteSliver(self, opts, args):
        slice_xrn = args[0]
        slice_cred = self.get_slice_cred(slice_xrn).save_to_string(save_parents=True)
        server = self.geni_am
        return server.DeleteSliver(slice_xrn, [slice_cred])    

    def SliverStatus(self, opts, args):
        slice_xrn = args[0]
        slice_cred = self.get_slice_cred(slice_xrn).save_to_string(save_parents=True)
        server = self.geni_am
        print server.SliverStatus(slice_xrn, [slice_cred])
    
    def RenewSliver(self, opts, args):
        slice_xrn = args[0]
        slice_cred = self.get_slice_cred(slice_xrn).save_to_string(save_parents=True)
        time = args[1]
        server = self.geni_am
        return server.RenewSliver(slice_xrn, [slice_cred], time)   

    def Shutdown(self, opts, args):
        slice_xrn = args[0]
        slice_cred = self.get_slice_cred(slice_xrn).save_to_string(save_parents=True)
        server = self.geni_am
        return server.Shutdown(slice_xrn, [slice_cred])         
    
    #
    # Main: parse arguments and dispatch to command
    #
    def main(self):
        parser = self.create_parser()
        (options, args) = parser.parse_args()
        self.options = options
   
        if options.hashrequest:
            self.hashrequest = True
 
        if len(args) <= 0:
            print "No command given. Use -h for help."
            return - 1
    
        command = args[0]
        (cmd_opts, cmd_args) = self.create_cmd_parser(command).parse_args(args[1:])
        if self.options.verbose :
            print "Registry %s, sm %s, dir %s, user %s, auth %s" % (options.registry, options.sm,
                                                                   options.sfi_dir, options.user,
                                                                   options.auth)
            print "Command %s" % command
            if command in ("resources"):
                print "resources cmd_opts %s" % cmd_opts.format
            elif command in ("list", "show", "remove"):
                print "cmd_opts.type %s" % cmd_opts.type
            print "cmd_args %s" % cmd_args
    
        self.set_servers()
    
        try:
            self.dispatch(command, cmd_opts, cmd_args)
        except KeyError:
            raise 
            print "Command not found:", command
            sys.exit(1)
    
        return
    
if __name__ == "__main__":
   Sfi().main()
