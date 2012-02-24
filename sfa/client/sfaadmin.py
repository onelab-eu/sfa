#!/usr/bin/python
import sys
import copy
from pprint import pformat 
from sfa.generic import Generic
from optparse import OptionParser
from pprint import PrettyPrinter
from sfa.util.xrn import Xrn
from sfa.storage.record import SfaRecord 
from sfa.client.sfi import save_records_to_file
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
          choices=('text', 'xml', 'summary'), help='display record in different formats') 
    def show(self, xrn, type=None, format=None, outfile=None):
        records = self.api.manager.Resolve(self.api, xrn, type, True)
        for record in records:
            sfa_record = SfaRecord(dict=record)
            sfa_record.dump(format) 
        if outfile:
            save_records_to_file(outfile, records)                

    def register(self, record):
        pass

    def update(self, record):
        pass
        
    def remove(self, xrn):            
        pass

    def credential(self, xrn):
        pass

    def gid(self, xrn):
        pass

class CerficiateCommands(Commands):
    
    def import_records(self, xrn):
        pass

    def export(self, xrn):
        pass

    def display(self, xrn):
        pass

    def nuke(self):
        pass  

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
 
    def resources(self, xrn):
        pass

    def create(self, xrn, rspec):
        pass

    def delete(self, xrn):
        pass 
    
    def start(self, xrn):
        pass

    def stop(self, xrn):
        pass      

    def reset(self, xrn):
        pass

    def ticket(self):
        pass


class SliceManagerCommands(AggregateCommands):
    
    def __init__(self, *args, **kwds):
        self.api= Generic().make_api(interface='slicemgr')


CATEGORIES = {'registry': RegistryCommands,
              'aggregate': AggregateCommands,
              'slicemgr': SliceManagerCommands}

def main():
    argv = copy.deepcopy(sys.argv)
    script_name = argv.pop(0)
    if len(argv) < 1:
        print script_name + " category action [<args>]"
        print "Available categories:"
        for k in CATEGORIES:
            print "\t%s" % k
        sys.exit(2)

    category = argv.pop(0)
    usage = "%%prog %s action <args> [options]" % (category)
    parser = OptionParser(usage=usage)
    command_class =  CATEGORIES[category]
    command_instance = command_class()
    actions = command_instance._get_commands()
    if len(argv) < 1:
        if hasattr(command_instance, '__call__'):
            action = ''
            command = command_instance.__call__
        else:
            print script_name + " category action [<args>]"
            print "Available actions for %s category:" % category
            for k in actions:
                print "\t%s" % k 
            sys.exit(2)
    else:
        action = argv.pop(0)
        command = getattr(command_instance, action)

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
    
     
        
     
