#!/usr/bin/python
import os
import sys
import copy
from pprint import pformat 
from sfa.generic import Generic
from optparse import OptionParser
from pprint import PrettyPrinter
from sfa.util.xrn import Xrn
from sfa.storage.record import Record 
from sfa.client.sfi import save_records_to_file
from sfa.trust.hierarchy import Hierarchy
from sfa.trust.gid import GID

pprinter = PrettyPrinter(indent=4)

def args(*args, **kwargs):
    def _decorator(func):
        func.__dict__.setdefault('options', []).insert(0, (args, kwargs))
        return func
    return _decorator

class Commands(object):

    def _get_commands(self):
        available_methods = []
        for attrib in dir(self):
            if callable(getattr(self, attrib)) and not attrib.startswith('_'):
                available_methods.append(attrib)
        return available_methods         


class RegistryCommands(Commands):
    def __init__(self, *args, **kwds):
        self.api= Generic.the_flavour().make_api(interface='registry')
 
    def version(self):
        version = self.api.manager.GetVersion(self.api, {})
        pprinter.pprint(version)

    @args('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn') 
    @args('-t', '--type', dest='type', metavar='<type>', help='object type', default=None) 
    def list(self, xrn, type=None):
        xrn = Xrn(xrn, type) 
        records = self.api.manager.List(self.api, xrn.get_hrn())
        for record in records:
            if not type or record['type'] == type:
                print "%s (%s)" % (record['hrn'], record['type'])


    @args('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn') 
    @args('-t', '--type', dest='type', metavar='<type>', help='object type', default=None) 
    @args('-o', '--outfile', dest='outfile', metavar='<outfile>', help='save record to file') 
    @args('-f', '--format', dest='format', metavar='<display>', type='choice', 
          choices=('text', 'xml', 'simple'), help='display record in different formats') 
    def show(self, xrn, type=None, format=None, outfile=None):
        records = self.api.manager.Resolve(self.api, xrn, type, True)
        for record in records:
            sfa_record = Record(dict=record)
            sfa_record.dump(format) 
        if outfile:
            save_records_to_file(outfile, records)                

    def register(self, record):
        pass

    def update(self, record):
        pass
        
    @args('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn') 
    @args('-t', '--type', dest='type', metavar='<type>', help='object type', default=None) 
    def remove(self, xrn, type=None):
        xrn = Xrn(xrn, type)
        self.api.manager.Remove(self.api, xrn)            


    @args('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn') 
    @args('-t', '--type', dest='type', metavar='<type>', help='object type', default=None) 
    def credential(self, xrn, type=None):
        cred = self.api.manager.GetCredential(self.api, xrn, type, self.api.hrn)
        print cred
   

    def import_registry(self):
        from sfa.importer import Importer
        importer = Importer()
        importer.run()
    
    @args('-a', '--all', dest='all', metavar='<all>', action='store_true', default=False,
          help='Remove all registry records and all files in %s area' % Hierarchy().basedir)
    @args('-c', '--certs', dest='certs', metavar='<certs>', action='store_true', default=False,
          help='Remove all cached certs/gids found in %s' % Hierarchy().basedir )
    @args('-0', '--no-reinit', dest='reinit', metavar='<reinit>', action='store_false', default=True,
          help='Prevents new DB schema from being installed after cleanup')
    def nuke(self, all=False, certs=False, reinit=True):
        from sfa.storage.dbschema import DBSchema
        from sfa.util.sfalogging import _SfaLogger
        logger = _SfaLogger(logfile='/var/log/sfa_import.log', loggername='importlog')
        logger.setLevelFromOptVerbose(self.api.config.SFA_API_LOGLEVEL)
        logger.info("Purging SFA records from database")
        dbschema=DBSchema()
        dbschema.nuke()

        # for convenience we re-create the schema here, so there's no need for an explicit
        # service sfa restart
        # however in some (upgrade) scenarios this might be wrong
        if reinit:
            logger.info("re-creating empty schema")
            dbschema.init_or_upgrade()

        # remove the server certificate and all gids found in /var/lib/sfa/authorities
        if certs:
            logger.info("Purging cached certificates")
            for (dir, _, files) in os.walk('/var/lib/sfa/authorities'):
                for file in files:
                    if file.endswith('.gid') or file == 'server.cert':
                        path=dir+os.sep+file
                        os.unlink(path)

        # just remove all files that do not match 'server.key' or 'server.cert'
        if all:
            logger.info("Purging registry filesystem cache")
            preserved_files = [ 'server.key', 'server.cert']
            for (dir,_,files) in os.walk(Hierarchy().basedir):
                for file in files:
                    if file in preserved_files: continue
                    path=dir+os.sep+file
                    os.unlink(path)
        
    
class CertCommands(Commands):
    
    def import_gid(self, xrn):
        pass

    @args('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn')
    @args('-t', '--type', dest='type', metavar='<type>', help='object type', default=None)
    @args('-o', '--outfile', dest='outfile', metavar='<outfile>', help='output file', default=None)
    def export(self, xrn, type=None, outfile=None):
        from sfa.storage.alchemy import dbsession
        from sfa.storage.model import RegRecord
        hrn = Xrn(xrn).get_hrn()
        request=dbsession.query(RegRecord).filter_by(hrn=hrn)
        if type: request = request.filter_by(type=type)
        record=request.first()
        if record:
            gid = GID(string=record.gid)
        else:
            # check the authorities hierarchy
            hierarchy = Hierarchy()
            try:
                auth_info = hierarchy.get_auth_info(hrn)
                gid = auth_info.gid_object
            except:
                print "Record: %s not found" % hrn
                sys.exit(1)
        # save to file
        if not outfile:
            outfile = os.path.abspath('./%s.gid' % gid.get_hrn())
        gid.save_to_file(outfile, save_parents=True)
        
    @args('-g', '--gidfile', dest='gid', metavar='<gid>', help='path of gid file to display') 
    def display(self, gidfile):
        gid_path = os.path.abspath(gidfile)
        if not gid_path or not os.path.isfile(gid_path):
            print "No such gid file: %s" % gidfile
            sys.exit(1)
        gid = GID(filename=gid_path)
        gid.dump(dump_parents=True)
    

