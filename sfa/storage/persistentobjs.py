from types import StringTypes

from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import Table, Column, MetaData, join, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import column_property
from sqlalchemy.ext.declarative import declarative_base

from sfa.util.sfalogging import logger

from sfa.trust.gid import GID

from sfa.storage.alchemy import Base, alchemy, dbsession, engine, AlchemyObj

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

def insert_builtin_types(engine,dbsession):
    Base.metadata.create_all(engine)
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
    def __init__ (self, type, hrn=None, gid=None, authority=None, peer_authority=None, pointer=-1):
        self.type=type
        if hrn: self.hrn=hrn
        if gid: 
            if isinstance(gid, StringTypes): self.gid=gid
            else: self.gid=gid.save_to_string(save_parents=True)
        if authority: self.authority=authority
        if peer_authority: self.peer_authority=peer_authority
        self.pointer=pointer

    def __repr__(self):
        result="[Record(record_id=%s, hrn=%s, type=%s, authority=%s, pointer=%s" % \
                (self.record_id, self.hrn, self.type, self.authority, self.pointer)
        if self.gid: result+=" %s..."%self.gid[:10]
        else: result+=" no-gid"
        result += "]"
        return result

    def get_gid_object (self):
        if not self.gid: return None
        else: return GID(string=self.gid)

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
def init_tables():
    logger.info("Initializing db schema and builtin types")
    Base.metadata.create_all(engine)
    insert_builtin_types(engine,dbsession)

def drop_tables():
    logger.info("Dropping tables")
    Base.metadata.drop_all(engine)
