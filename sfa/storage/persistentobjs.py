from types import StringTypes
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import Table, Column, MetaData, join, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import column_property
from sqlalchemy.orm import object_mapper
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
            if isinstance(v, StringTypes):
                if v.lower() in ['true']: v=True
                if v.lower() in ['false']: v=False
            setattr(self,k,v)
        assert self.type in BUILTIN_TYPES
    
    # in addition we provide convenience for converting to and from xml records
    # for this purpose only, we need the subclasses to define 'fields' as either 
    # a list or a dictionary
    def xml_fields (self):
        fields=self.fields
        if isinstance(fields,dict): fields=fields.keys()
        return fields
    def load_from_xml (self, xml):
        xml_record = XML(xml)
        xml_dict = xml_record.todict()
        for k in self.xml_fields():
            if k in xml_dict:
                setattr(self,k,xml_dict[k])

    def save_as_xml (self):
        # xxx unset fields don't get exposed, is that right ?
        input_dict = dict( [ (key, getattr(self.key), ) for key in self.xml_fields() if getattr(self,key,None) ] )
        xml_record=XML("<record />")
        xml_record.parse_dict (input_dict)
        return xml_record.toxml()

##############################
class Type (Base):
    __table__ = Table ('types', Base.metadata,
                       Column ('type',String, primary_key=True)
                       )
    def __init__ (self, type): self.type=type
    def __repr__ (self): return "<Type %s>"%self.type
    
#BUILTIN_TYPES = [ 'authority', 'slice', 'node', 'user' ]
# xxx for compat but sounds useless
BUILTIN_TYPES = [ 'authority', 'slice', 'node', 'user',
                  'authority+sa', 'authority+am', 'authority+sm' ]

def insert_builtin_types(dbsession):
    for type in BUILTIN_TYPES :
        count = dbsession.query (Type).filter_by (type=type).count()
        if count==0:
            dbsession.add (Type (type))
    dbsession.commit()

##############################
class RegRecord (Base,AlchemyObj):
    # xxx tmp would be 'records'
    __table__ = Table ('records', Base.metadata,
                       Column ('record_id', Integer, primary_key=True),
                       Column ('type', String, ForeignKey ("types.type")),
                       Column ('hrn',String),
                       Column ('gid',String),
                       Column ('authority',String),
                       Column ('peer_authority',String),
                       Column ('pointer',Integer,default=-1),
                       Column ('date_created',DateTime),
                       Column ('last_updated',DateTime),
                       )
    fields = [ 'type', 'hrn', 'gid', 'authority', 'peer_authority' ]
    def __init__ (self, type='unknown', hrn=None, gid=None, authority=None, peer_authority=None, 
                  pointer=-1, dict=None):
        self.type=type
        if hrn: self.hrn=hrn
        if gid: 
            if isinstance(gid, StringTypes): self.gid=gid
            else: self.gid=gid.save_to_string(save_parents=True)
        if authority: self.authority=authority
        if peer_authority: self.peer_authority=peer_authority
        if not hasattr(self,'pointer'): self.pointer=pointer
        if dict:
            self.load_from_dict (dict)

    def __repr__(self):
        result="[Record(record_id=%s, hrn=%s, type=%s, authority=%s, pointer=%s" % \
                (self.record_id, self.hrn, self.type, self.authority, self.pointer)
        if self.gid: result+=" %s..."%self.gid[:10]
        else: result+=" no-gid"
        result += "]"
        return result

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
class User (Base):
    __table__ = Table ('users', Base.metadata,
                       Column ('user_id', Integer, primary_key=True),
                       Column ('record_id',Integer, ForeignKey('records.record_id')),
                       Column ('email', String),
                       )
    def __init__ (self, email):
        self.email=email
    def __repr__ (self): return "<User(%d) %s, record_id=%d>"%(self.user_id,self.email,self.record_id,)
                           
record_table = RegRecord.__table__
user_table = User.__table__
record_user_join = join (record_table, user_table)

class UserRecord (Base):
    __table__ = record_user_join
    record_id = column_property (record_table.c.record_id, user_table.c.record_id)
    user_id = user_table.c.user_id
    def __init__ (self, gid, email):
        self.type='user'
        self.gid=gid
        self.email=email
    def __repr__ (self): return "<UserRecord %s %s>"%(self.email,self.gid)

##############################
def init_tables(dbsession):
    logger.info("Initializing db schema and builtin types")
    # the doc states we could retrieve the engine this way
    # engine=dbsession.get_bind()
    # however I'm getting this
    # TypeError: get_bind() takes at least 2 arguments (1 given)
    # so let's import alchemy - but not from toplevel 
    from sfa.storage.alchemy import engine
    Base.metadata.create_all(engine)
    insert_builtin_types(dbsession)

def drop_tables(dbsession):
    logger.info("Dropping tables")
    # same as for init_tables
    from sfa.storage.alchemy import engine
    Base.metadata.drop_all(engine)
