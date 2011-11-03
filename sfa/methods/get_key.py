import os
import tempfile
import commands
from sfa.util.faults import NonExistingRecord, RecordNotFound
from sfa.util.xrn import hrn_to_urn
from sfa.util.method import Method
from sfa.util.parameter import Parameter
from sfa.util.table import SfaTable
from sfa.trust.certificate import Keypair
from sfa.trust.gid import create_uuid

class get_key(Method):
    """
    Generate a new keypair and gid for requesting caller (component).     
    @return 1 If successful  
    """

    interfaces = ['registry']
    
    accepts = []

    returns = Parameter(int, "1 if successful, faults otherwise")
    
    def call(self):
        # verify that the callers's ip address exist in the db and is an inteface
        # for a node in the db
        (ip, port) = self.api.remote_addr
        interfaces = self.api.plshell.GetInterfaces(self.api.plauth, {'ip': ip}, ['node_id'])
        if not interfaces:
            raise NonExistingRecord("no such ip %(ip)s" % locals())
        nodes = self.api.plshell.GetNodes(self.api.plauth, [interfaces[0]['node_id']], ['node_id', 'hostname'])
        if not nodes:
            raise NonExistingRecord("no such node using ip %(ip)s" % locals())
        node = nodes[0]
       
        # look up the sfa record
        table = SfaTable()
        records = table.findObjects({'type': 'node', 'pointer': node['node_id']})
        if not records:
            raise RecordNotFound("pointer:" + str(node['node_id']))  
        record = records[0]
        
        # generate a new keypair and gid
        uuid = create_uuid()
        pkey = Keypair(create=True)
        urn = hrn_to_urn(record['hrn'], record['type'])
        gid_object = self.api.auth.hierarchy.create_gid(urn, uuid, pkey)
        gid = gid_object.save_to_string(save_parents=True)
        record['gid'] = gid
        record.set_gid(gid)

        # update the record
        table.update(record)
  
        # attempt the scp the key
        # and gid onto the node
        # this will only work for planetlab based components
        (kfd, key_filename) = tempfile.mkstemp() 
        (gfd, gid_filename) = tempfile.mkstemp() 
        pkey.save_to_file(key_filename)
        gid_object.save_to_file(gid_filename, save_parents=True)
        host = node['hostname']
        key_dest="/etc/sfa/node.key"
        gid_dest="/etc/sfa/node.gid" 
        scp = "/usr/bin/scp" 
        #identity = "/etc/planetlab/root_ssh_key.rsa"
        identity = "/etc/sfa/root_ssh_key"
        scp_options=" -i %(identity)s " % locals()
        scp_options+="-o StrictHostKeyChecking=no " % locals()
        scp_key_command="%(scp)s %(scp_options)s %(key_filename)s root@%(host)s:%(key_dest)s" %\
                         locals()
        scp_gid_command="%(scp)s %(scp_options)s %(gid_filename)s root@%(host)s:%(gid_dest)s" %\
                         locals()    

        all_commands = [scp_key_command, scp_gid_command]
        
        for command in all_commands:
            (status, output) = commands.getstatusoutput(command)
            if status:
                raise Exception, output

        for filename in [key_filename, gid_filename]:
            os.unlink(filename)

        return 1 
