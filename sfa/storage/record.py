from sfa.util.sfatime import utcparse, datetime_to_string
from types import StringTypes
from datetime import datetime
from sfa.util.xml import XML
from sfa.trust.gid import GID

class Record:

    def __init__(self, dict=None, xml=None):
        if dict:
            self.load_from_dict(dict)
        elif xml:
            xml_record = XML(xml)
            xml_dict = xml_record.todict()
            self.load_from_dict(xml_dict)  


    def get_field(self, field):
        return self.__dict__.get(field, None)

    # xxx fixme
    # turns out the date_created field is received by the client as a 'created' int
    # (and 'last_updated' does not make it at all)
    # let's be flexible
    def date_repr (self,fields):
        if not isinstance(fields,list): fields=[fields]
        for field in fields:
            value=getattr(self,field,None)
            if isinstance (value,datetime):
                return datetime_to_string (value)
            elif isinstance (value,(int,float)):
                return datetime_to_string(utcparse(value))
        # fallback
        return "** undef_datetime **"
    
    def todict (self):
        d=self.__dict__
        keys=[k for k in d.keys() if not k.startswith('_')]
        return dict ( [ (k,d[k]) for k in keys ] )
    
    def toxml(self):
        return self.save_as_xml()

    def load_from_dict (self, d):
        for (k,v) in d.iteritems():
            # experimental
            if isinstance(v, StringTypes) and v.lower() in ['true']: v=True
            if isinstance(v, StringTypes) and v.lower() in ['false']: v=False
            setattr(self,k,v)

    # in addition we provide convenience for converting to and from xml records
    # for this purpose only, we need the subclasses to define 'fields' as either
    # a list or a dictionary
    def xml_fields (self):
        fields = self.__dict__.keys()
        return fields

    def save_as_xml (self):
        # xxx not sure about the scope here
        input_dict = dict( [ (key, getattr(self,key)) for key in self.xml_fields() if getattr(self,key,None) ] )
        xml_record=XML("<record />")
        xml_record.parse_dict (input_dict)
        return xml_record.toxml()

    def dump(self, format=None, dump_parents=False):
        if not format:
            format = 'text'
        else:
            format = format.lower()
        if format == 'text':
            self.dump_text(dump_parents)
        elif format == 'xml':
            print self.save_to_string()
        elif format == 'simple':
            print self.dump_simple()
        else:
            raise Exception, "Invalid format %s" % format

    def dump_text(self, dump_parents=False):
        # print core fields in this order
        core_fields = [ 'hrn', 'type', 'authority', 'date_created', 'created', 'last_updated', 'gid',  ]
        print "".join(['=' for i in range(40)])
        print "RECORD"
        print "    hrn:", self.hrn
        print "    type:", self.type
        print "    authority:", self.authority
        print "    date created:", self.date_repr( ['date_created','created'] )
        print "    last updated:", self.date_repr('last_updated')
        print "    gid:"
        if self.gid:
            print GID(self.gid).dump_string(8, dump_parents)    

        # print remaining fields
        for attrib_name in dir(self):
            attrib = getattr(self, attrib_name)
            # skip internals
            if attrib_name.startswith('_'):     continue
            # skip core fields
            if attrib_name in core_fields:      continue
            # skip callables
            if callable (attrib):               continue
            print "     %s: %s" % (attrib_name, attrib)

    def dump_simple(self):
        return "%s"%self    
