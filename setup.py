#!/usr/bin/python

"""
Installation script for the sfa module
"""

import sys, os, os.path
from glob import glob
import shutil
from distutils.core import setup

bins = [ 
    'config/sfa-config-tty',
    'config/gen-sfa-cm-config.py',
    'sfa/plc/sfa-import-plc.py', 
    'sfa/plc/sfa-nuke-plc.py', 
    'sfa/server/sfa-ca.py', 
    'sfa/server/sfa-server.py', 
    'sfa/server/sfa-clean-peer-records.py', 
    'sfa/server/sfa_component_setup.py', 
    'sfa/client/sfi.py', 
    'sfa/client/getNodes.py',
    'sfa/client/getRecord.py',
    'sfa/client/setRecord.py',
    'sfa/client/sfadump.py',
    'sfa/client/sfiListNodes.py',
    'sfa/client/sfiListSlivers.py',
    'sfa/client/sfiAddSliver.py',
    'sfa/client/sfiDeleteSliver.py',
    'sfa/client/sfiAddAttribute.py',
    'sfa/client/sfiDeleteAttribute.py',
    'sfatables/sfatables',
    'keyconvert/keyconvert.py',
    'flashpolicy/sfa_flashpolicy.py',
    ]

package_dirs = [
    'sfa', 
    'sfa/client',
    'sfa/methods',
    'sfa/plc',
    'sfa/senslab',
    'sfa/server',
    'sfa/trust',
    'sfa/util', 
    'sfa/managers',
    'sfa/managers/vini',
    'sfa/rspecs',
    'sfa/rspecs/elements',
    'sfa/rspecs/versions',
    'sfatables',
    'sfatables/commands',
    'sfatables/processors',
    'flashpolicy',
    ]


data_files = [('/etc/sfa/', [ 'config/aggregates.xml',
                              'config/registries.xml',
                              'config/default_config.xml',
                              'config/sfi_config',
                              'sfa/managers/pl/pl.rng',
                              'sfa/trust/credential.xsd',
                              'sfa/trust/top.xsd',
                              'sfa/trust/sig.xsd',
                              'sfa/trust/xml.xsd',
                              'sfa/trust/protogeni-rspec-common.xsd',
                              'flashpolicy/sfa_flashpolicy_config.xml',
                            ]),
              ('/etc/sfatables/matches/', glob('sfatables/matches/*.xml')),
              ('/etc/sfatables/targets/', glob('sfatables/targets/*.xml')),
              ('/etc/init.d/', ['sfa/init.d/sfa', 'sfa/init.d/sfa-cm'])]

# add sfatables processors as data_files
processor_files = [f for f in glob('sfatables/processors/*') if os.path.isfile(f)]
data_files.append(('/etc/sfatables/processors/', processor_files))
processor_subdirs = [d for d in glob('sfatables/processors/*') if os.path.isdir(d)]
for d in processor_subdirs:
    etc_dir = os.path.join("/etc/sfatables/processors", os.path.basename(d))
    d_files = [f for f in glob(d + '/*') if os.path.isfile(f)]
    data_files.append((etc_dir, processor_files))

initscripts = [ '/etc/init.d/sfa', '/etc/init.d/sfa-cm' ]

if sys.argv[1] in ['uninstall', 'remove', 'delete', 'clean']:
    python_path = sys.path
    site_packages_path = [ os.path.join(p,'sfa') for p in python_path if p.endswith('site-packages')]
    site_packages_path += [ os.path.join(p,'sfatables') for p in python_path if p.endswith('site-packages')]
    remove_dirs = ['/etc/sfa/', '/etc/sfatables'] + site_packages_path
    remove_bins = [ '/usr/bin/' + os.path.basename(bin) for bin in bins ]
    remove_files = remove_bins + initscripts

    # remove files   
    for filepath in remove_files:
        print "removing", filepath, "...",
        try: 
            os.remove(filepath)
            print "success"
        except: print "failed"
    # remove directories 
    for directory in remove_dirs: 
        print "removing", directory, "...",
        try: 
            shutil.rmtree(directory)
            print "success"
        except: print "failed"
else:
    # avoid repeating what's in the specfile already
    setup(name='sfa',
          packages = package_dirs, 
          data_files = data_files,
          ext_modules = [],
          py_modules = [],
          scripts = bins)

