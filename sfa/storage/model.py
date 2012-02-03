from types import StringTypes
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import Table, Column, MetaData, join, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import column_property
from sqlalchemy.orm import object_mapper
from sqlalchemy.orm import validates
from sqlalchemy.ext.declarative import declarative_base

from sfa.util.sfalogging import logger
from sfa.util.xml import XML 

from sfa.trust.gid import GID

##############################
Base=declarative_base()

####################
# dicts vs objects
####################
# historically the front end to the db dealt with dicts, so the code was only dealing with dicts
# sqlalchemy however offers an object interface, meaning that you write obj.id instead of obj['id']
# which is admittedly much nicer
# however we still need to deal with dictionaries if only for the xmlrpc layer
# 
# here are a few utilities for this 
# 
# (*) first off, when an old pieve of code needs to be used as-is, if only temporarily, the simplest trick
# is to use obj.__dict__
# this behaves exactly like required, i.e. obj.__dict__['field']='new value' does change obj.field
# however this depends on sqlalchemy's implementation so it should be avoided 
#
# (*) second, when an object needs to be exposed to the xmlrpc layer, we need to convert it into a dict
# remember though that writing the resulting dictionary won't change the object
# essentially obj.__dict__ would be fine too, except that we want to discard alchemy private keys starting with '_'
# 2 ways are provided for that:
# . dict(obj)
# . obj.todict()
# the former dict(obj) relies on __iter__() and next() below, and does not rely on the fields names
# although it seems to work fine, I've found cases where it issues a weird python error that I could not get right
# so the latter obj.todict() seems more reliable but more hacky as is relies on the form of fields, so this can probably be improved
#
# (*) finally for converting a dictionary into an sqlalchemy object, we provide
# obj.load_from_dict(dict)

class AlchemyObj:
    def __iter__(self): 
        self._i = iter(object_mapper(self).columns)
        return self 
    def next(self): 
        n = self._i.next().name
        return n, getattr(self, n)
    def todict (self):
        d=self.__dict__
        keys=[k for k in d.keys() if not k.startswith('_')]
        return dict ( [ (k,d[k]) for k in keys ] )
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
        fields=self.fields
        if isinstance(fields,dict): fields=fields.keys()
        return fields

    def save_as_xml (self):
        # xxx not sure about the scope here
        input_dict = dict( [ (key, getattr(self.key), ) for key in self.xml_fields() if getattr(self,key,None) ] )
        xml_record=XML("<record />")
        xml_record.parse_dict (input_dict)
        return xml_record.toxml()

    def dump(self, dump_parents=False):
        for key in self.fields:
            if key == 'gid' and self.gid:
                gid = GID(string=self.gid)
                print "    %s:" % key
                gid.dump(8, dump_parents)
            elif getattr(self,key,None):    
                print "    %s: %s" % (key, getattr(self,key))
    
#    # only intended for debugging 
#    def inspect (self, logger, message=""):
#        logger.info("%s -- Inspecting AlchemyObj -- attrs"%message)
#        for k in dir(self):
#            if not k.startswith('_'):
#                logger.info ("  %s: %s"%(k,getattr(self,k)))
#        logger.info("%s -- Inspecting AlchemyObj -- __dict__"%message)
#        d=self.__dict__
#        for (k,v) in d.iteritems():
#            logger.info("[%s]=%s"%(k,v))


##############################
# various kinds of records are implemented as an inheritance hierarchy
# RegRecord is the base class for all actual variants
# a first draft was using 'type' as the discriminator for the inheritance
# but we had to define another more internal column (classtype) so we 
# accomodate variants in types like authority+am and the like

class RegRecord (Base,AlchemyObj):
    __tablename__       = 'records'
    record_id           = Column (Integer, primary_key=True)
    # this is the discriminator that tells which class to use
    classtype           = Column (String)
    type                = Column (String)
    hrn                 = Column (String)
    gid                 = Column (String)
    authority           = Column (String)
    peer_authority      = Column (String)
    pointer             = Column (Integer, default=-1)
    date_created        = Column (DateTime)
    last_updated        = Column (DateTime)
    # use the 'type' column to decide which subclass the object is of
    __mapper_args__     = { 'polymorphic_on' : classtype }

    fields = [ 'type', 'hrn', 'gid', 'authority', 'peer_authority' ]
    def __init__ (self, type=None, hrn=None, gid=None, authority=None, peer_authority=None, 
                  pointer=None, dict=None):
        if type:                                self.type=type
        if hrn:                                 self.hrn=hrn
        if gid: 
            if isinstance(gid, StringTypes):    self.gid=gid
            else:                               self.gid=gid.save_to_string(save_parents=True)
        if authority:                           self.authority=authority
        if peer_authority:                      self.peer_authority=peer_authority
        if pointer:                             self.pointer=pointer
        if dict:                                self.load_from_dict (dict)

    def __repr__(self):
        result="[Record id=%s, type=%s, hrn=%s, authority=%s, pointer=%s" % \
                (self.record_id, self.type, self.hrn, self.authority, self.pointer)
        # skip the uniform '--- BEGIN CERTIFICATE --' stuff
        if self.gid: result+=" gid=%s..."%self.gid[28:36]
        else: result+=" nogid"
        result += "]"
        return result

    @validates ('gid')
    def validate_gid (self, key, gid):
        if gid is None:                     return
        elif isinstance(gid, StringTypes):  return gid
        else:                               return gid.save_to_string(save_parents=True)

    # xxx - there might be smarter ways to handle get/set'ing gid using validation hooks 
    def get_gid_object (self):
        if not self.gid: return None
        else: return GID(string=self.gid)

    def just_created (self):
        now=datetime.now()
        self.date_created=now
        self.last_updated=now

    def just_updated (self):
        now=datetime.now()
        self.last_updated=now