class AggregateCommands(Commands):

    def __init__(self, *args, **kwds):
        self.api= Generic.the_flavour().make_api(interface='aggregate')
   
    def version(self):
        version = self.api.manager.GetVersion(self.api, {})
        pprinter.pprint(version)

    def slices(self):
        print self.api.manager.ListSlices(self.api, [], {})

    @args('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn') 
    def status(self, xrn):
        urn = Xrn(xrn, 'slice').get_urn()
        status = self.api.manager.SliverStatus(self.api, urn, [], {})
        pprinter.pprint(status)
 
    @args('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn', default=None)
    @args('-r', '--rspec-version', dest='rspec_version', metavar='<rspec_version>', 
          default='GENI', help='version/format of the resulting rspec response')  
    def resources(self, xrn=None, rspec_version='GENI'):
        options = {'geni_rspec_version': rspec_version}
        if xrn:
            options['geni_slice_urn'] = xrn
        resources = self.api.manager.ListResources(self.api, [], options)
        print resources
        
    @args('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn', default=None)
    @args('-r', '--rspec', dest='rspec', metavar='<rspec>', help='rspec file')  
    @args('-u', '--user', dest='user', metavar='<user>', help='hrn/urn of slice user')  
    @args('-k', '--key', dest='key', metavar='<key>', help="path to user's public key file")  
    def create(self, xrn, rspec, user, key):
        xrn = Xrn(xrn, 'slice')
        slice_urn=xrn.get_urn()
        rspec_string = open(rspec).read()
        user_xrn = Xrn(user, 'user')
        user_urn = user_xrn.get_urn()
        user_key_string = open(key).read()
        users = [{'urn': user_urn, 'keys': [user_key_string]}]
        options={}
        self.api.manager.CreateSliver(self, slice_urn, [], rspec_string, users, options) 

    @args('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn', default=None)
    def delete(self, xrn):
        self.api.manager.DeleteSliver(self.api, xrn, [], {})
 
    @args('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn', default=None)
    def start(self, xrn):
        self.api.manager.start_slice(self.api, xrn, [])

    @args('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn', default=None)
    def stop(self, xrn):
        self.api.manager.stop_slice(self.api, xrn, [])      

    @args('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn', default=None)
    def reset(self, xrn):
        self.api.manager.reset_slice(self.api, xrn)


    @args('-x', '--xrn', dest='xrn', metavar='<xrn>', help='object hrn/urn', default=None)
    @args('-r', '--rspec', dest='rspec', metavar='<rspec>', help='request rspec', default=None)
    def ticket(self, xrn, rspec):
        pass



class SliceManagerCommands(AggregateCommands):
    
    def __init__(self, *args, **kwds):
        self.api= Generic.the_flavour().make_api(interface='slicemgr')


CATEGORIES = {'cert': CertCommands,
              'registry': RegistryCommands,
              'aggregate': AggregateCommands,
              'slicemgr': SliceManagerCommands}

def category_usage():
    print "Available categories:"
    for k in CATEGORIES:
        print "\t%s" % k

def main():
    argv = copy.deepcopy(sys.argv)
    script_name = argv.pop(0)
    # ensure category is specified    
    if len(argv) < 1:
        print script_name + " category action [<args>]"
        category_usage()
        sys.exit(2)

    # ensure category is valid
    category = argv.pop(0)
    usage = "%%prog %s action <args> [options]" % (category)
    parser = OptionParser(usage=usage)
    command_class =  CATEGORIES.get(category, None)
    if not command_class:
        print "no such category %s " % category
        category_usage()
        sys.exit(2)  
    
    # ensure command is valid      
    command_instance = command_class()
    actions = command_instance._get_commands()
    if len(argv) < 1:
        action = '__call__'
    else:
        action = argv.pop(0)
    
    if hasattr(command_instance, action):
        command = getattr(command_instance, action)
    else:
        print script_name + " category action [<args>]"
        print "Available actions for %s category:" % category
        for k in actions:
            print "\t%s" % k
        sys.exit(2)

    # ensure options are valid
    options = getattr(command, 'options', [])
    usage = "%%prog %s %s <args> [options]" % (category, action)
    parser = OptionParser(usage=usage)
    for arg, kwd in options:
        parser.add_option(*arg, **kwd)
    (opts, cmd_args) = parser.parse_args(argv)
    cmd_kwds = vars(opts)

    # dont overrride meth
    for k, v in cmd_kwds.items():
        if v is None:
            del cmd_kwds[k]

    # execute commadn
    try:
        command(*cmd_args, **cmd_kwds)
        sys.exit(0)
    except TypeError:
        print "Possible wrong number of arguments supplied"
        print command.__doc__
        parser.print_help()
        #raise
        raise
    except Exception:
        print "Command failed, please check log for more info"
        raise


if __name__ == '__main__':
    main()
    
     
        
     
