from types import StringTypes

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy import Column, Integer, String
from sqlalchemy import ForeignKey

from sfa.util.sfalogging import logger

# this module is designed to be loaded when the configured db server is reachable
# OTOH model can be loaded from anywhere including the client-side

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
        unix_url = "postgresql+psycopg2://%s:%s@:%s/%s"%\
            (config.SFA_DB_USER,config.SFA_DB_PASSWORD,config.SFA_DB_PORT,dbname)
        # the TCP fallback method
        tcp_url = "postgresql+psycopg2://%s:%s@%s:%s/%s"%\
            (config.SFA_DB_USER,config.SFA_DB_PASSWORD,config.SFA_DB_HOST,config.SFA_DB_PORT,dbname)
        for url in [ unix_url, tcp_url ] :
            try:
                logger.debug("Trying db URL %s"%url)
                self.engine = create_engine (url)
                self.check()
                self.url=url
                return
            except:
                pass
        self.engine=None
        raise Exception,"Could not connect to database %s as %s with psycopg2"%(dbname,config.SFA_DB_USER)


    # expects boolean True: debug is ON or False: debug is OFF
    def debug (self, echo):
        self.engine.echo=echo

    def check (self):
        self.engine.execute ("select 1").scalar()

    def global_session (self):
        if self._session is None:
            Session=sessionmaker ()
            self._session=Session(bind=self.engine)
            logger.info('alchemy.global_session created session %s'%self._session)
        return self._session

    def close_global_session (self):
        if self._session is None: return
        logger.info('alchemy.close_global_session %s'%self._session)
        self._session.close()
        self._session=None

    # create a dbsession to be managed separately
    def session (self):
        Session=sessionmaker()
        session=Session (bind=self.engine)
        logger.info('alchemy.session created session %s'%session)
        return session

    def close_session (self, session):
        logger.info('alchemy.close_session closed session %s'%session)
        session.close()

####################
from sfa.util.config import Config

alchemy=Alchemy (Config())
engine=alchemy.engine
global_dbsession=alchemy.global_session()