##############################
class RegAuthority (RegRecord):
    __tablename__       = 'authorities'
    __mapper_args__     = { 'polymorphic_identity' : 'authority' }
    record_id           = Column (Integer, ForeignKey ("records.record_id"), primary_key=True)
    
    # no proper data yet, just hack the typename
    def __repr__ (self):
        return RegRecord.__repr__(self).replace("Record","Authority")

##############################
class RegSlice (RegRecord):
    __tablename__       = 'slices'
    __mapper_args__     = { 'polymorphic_identity' : 'slice' }
    record_id           = Column (Integer, ForeignKey ("records.record_id"), primary_key=True)
    
    def __repr__ (self):
        return RegRecord.__repr__(self).replace("Record","Slice")

##############################
class RegNode (RegRecord):
    __tablename__       = 'nodes'
    __mapper_args__     = { 'polymorphic_identity' : 'node' }
    record_id           = Column (Integer, ForeignKey ("records.record_id"), primary_key=True)
    
    def __repr__ (self):
        return RegRecord.__repr__(self).replace("Record","Node")

##############################
class RegUser (RegRecord):
    __tablename__       = 'users'
    # these objects will have type='user' in the records table
    __mapper_args__     = { 'polymorphic_identity' : 'user' }
    record_id           = Column (Integer, ForeignKey ("records.record_id"), primary_key=True)
    email               = Column ('email', String)
    # can't use name 'keys' here because when loading from xml we're getting
    # a 'keys' tag, and assigning a list of strings in a reference column like this crashes
    reg_keys                = relationship ('RegKey', backref='reg_user')
    
    def __init__ (self, **kwds):
        # handle local settings
        if 'email' in kwds: self.email=kwds.pop('email')
        # fill in type if not previously set
        if 'type' not in kwds: kwds['type']='user'
        RegRecord.__init__(self, **kwds)

    # append stuff at the end of the record __repr__
    def __repr__ (self): 
        result = RegRecord.__repr__(self).replace("Record","User")
        result.replace ("]"," email=%s"%self.email)
        result += "]"
        return result
    
    @validates('email') 
    def validate_email(self, key, address):
        assert '@' in address
        return address

####################
# xxx tocheck : not sure about eager loading of this one
# meaning, when querying the whole records, we expect there should
# be a single query to fetch all the keys 
class RegKey (Base):
    __tablename__       = 'keys'
    key_id              = Column (Integer, primary_key=True)
    record_id             = Column (Integer, ForeignKey ("records.record_id"))
    key                 = Column (String)
    pointer             = Column (Integer, default = -1)
    
    def __init__ (self, key, pointer=None):
        self.key=key
        if pointer: self.pointer=pointer

    def __repr__ (self):
        result="[key key=%s..."%self.key[8:16]
        try:    result += " user=%s"%self.user.record_id
        except: result += " <orphan>"
        result += "]"
        return result

##############################
# although the db needs of course to be reachable,
# the schema management functions are here and not in alchemy
# because the actual details of the classes need to be known
# migrations: this code has no notion of the previous versions
# of the data model nor of migrations
# sfa.storage.migrations.db_init uses this when starting from
# a fresh db only
def init_tables(engine):
    logger.info("Initializing db schema from current/latest model")
    Base.metadata.create_all(engine)

def drop_tables(engine):
    logger.info("Dropping tables from current/latest model")
    Base.metadata.drop_all(engine)

##############################
# create a record of the right type from either a dict or an xml string
def make_record (dict={}, xml=""):
    if dict:    return make_record_dict (dict)
    elif xml:   return make_record_xml (xml)
    else:       raise Exception("make_record has no input")

# convert an incoming record - typically from xmlrpc - into an object
def make_record_dict (record_dict):
    assert ('type' in record_dict)
    type=record_dict['type'].split('+')[0]
    if type=='authority':
        result=RegAuthority (dict=record_dict)
    elif type=='user':
        result=RegUser (dict=record_dict)
    elif type=='slice':
        result=RegSlice (dict=record_dict)
    elif type=='node':
        result=RegNode (dict=record_dict)
    else:
        logger.debug("Untyped RegRecord instance")
        result=RegRecord (dict=record_dict)
    logger.info ("converting dict into Reg* with type=%s"%type)
    logger.info ("returning=%s"%result)
    # xxx todo
    # register non-db attributes in an extensions field
    return result
        
def make_record_xml (xml):
    xml_record = XML(xml)
    xml_dict = xml_record.todict()
    logger.info("load from xml, keys=%s"%xml_dict.keys())
    return make_record_dict (xml_dict)
