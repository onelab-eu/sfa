import sys

from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker

from sfa.util.config import Config
from sfa.util.sfalogging import logger

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import Table, Column, MetaData, join, ForeignKey
import sfa.storage.model as model

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref


from sqlalchemy.dialects import postgresql

from sqlalchemy import MetaData, Table
from sqlalchemy.exc import NoSuchTableError

from sqlalchemy import String

#Dict holding the columns names of the table as keys
#and their type, used for creation of the table
slice_table = {'record_id_user':'integer PRIMARY KEY references X ON DELETE CASCADE ON UPDATE CASCADE','oar_job_id':'integer DEFAULT -1',  'record_id_slice':'integer', 'slice_hrn':'text NOT NULL'}

#Dict with all the specific senslab tables
tablenames_dict = {'slice_senslab': slice_table}

##############################



SlabBase = declarative_base()




class SliceSenslab (SlabBase):
    __tablename__ = 'slice_senslab' 
    #record_id_user = Column(Integer, primary_key=True)
    slice_hrn = Column(String,primary_key=True)
    peer_authority = Column( String,nullable = True)
    record_id_slice = Column(Integer)    
    record_id_user = Column(Integer)
    oar_job_id = Column( Integer,default = -1)
    node_list = Column(postgresql.ARRAY(String), nullable =True)
    
    def __init__ (self, slice_hrn =None, oar_job_id=None, record_id_slice=None, record_id_user= None,peer_authority=None):
        self.node_list = []
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
        if peer_authority:
            self.peer_authority = peer_authority
            
            
    def __repr__(self):
        result="<Record id user =%s, slice hrn=%s, oar_job id=%s,Record id slice =%s  node_list =%s peer_authority =%s"% \
                (self.record_id_user, self.slice_hrn, self.oar_job_id, self.record_id_slice, self.node_list, self.peer_authority)
        result += ">"
        return result
          
    def dump_sqlalchemyobj_to_dict(self):
        dict = {'slice_hrn':self.slice_hrn,
        'peer_authority':self.peer_authority,
        'record_id':self.record_id_slice, 
        'record_id_user':self.record_id_user,
        'oar_job_id':self.oar_job_id, 
        'record_id_slice':self.record_id_slice, 
         'node_list':self.node_list}
        return dict       
#class PeerSenslab(SlabBase):
    #__tablename__ = 'peer_senslab' 
    #peername = Column(String, nullable = False)
    #peerid = Column( Integer,primary_key=True)
    
    #def __init__ (self,peername = None ):
        #if peername:
            #self.peername = peername
            
            
      #def __repr__(self):
        #result="<Peer id  =%s, Peer name =%s" % (self.peerid, self.peername)
        #result += ">"
        #return result
          
class SlabDB:
    def __init__(self,config, debug = False):
        self.sl_base = SlabBase
        dbname="slab_sfa"
        if debug == True :
            l_echo_pool = True
            l_echo=True 
        else :
            l_echo_pool = False
            l_echo = False 
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
                self.slab_engine = create_engine (url,echo_pool = l_echo_pool, echo = l_echo)
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
    
    #Updates the job_id and the nodes list 
    #The nodes list is never erased.
    def update_job(self, hrn, job_id= None, nodes = None ):
        slice_rec = slab_dbsession.query(SliceSenslab).filter_by(slice_hrn = hrn).first()
        print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES  update_job slice_rec %s"%(slice_rec)
        if job_id is not None:
            slice_rec.oar_job_id = job_id
        if nodes is not None :
            slice_rec.node_list = nodes
        slab_dbsession.commit()

    def find (self, name = None, filter_dict = None):
        print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES find  filter_dict %s"%(filter_dict)

        #Filter_by can not handle more than one argument, hence these functions
        def filter_id_user(query, user_id):
            print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES find  filter_id_user"
            return query.filter_by(record_id_user = user_id)
        
        def filter_job(query, job):
            print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES find filter_job "
            return query.filter_by(oar_job_id = job)
        
        def filer_id_slice (query, id_slice):
            print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES find  filer_id_slice"
            return query.filter_by(record_id_slice = id_slice)
        
        def filter_slice_hrn(query, hrn):
            print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES find  filter_slice_hrn"
            return query.filter_by(slice_hrn = hrn)
        
        
        extended_filter = {'record_id_user': filter_id_user,
         'oar_job_id':filter_job,
         'record_id_slice': filer_id_slice,
         'slice_hrn': filter_slice_hrn}
         
        Q = slab_dbsession.query(SliceSenslab) 
        
        if filter_dict is not None:
            for k in filter_dict:
                try:
                  newQ= extended_filter[k](Q, filter_dict[k])
                  Q = newQ
                except KeyError:
                    print>>sys.stderr, "\r\n \t\t FFFFFFFFFFFFFFFFUUUUUUUUFUFUFU!!!!!!!!"
        print>>sys.stderr, " HEEEEEEEEEEEEY %s " %(Q.first())
        rec = Q.first()
        print>>sys.stderr, " \r\n \r\n \t SLABPOSTGRES find  rec %s" %(rec)
        return dict(zip(['record_id_user','oar_job_id', 'record_id_slice','slice_hrn'],[rec.record_id_user,rec.oar_job_id,rec.record_id_slice, rec.slice_hrn]))
        #reclist = []
        ##for rec in Q.all():
            #reclist.append(dict(zip(['record_id_user','oar_job_id', 'record_id_slice','slice_hrn'],[rec.record_id_user,rec.oar_job_id,rec.record_id_slice, rec.slice_hrn])))
        #return reclist
        
       


from sfa.util.config import Config

slab_alchemy= SlabDB(Config())
slab_engine=slab_alchemy.slab_engine
slab_dbsession=slab_alchemy.session()
