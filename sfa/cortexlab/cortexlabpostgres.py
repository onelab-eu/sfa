"""
File defining classes to handle the table in the iotlab dedicated database.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# from sfa.util.config import Config
from sfa.util.sfalogging import logger

from sqlalchemy import Column, Integer, String
from sqlalchemy import Table, MetaData
from sqlalchemy.ext.declarative import declarative_base

# from sqlalchemy.dialects import postgresql

from sqlalchemy.exc import NoSuchTableError


#Dict holding the columns names of the table as keys
#and their type, used for creation of the table
slice_table = {'record_id_user': 'integer PRIMARY KEY references X ON DELETE \
                CASCADE ON UPDATE CASCADE', 'oar_job_id': 'integer DEFAULT -1',
               'record_id_slice': 'integer', 'slice_hrn': 'text NOT NULL'}

#Dict with all the specific iotlab tables
tablenames_dict = {'iotlab_xp': slice_table}


IotlabBase = declarative_base()


class IotlabXP (IotlabBase):
    """ SQL alchemy class to manipulate the rows of the slice_iotlab table in
    iotlab_sfa database. Handles the records representation and creates the
    table if it does not exist yet.

    """
    __tablename__ = 'iotlab_xp'

    slice_hrn = Column(String)
    job_id = Column(Integer, primary_key=True)
    end_time = Column(Integer, nullable=False)

    def __init__(self, slice_hrn=None, job_id=None,  end_time=None):
        """
        Defines a row of the slice_iotlab table
        """
        if slice_hrn:
            self.slice_hrn = slice_hrn
        if job_id:
            self.job_id = job_id
        if end_time:
            self.end_time = end_time

    def __repr__(self):
        """Prints the SQLAlchemy record to the format defined
        by the function.
        """
        result = "<iotlab_xp : slice_hrn = %s , job_id %s end_time = %s" \
            % (self.slice_hrn, self.job_id, self.end_time)
        result += ">"
        return result


class IotlabDB(object):
    """ SQL Alchemy connection class.
    From alchemy.py
    """
    # Stores the unique Singleton instance-
    _connection_singleton = None
    # defines the database name
    dbname = "iotlab_sfa"

    class Singleton:
        """
        Class used with this Python singleton design pattern to allow the
        definition of one single instance of iotlab db session in the whole
        code. Wherever a connection to the database is needed, this class
        returns the same instance every time. Removes the need for global
        variable throughout the code.
        """

        def __init__(self, config, debug=False):
            self.iotlab_engine = None
            self.iotlab_session = None
            self.url = None
            self.create_iotlab_engine(config, debug)
            self.session()

        def create_iotlab_engine(self, config, debug=False):
            """Creates the SQLAlchemy engine, which is the starting point for
            any SQLAlchemy application.
            :param config: configuration object created by SFA based on the
            configuration file in /etc
            :param debug: if set to true, echo and echo pool will be set to true
            as well. If echo is True, all statements as well as a repr() of
            their parameter lists to the engines logger, which defaults to
            sys.stdout. If echo_pool is True, the connection pool will log all
            checkouts/checkins to the logging stream. A python logger can be
            used to configure this logging directly but so far it has not been
            configured. Refer to sql alchemy engine documentation.

            :type config: Config instance (sfa.util.config)
            :type debug: bool

            """

            if debug is True:
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
            unix_url = "postgresql+psycopg2://%s:%s@:%s/%s" \
                % (config.SFA_DB_USER, config.SFA_DB_PASSWORD,
                   config.SFA_DB_PORT, IotlabDB.dbname)

            # the TCP fallback method
            tcp_url = "postgresql+psycopg2://%s:%s@%s:%s/%s" \
                % (config.SFA_DB_USER, config.SFA_DB_PASSWORD,
                    config.SFA_DB_HOST, config.SFA_DB_PORT, IotlabDB.dbname)

            for url in [unix_url, tcp_url]:
                try:
                    self.iotlab_engine = create_engine(
                        url, echo_pool=l_echo_pool, echo=l_echo)
                    self.check()
                    self.url = url
                    return
                except:
                    pass
                self.iotlab_engine = None

            raise Exception("Could not connect to database")

        def check(self):
            """ Check if a table exists by trying a selection
            on the table.

            """
            self.iotlab_engine.execute("select 1").scalar()


        def session(self):
            """
            Creates a SQLalchemy session. Once the session object is created
            it should be used throughout the code for all the operations on
            tables for this given database.

            """
            if self.iotlab_session is None:
                Session = sessionmaker()
                self.iotlab_session = Session(bind=self.iotlab_engine)
            return self.iotlab_session

        def close_session(self):
            """
            Closes connection to database.

            """
            if self.iotlab_session is None:
                return
            self.iotlab_session.close()
            self.iotlab_session = None


        def update_jobs_in_iotlabdb(self, job_oar_list, jobs_psql):
            """ Cleans the iotlab db by deleting expired and cancelled jobs.

            Compares the list of job ids given by OAR with the job ids that
            are already in the database, deletes the jobs that are no longer in
            the OAR job id list.

            :param  job_oar_list: list of job ids coming from OAR
            :type job_oar_list: list
            :param job_psql: list of job ids from the database.
            :type job_psql: list

            :returns: None
            """
            #Turn the list into a set
            set_jobs_psql = set(jobs_psql)

            kept_jobs = set(job_oar_list).intersection(set_jobs_psql)
            logger.debug("\r\n \t update_jobs_in_iotlabdb jobs_psql %s \r\n \
                            job_oar_list %s kept_jobs %s "
                         % (set_jobs_psql, job_oar_list, kept_jobs))
            deleted_jobs = set_jobs_psql.difference(kept_jobs)
            deleted_jobs = list(deleted_jobs)
            if len(deleted_jobs) > 0:
                self.iotlab_session.query(IotlabXP).filter(IotlabXP.job_id.in_(deleted_jobs)).delete(synchronize_session='fetch')
                self.iotlab_session.commit()
            return

    def __init__(self, config, debug=False):
        self.sl_base = IotlabBase

         # Check whether we already have an instance
        if IotlabDB._connection_singleton is None:
            IotlabDB._connection_singleton = IotlabDB.Singleton(config, debug)

        # Store instance reference as the only member in the handle
        self._EventHandler_singleton = IotlabDB._connection_singleton

    def __getattr__(self, aAttr):
        """
        Delegate access to implementation.

        :param aAttr: Attribute wanted.
        :returns: Attribute
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
        :param tablename: name of the table in the db that has to be checked.
        :type tablename: string
        :returns: True if the table exists, False otherwise.
        :rtype: bool

        """
        metadata = MetaData(bind=self.iotlab_engine)
        try:
            table = Table(tablename, metadata, autoload=True)
            return True

        except NoSuchTableError:
            logger.log_exc("IOTLABPOSTGRES tablename %s does not exist"
                           % (tablename))
            return False

    def createtable(self):
        """
        Creates all the table sof the engine.
        Uses the global dictionnary holding the tablenames and the table schema.

        """

        logger.debug("IOTLABPOSTGRES createtable \
                    IotlabBase.metadata.sorted_tables %s \r\n engine %s"
                     % (IotlabBase.metadata.sorted_tables, self.iotlab_engine))
        IotlabBase.metadata.create_all(self.iotlab_engine)
        return
