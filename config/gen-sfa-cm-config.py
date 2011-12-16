#!/usr/bin/python
import os
import sys
import socket
sys.path.append('/usr/share/plc_api')
from sfa.util.config import Config as SfaConfig
from PLC.Config import Config as PlcConfig

sfa_config = SfaConfig()
plc_config = PlcConfig()
default_host = socket.gethostbyname(socket.gethostname())
all_vars = ['SFA_CONFIG_DIR', 'SFA_DATA_DIR', 'SFA_INTERFACE_HRN',
            'SFA_CM_SLICE_PREFIX', 'SFA_REGISTRY_HOST', 'SFA_REGISTRY_PORT', 
            'SFA_AGGREGATE_HOST', 'SFA_AGGREGATE_PORT', 
            'SFA_SM_HOST', 'SFA_SM_PORT',
            'SFA_CM_ENABLED', 'SFA_CM_HOST', 'SFA_CM_PORT', 'SFA_CM_TYPE', 'SFA_CM_SLICE_PREFIX',
            'SFA_API_LOGLEVEL']

defaults = {
    'SFA_CM_ENABLED': '1',
    'SFA_CM_HOST': 'localhost',
    'SFA_CM_PORT': '12346',
    'SFA_CM_SLICE_PREFIX': plc_config.PLC_SLICE_PREFIX,
    'SFA_CM_TYPE': 'pl',
    'SFA_API_LOGLEVEL': '0'
    }

host_defaults = {
    'SFA_REGISTRY_HOST': default_host,
    'SFA_AGGREGATE_HOST': default_host,
    'SFA_SM_HOST': default_host,    
    }
     
const_dict = {}
for key in all_vars:
    value = ""
    
           
    if key in defaults:
        value = defaults[key]
    elif hasattr(sfa_config, key):
        value = getattr(sfa_config, key)
        # sfa_config may specify localhost instead of a resolvalbe host or ip
        # if so replace this with the host's address
        if key in host_defaults and value in ['localhost', '127.0.0.1']:
            value = host_defaults[key] 
    const_dict[key] = value

filename = sfa_config.config_path + os.sep + 'sfa_component_config'
conffile = open(filename, 'w')
format='%s="%s"\n'

for var in all_vars:
    conffile.write(format % (var, const_dict[var]))

conffile.close() 
    

