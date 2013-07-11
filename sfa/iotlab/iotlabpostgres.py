from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sfa.util.config import Config
from sfa.util.sfalogging import logger

from sqlalchemy import Column, Integer, String
from sqlalchemy import Table, MetaData
from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.dialects import postgresql

from sqlalchemy.exc import NoSuchTableError


#Dict holding the columns names of the table as keys
#and their type, used for creation of the table
slice_table = {'record_id_user': 'integer PRIMARY KEY references X ON DELETE \
CASCADE ON UPDATE CASCADE','oar_job_id':'integer DEFAULT -1',  \
'record_id_slice':'integer', 'slice_hrn':'text NOT NULL'}

#Dict with all the specific iotlab tables
tablenames_dict = {'iotlab_xp': slice_table}


IotlabBase = declarative_base()



class IotlabXP (IotlabBase):
    """ SQL alchemy class to manipulate slice_iotlab table in
    iotlab_sfa database.

    """
    __tablename__ = 'iotlab_xp'


    slice_hrn = Column(String)
    job_id = Column(Integer, primary_key = True)
    end_time = Column(Integer, nullable = False)


    #oar_job_id = Column( Integer,default = -1)
    #node_list = Column(postgresql.ARRAY(String), nullable =True)

    def __init__ (self, slice_hrn =None, job_id=None,  end_time=None):
        """
        Defines a row of the slice_iotlab table
        """
        if slice_hrn:
            self.slice_hrn = slice_hrn
        if job_id :
            self.job_id = job_id
        if end_time:
            self.end_time = end_time


    def __repr__(self):
        """Prints the SQLAlchemy record to the format defined
        by the function.
        """
        result = "<iotlab_xp : slice_hrn = %s , job_id %s end_time = %s" \
            %(self.slice_hrn, self.job_id, self.end_time)
        result += ">"
        return result



class IotlabDB(object):
    """ SQL Alchemy connection class.
    From alchemy.py
    """
    # Stores the unique Singleton instance-
    _connection_singleton = None
    _dbname = "iotlab_sfa"


    class Singleton:
        """
        Class used with this Python singleton design pattern
            @todo Add all variables, and methods needed for the
            Singleton class below
        """

        def __init__(self, config, debug = False):
            self.iotlab_engine = None
            self.iotlab_session = None
            self.create_engine(config, debug)
            self.session()

        def create_engine(self, config, debug = False):


            if debug == True:
                l_echo_pool = True
                l_echo = True
            else:
                l_echo_pool = False
                l_echo = False
             # the former PostgreSQL.py used the psycopg2 directly and was doing
            #self.connection.set_client_encoding("UNICODE")
            # it's unclear how to achieve this in sqlalchemy, nor if it's needed
            # at all
            # http://www.sqlalchemy.org/docs/dialects/postgresql.html#unicode
            # we indeed have /var/lib/pgsql/data/postgresql.conf where
            # this setting is unset, it might be an angle to tweak that if need
            # be try a unix socket first
            #  - omitting the hostname does the trick
            unix_url = "postgresql+psycopg2://%s:%s@:%s/%s"% \
                (config.SFA_DB_USER, config.SFA_DB_PASSWORD, \
                                        config.SFA_DB_PORT, IotlabDB._dbname)

            # the TCP fallback method
            tcp_url = "postgresql+psycopg2://%s:%s@%s:%s/%s"% \
                (config.SFA_DB_USER, config.SFA_DB_PASSWORD, config.SFA_DB_HOST, \
                                        config.SFA_DB_PORT, IotlabDB._dbname)

            for url in [ unix_url, tcp_url ] :
                try:
                    self.iotlab_engine = create_engine (url, echo_pool =
                                                l_echo_pool, echo = l_echo)
                    self.check()
                    self.url = url
                    return
                except:
                    pass
                self.iotlab_engine = None


            raise Exception, "Could not connect to database"

        def check (self):
            """ Check if a table exists by trying a selection
            on the table.

            """
            self.iotlab_engine.execute ("select 1").scalar()


        def session (self):
            """
            Creates a SQLalchemy session. Once the session object is created
            it should be used throughout the code for all the operations on
            tables for this given database.

            """
            if self.iotlab_session is None:
                Session = sessionmaker()
                self.iotlab_session = Session(bind = self.iotlab_engine)
            return self.iotlab_session

        def close_session(self):
            """
            Closes connection to database.

            """
            if self.iotlab_session is None:
                return
            self.iotlab_session.close()
            self.iotlab_session = None

        def update_jobs_in_iotlabdb( job_oar_list, jobs_psql):
            """ Cleans the iotlab db by deleting expired and cancelled jobs.
            Compares the list of job ids given by OAR with the job ids that
            are already in the database, deletes the jobs that are no longer in
            the OAR job id list.
            :param  job_oar_list: list of job ids coming from OAR
            :type job_oar_list: list
            :param job_psql: list of job ids cfrom the database.
            type job_psql: list
            """
            #Turn the list into a set
            set_jobs_psql = set(jobs_psql)

            kept_jobs = set(job_oar_list).intersection(set_jobs_psql)
            logger.debug ( "\r\n \t\ update_jobs_in_iotlabdb jobs_psql %s \r\n \t \
                job_oar_list %s kept_jobs %s "%(set_jobs_psql, job_oar_list, kept_jobs))
            deleted_jobs = set_jobs_psql.difference(kept_jobs)
            deleted_jobs = list(deleted_jobs)
            if len(deleted_jobs) > 0:
                self.iotlab_session.query(IotlabXP).filter(IotlabXP.job_id.in_(deleted_jobs)).delete(synchronize_session='fetch')
                self.iotlab_session.commit()

            return



    def __init__(self, config, debug = False):
        self.sl_base = IotlabBase

         # Check whether we already have an instance
        if IotlabDB._connection_singleton is None:
            IotlabDB._connection_singleton = IotlabDB.Singleton(config, debug)

        # Store instance reference as the only member in the handle
        self._EventHandler_singleton = IotlabDB._connection_singleton



    def __getattr__(self, aAttr):
        """
        Delegate access to implementation.

        :param attr: Attribute wanted.
        :return: Attribute
        """
        return getattr(self._connection_singleton, aAttr)



    # def __setattr__(self, aAttr, aValue):
    #     """Delegate access to implementation.

    #      :param attr: Attribute wanted.
    #      :param value: Vaule to be set.
    #      :return: Result of operation.
    #      """
    #     return setattr(self._connection_singleton, aAttr, aValue)





    def exists(self, tablename):
        """
        Checks if the table specified as tablename exists.

        """

        try:
            metadata = MetaData (bind=self.iotlab_engine)
            table = Table (tablename, metadata, autoload=True)
            return True

        except NoSuchTableError:
            logger.log_exc("SLABPOSTGRES tablename %s does not exists" \
                            %(tablename))
            return False


    def createtable(self):
        """
        Creates all the table sof the engine.
        Uses the global dictionnary holding the tablenames and the table schema.

        """

        logger.debug("SLABPOSTGRES createtable IotlabBase.metadata.sorted_tables \
            %s \r\n engine %s" %(IotlabBase.metadata.sorted_tables , self.iotlab_engine))
        IotlabBase.metadata.create_all(self.iotlab_engine)
        return



# iotlab_alchemy = IotlabDB(Config())
# iotlab_engine = iotlab_alchemy.iotlab_engine
# iotlab_dbsession = iotlab_alchemy.session()
