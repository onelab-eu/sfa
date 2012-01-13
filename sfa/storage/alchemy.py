from sqlalchemy import create_engine

from sqlalchemy.orm import sessionmaker
Session=sessionmaker ()
session=Session(bind=engine)
#session.configure(bind=engine)

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, backref
from sqlalchemy import ForeignKey

from sfa.util.sfalogger import logger

Base=declarative_base()

class DB:

    def __init__ (self, config):
        dbname="sfa"
        # will be created lazily on-demand
        self.session = None
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
        for desc in [ unix_desc, tcp_desc ] :
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
