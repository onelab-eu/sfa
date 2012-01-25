from types import StringTypes

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, backref
from sqlalchemy import ForeignKey

from sfa.util.sfalogging import logger

# this module is designed to be loaded when the configured db server is reachable
# OTOH persistentobjs can be loaded from anywhere including the client-side

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

    def session (self):
        if self._session is None:
            Session=sessionmaker ()
            self._session=Session(bind=self.engine)
        return self._session

    def close_session (self):
        if self._session is None: return
        self._session.close()
        self._session=None

####################
from sfa.util.config import Config

alchemy=Alchemy (Config())
engine=alchemy.engine
dbsession=alchemy.session()

