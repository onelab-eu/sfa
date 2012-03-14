import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sfa.util.config import Config
from sfa.util.sfalogging import logger

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import Table, Column, MetaData, join, ForeignKey
import sfa.storage.model as model

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref


from sqlalchemy import MetaData, Table
from sqlalchemy.exc import NoSuchTableError

#Dict holding the columns names of the table as keys
#and their type, used for creation of the table
slice_table = {'record_id_user':'integer PRIMARY KEY references X ON DELETE CASCADE ON UPDATE CASCADE','oar_job_id':'integer DEFAULT -1',  'record_id_slice':'integer', 'slice_hrn':'text NOT NULL'}

#Dict with all the specific senslab tables
tablenames_dict = {'slice_senslab': slice_table}

##############################



SlabBase = declarative_base()




class SlabSliceDB (SlabBase):
    __tablename__ = 'slice_senslab' 
    record_id_user = Column(Integer, primary_key=True)
    oar_job_id = Column( Integer,default = -1)
    record_id_slice = Column(Integer)
    slice_hrn = Column(String,nullable = False)
    
    def __init__ (self, slice_hrn =None, oar_job_id=None, record_id_slice=None, record_id_user= None):
        if record_id_slice: 
            self.record_id_slice = record_id_slice
        if slice_hrn:
            self.slice_hrn = slice_hrn
        if oar_job_id:
            self.oar_job_id = oar_job_id
        if slice_hrn:
            self.slice_hrn = slice_hrn 
        if record_id_user: 
            self.record_id_user= record_id_user
            
    def __repr__(self):
        result="<Record id user =%s, slice hrn=%s, oar_job id=%s,Record id slice =%s" % \
                (self.record_id_user, self.slice_hrn, self.oar_job_id, self.record_id_slice)
        result += ">"
        return result
          
            

          
class SlabDB:
    def __init__(self,config):
        self.sl_base = SlabBase

        dbname="slab_sfa"
        # will be created lazily on-demand
        self.slab_session = None
        # the former PostgreSQL.py used the psycopg2 directly and was doing
        #self.connection.set_client_encoding("UNICODE")
        # it's unclear how to achieve this in sqlalchemy, nor if it's needed at all
        # http://www.sqlalchemy.org/docs/dialects/postgresql.html#unicode
        # we indeed have /var/lib/pgsql/data/postgresql.conf where
        # this setting is unset, it might be an angle to tweak that if need be
        # try a unix socket first - omitting the hostname does the trick
        unix_url = "postgresql+psycopg2://%s:%s@:%s/%s"%\
            (config.SFA_DB_USER,config.SFA_DB_PASSWORD,config.SFA_DB_PORT,dbname)
        print >>sys.stderr, " \r\n \r\n SLAPOSTGRES INIT unix_url %s" %(unix_url)
        # the TCP fallback method
        tcp_url = "postgresql+psycopg2://%s:%s@%s:%s/%s"%\
            (config.SFA_DB_USER,config.SFA_DB_PASSWORD,config.SFA_DB_HOST,config.SFA_DB_PORT,dbname)
        for url in [ unix_url, tcp_url ] :
            try:
                self.slab_engine = create_engine (url,echo_pool=True,echo=True)
                self.check()
                self.url=url
                return
            except:
                pass
        self.slab_engine=None
        raise Exception,"Could not connect to database"

    def check (self):
        self.slab_engine.execute ("select 1").scalar()


    def session (self):
        if self.slab_session is None:
            Session=sessionmaker ()
            self.slab_session=Session(bind=self.slab_engine)
        return self.slab_session
        
        
   
        
    #Close connection to database
    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
            
   
        
        
    def exists(self, tablename):
        """
        Checks if the table specified as tablename exists.
    
        """
       
        try:
            metadata = MetaData (bind=self.slab_engine)
            table=Table (tablename, metadata, autoload=True)
           
            return True
        except NoSuchTableError:
            print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES EXISTS NOPE! tablename %s " %(tablename)
            return False
       
    
    def createtable(self, tablename ):
        """
        Creates the specifed table. Uses the global dictionnary holding the tablenames and
        the table schema.
    
        """

        print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES createtable SlabBase.metadata.sorted_tables %s \r\n engine %s" %(SlabBase.metadata.sorted_tables , slab_engine)
        SlabBase.metadata.create_all(slab_engine)
        return
    

    def find (self, name = None, filter_dict = None):
        if filter_dict:
            filter_statement = "and_(SlabSliceDB."
            for k in filter_dict:
                filter_statement += str(k)+ "==" + str(filter_dict[l])
            filter_statement +=')'
            print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES find filter_statement %s"%(filter_statement)
        slab_dbsession.query(SlabSliceDB).filter(filter_statement)
        
       


from sfa.util.config import Config

slab_alchemy= SlabDB(Config())
slab_engine=slab_alchemy.slab_engine
slab_dbsession=slab_alchemy.session()