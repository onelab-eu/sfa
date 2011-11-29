###########################################################################
#    Copyright (C) 2011 by                                       
#    <savakian@sfa2.grenoble.senslab.info>                                                             
#
# Copyright: See COPYING file that comes with this distribution
#
###########################################################################
import psycopg2
import psycopg2.extensions
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
# UNICODEARRAY not exported yet
psycopg2.extensions.register_type(psycopg2._psycopg.UNICODEARRAY)
from sfa.util.config import Config
from sfa.util.table import SfaTable
# allow to run sfa2wsdl if this is missing (for mac)
import sys
try: import pgdb
except: print >> sys.stderr, "WARNING, could not import pgdb"

slice_table = {'oar_job_id':'integer DEFAULT -1', 'record_id_user':'integer PRIMARY KEY references sfa ON DELETE CASCADE ON UPDATE CASCADE', 'record_id_slice':'integer', 'slice_hrn':'text NOT NULL'}
tablenames_dict = {'slice': slice_table}

class SlabDB:
    def __init__(self):
        self.config = Config()
        self.debug = False

        self.connection = None

    #@handle_exception
    def cursor(self):
        if self.connection is None:
            # (Re)initialize database connection
            if psycopg2:
                try:
                    # Try UNIX socket first                    
                    self.connection = psycopg2.connect(user = 'sfa',
                                                       password = 'sfa',
                                                       database = 'sfa')
                    #self.connection = psycopg2.connect(user = self.config.SFA_PLC_DB_USER,
                                                       #password = self.config.SFA_PLC_DB_PASSWORD,
                                                       #database = self.config.SFA_PLC_DB_NAME)
                except psycopg2.OperationalError:
                    # Fall back on TCP
                    self.connection = psycopg2.connect(user = self.config.SFA_PLC_DB_USER,
                                                       password = self.config.SFA_PLC_DB_PASSWORD,
                                                       database = self.config.SFA_PLC_DB_NAME,
                                                       host = self.config.SFA_PLC_DB_HOST,
                                                       port = self.config.SFA_PLC_DB_PORT)
                self.connection.set_client_encoding("UNICODE")
            else:
                self.connection = pgdb.connect(user = self.config.SFA_PLC_DB_USER,
                                               password = self.config.SFA_PLC_DB_PASSWORD,
                                               host = "%s:%d" % (self.config.SFA_PLC_DB_HOST, self.config.SFA_PLC_DB_PORT),
                                               database = self.config.SFA_PLC_DB_NAME)

        (self.rowcount, self.description, self.lastrowid) = \
                        (None, None, None)

        return self.connection.cursor()
        
    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
            
    def exists(self, tablename):
        mark = self.cursor()
        sql = "SELECT * from pg_tables"
        mark.execute(sql)
        rows = mark.fetchall()
        mark.close()
        labels = [column[0] for column in mark.description]
        rows = [dict(zip(labels, row)) for row in rows]

        rows = filter(lambda row: row['tablename'].startswith(tablename), rows)
        if rows:
            return True
        return False
    
    def createtable(self, tablename ):
        mark = self.cursor()
        tablelist =[]
        T  = tablenames_dict[tablename]
        for k in T.keys(): 
            tmp = str(k) +' ' + T[k]
            tablelist.append(tmp)
        end = ",".join(tablelist)
        
        statement = "CREATE TABLE " + tablename + " ("+ end +");"
     
        #template = "CREATE INDEX %s_%s_idx ON %s (%s);"
        #indexes = [template % ( self.tablename, field, self.tablename, field) \
                    #for field in ['hrn', 'type', 'authority', 'peer_authority', 'pointer']]
        # IF EXISTS doenst exist in postgres < 8.2
        try:
            mark.execute('DROP TABLE IF EXISTS ' + tablename +';')
        except:
            try:
                mark.execute('DROP TABLE' + tablename +';')
            except:
                pass
            
        mark.execute(statement)
        #for index in indexes:
            #self.db.do(index)
        self.connection.commit()
        mark.close()
        #self.connection.close()
        self.close()
        return
    
        
    def findRecords(self,table, column, operator, string):
        mark = self.cursor()
    
        statement =  'SELECT * FROM ' + table + ' WHERE ' + column + ' ' + operator + ' ' + ' \'' + string +'\''
        mark.execute(statement) 
        record = mark.fetchall() 
        mark.close()
        self.connection.close()
        return record


    def insert(self, table, columns,values):
         mark = self.cursor()
         statement = "INSERT INTO " + table + \
                       "(" + ",".join(columns) + ") " + \
                       "VALUES(" + ", ".join(values) + ");"

         #statement = 'INSERT INTO ' + table + ' (' + columns + ') VALUES (' + values + ')' 
         print>>sys.stderr, " \r\n insert statement", statement
         mark.execute(statement) 
         self.connection.commit()
         mark.close()
         #self.connection.close()
         self.close()
         return
    
    def insert_slice(self, person_rec):
        sfatable = SfaTable()
        keys = slice_table.keys()
        
        #returns a list of records (dicts)
        #the filters specified will return only one matching record, into a list of dicts

        userrecord = sfatable.find({'hrn': person_rec['hrn'], 'type':'user'})

        slicerec =  sfatable.find({'hrn': person_rec['hrn']+'_slice', 'type':'slice'})
        if (isinstance (userrecord, list)):
            userrecord = userrecord[0]
        if (isinstance (slicerec, list)):
            slicerec = slicerec[0]
        
        values = [ '-1', ' \''+ str(slicerec['hrn']) + '\'', str(userrecord['record_id']), str( slicerec['record_id'])]

        self.insert('slice', keys, values)
        return
        
    def update(self, table, column_names, values, whereclause, valueclause):

        #Creates the values string for the update SQL command
        if len(column_names) is not len(values):
            return
        else:
            valueslist = []
            valuesdict = dict(zip(column_names,values))
            for k in valuesdict.keys():
                valuesdict[k] = str(valuesdict[k])
                v = ' \''+ str(k) + '\''+ '='+' \''+ valuesdict[k]+'\''
                valueslist.append(v)
                
        statement = "UPDATE %s SET %s WHERE %s = %s" % \
                    (table, ", ".join(valueslist), whereclause, valueclause)
        print >>sys.stderr, "\r\n \r\n \t SLABPOSTGRES.PY UPDATE statement    ", statement
        mark = self.cursor()
        mark.execute(statement) 
        self.connection.commit()
        mark.close()
        self.close()
        #self.connection.close()
        return

    def update_slice(self, slice_rec):
        sfatable = SfaTable()
        userhrn = slice_rec['hrn'].strip('_slice')
        userrecords = sfatable.find({'hrn': userhrn, 'type':'user'})
        columns = [ 'record_user_id', 'oar_job_id']
        values = [slice_rec['record_user_id'],slice_rec['oar_job_id']]
        self.update('slice',columns, values,'record_slice_id', slice_rec['record_slice_id'])
        return 
        
       
       