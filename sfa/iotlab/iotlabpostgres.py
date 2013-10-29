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
# tablenames_dict = {'lease_table': slice_table}


TestbedBase = declarative_base()


class LeaseTableXP (TestbedBase):
    """ SQL alchemy class to manipulate the rows of the slice_iotlab table in
    lease_table database. Handles the records representation and creates the
    table if it does not exist yet.

    """
    __tablename__ = 'lease_table'

    slice_hrn = Column(String)
    experiment_id = Column(Integer, primary_key=True)
    end_time = Column(Integer, nullable=False)

    def __init__(self, slice_hrn=None, experiment_id=None,  end_time=None):
        """
        Defines a row of the slice_iotlab table
        """
        if slice_hrn:
            self.slice_hrn = slice_hrn
        if experiment_id:
            self.experiment_id = experiment_id
        if end_time:
            self.end_time = end_time

    def __repr__(self):
        """Prints the SQLAlchemy record to the format defined
        by the function.
        """207
        result = "<lease_table : slice_hrn = %s , experiment_id %s end_time = %s" \
            % (self.slice_hrn, self.experiment_id, self.end_time)
        result += ">"
        return result


class TestbedAdditionalSfaDB(object):
    """ SQL Alchemy connection class.
    From alchemy.py
    """
    # Stores the unique Singleton instance-
    _connection_singleton = None
    # defines the database name
    dbname = "testbed_xp"

    class Singleton:
        """
        Class used with this Python singleton design pattern to allow the
        definition of one single instance of iotlab db session in the whole
        code. Wherever a conenction to the database is needed, this class
        returns the same instance every time. Removes the need for global
        variable throughout the code.
        """

        def __init__(self, config, debug=False):
            self.testbed_engine = None
            self.testbed_session = None
            self.url = None
            self.create_testbed_engine(config, debug)
            self.session()

        def create_testbed_engine(self, config, debug=False):
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
                   config.SFA_DB_PORT, TestbedAdditionalSfaDB.dbname)

            # the TCP fallback method
            tcp_url = "postgresql+psycopg2://%s:%s@%s:%s/%s" \
                % (config.SFA_DB_USER, config.SFA_DB_PASSWORD,
                    config.SFA_DB_HOST, config.SFA_DB_PORT, TestbedAdditionalSfaDB.dbname)

            for url in [unix_url, tcp_url]:
                try:
                    self.testbed_engine = create_engine(
                        url, echo_pool=l_echo_pool, echo=l_echo)
                    self.check()
                    self.url = url
                    return
                except:
                    pass
                self.testbed_engine = None

            raise Exception("Could not connect to database")

        def check(self):
            """ Check if a table exists by trying a selection
            on the table.

            """
            self.testbed_engine.execute("select 1").scalar()


        def session(self):
            """
            Creates a SQLalchemy session. Once the session object is created
            it should be used throughout the code for all the operations on
            tables for this given database.

            """
            if self.testbed_session is None:
                Session = sessionmaker()
                self.testbed_session = Session(bind=self.testbed_engine)
            return self.testbed_session

        def close_session(self):
            """
            Closes connection to database.

            """
            if self.testbed_session is None:
                return
            self.testbed_session.close()
            self.testbed_session = None


        def update_experiments_in_additional_sfa_db(self,
            experiment_list_from_testbed, experiment_list_in_db):
            """ Cleans the iotlab db by deleting expired and cancelled jobs.

            Compares the list of experiment ids given by the testbed with the
            experiment ids that are already in the database, deletes the
            experiments that are no longer in the testbed experiment id list.

            :param  experiment_list_from_testbed: list of experiment ids coming
                from testbed
            :type experiment_list_from_testbed: list
            :param experiment_list_in_db: list of experiment ids from the sfa
                additionnal database.
            :type experiment_list_in_db: list

            :returns: None
            """
            #Turn the list into a set
            set_experiment_list_in_db = set(experiment_list_in_db)

            kept_experiments = set(experiment_list_from_testbed).intersection(set_experiment_list_in_db)
            logger.debug("\r\n \t update_experiments_in_additional_sfa_db \
                            experiment_list_in_db %s \r\n \
                            experiment_list_from_testbed %s \
                            kept_experiments %s "
                         % (set_experiment_list_in_db,
                          experiment_list_from_testbed, kept_experiments))
            deleted_experiments = set_experiment_list_in_db.difference(
                kept_experiments)
            deleted_experiments = list(deleted_experiments)
            if len(deleted_experiments) > 0:
                self.testbed_session.query(LeaseTableXP).filter(LeaseTableXP.experiment_id.in_(deleted_experiments)).delete(synchronize_session='fetch')
                self.testbed_session.commit()
            return

    def __init__(self, config, debug=False):
        self.sl_base = TestbedBase

         # Check whether we already have an instance
        if TestbedAdditionalSfaDB._connection_singleton is None:
            TestbedAdditionalSfaDB._connection_singleton = \
                TestbedAdditionalSfaDB.Singleton(config, debug)

        # Store instance reference as the only member in the handle
        self._EventHandler_singleton = \
            TestbedAdditionalSfaDB._connection_singleton

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
        metadata = MetaData(bind=self.testbed_engine)
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
                    TestbedBase.metadata.sorted_tables %s \r\n engine %s"
                     % (TestbedBase.metadata.sorted_tables, self.testbed_engine))
        TestbedBase.metadata.create_all(self.testbed_engine)
        return
