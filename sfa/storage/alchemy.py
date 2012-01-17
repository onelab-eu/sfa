from types import StringTypes

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, backref
from sqlalchemy import ForeignKey

from sfa.util.sfalogging import logger

Base=declarative_base()

class Alchemy:

    def __init__ (self, config):
        dbname="sfa"
        # will be created lazily on-demand
        self._session = None
        # the former PostgreSQL.py used the psycopg2 directly and was doing
        #self.connection.set_client_encoding("UNICODE")
        # it's unclear how to achieve this in sqlalchemy, nor if it's needed at all
        # http://www.sqlalchemy.org/docs/dialects/postgresql.html#unicode
        # we indeed have /var/lib/pgsql/data/postgresql.conf where
        # this setting is unset, it might be an angle to tweak that if need be
        # try a unix socket first - omitting the hostname does the trick
        unix_desc = "postgresql+psycopg2://%s:%s@:%s/%s"%\
            (config.SFA_DB_USER,config.SFA_DB_PASSWORD,config.SFA_DB_PORT,dbname)
        # the TCP fallback method
        tcp_desc = "postgresql+psycopg2://%s:%s@%s:%s/%s"%\
            (config.SFA_DB_USER,config.SFA_DB_PASSWORD,config.SFA_DB_HOST,config.SFA_DB_PORT,dbname)
        for engine_desc in [ unix_desc, tcp_desc ] :
            try:
                self.engine = create_engine (engine_desc)
                self.check()
                return
            except:
                pass
        self.engine=None
        raise Exception,"Could not connect to database"
                

    # expects boolean True: debug is ON or False: debug is OFF
    def debug (self, echo):
        self.engine.echo=echo

    def check (self):
        self.engine.execute ("select 1").scalar()

    # create schema
    # warning: need to have all Base subclass loaded for this to work
    def create_schema (self):
        return Base.metadata.create_all(self.engine)

    # does a complete wipe of the schema, use with care
    def drop_schema (self):
        return Base.metadata.drop_all(self.engine)

    def session (self):
        if self._session is None:
            Session=sessionmaker ()
            self._session=Session(bind=self.engine)
        return self._session

    def close_session (self):
        if self._session is None: return
        self._session.close()
        self._session=None

    def commit (self):
        self.session().commit()
            
    def insert (self, stuff, commit=False):
        if isinstance (stuff,list):
            self.session().add_all(stuff)
        else:
            self.session().add(obj)

    # for compat with the previous PostgreSQL stuff
    def update (self, record):
        self.commit()

    def remove (self, record):
        del record
        self.commit()

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
# obj.set_from_dict(dict)

from sqlalchemy.orm import object_mapper
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
    def set_from_dict (self, d):
        for (k,v) in d.iteritems():
            # experimental
            if isinstance(v, StringTypes):
                if v.lower() in ['true']: v=True
                if v.lower() in ['false']: v=False
            setattr(self,k,v)

####################
from sfa.util.config import Config

alchemy=Alchemy (Config())
engine=alchemy.engine
dbsession=alchemy.session()

