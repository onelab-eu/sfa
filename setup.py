#!/usr/bin/python

"""
Installation script for the sfa module
"""

import sys, os, os.path
from glob import glob
import shutil
from distutils.core import setup

from sfa.util.version import version_tag

scripts = glob("clientbin/*.py") + \
    [ 
    'config/sfa-config-tty',
    'config/sfa-config',
#    'config/gen-sfa-cm-config.py',
    'sfa/server/sfa-start.py', 
#    'sfa/server/sfa_component_setup.py', 
    'sfatables/sfatables',
    'keyconvert/keyconvert.py',
    'flashpolicy/sfa_flashpolicy.py',
    ]

packages = [
    'sfa', 
    'sfa/trust',
    'sfa/storage',
    'sfa/util', 
    'sfa/server',
    'sfa/methods',
    'sfa/generic',
    'sfa/managers',
    'sfa/importer',
    'sfa/rspecs',
    'sfa/rspecs/elements',
    'sfa/rspecs/elements/versions',
    'sfa/rspecs/versions',
    'sfa/client',
    'sfa/planetlab',
    'sfa/nitos',
    'sfa/dummy',
    'sfa/openstack',
    'sfa/federica',
    'sfa/senslab',
    'sfatables',
    'sfatables/commands',
    'sfatables/processors',
    ]

initscripts = [ 'sfa' ]
if not os.path.isfile('/etc/redhat-release'): initscripts.append('functions.sfa')

data_files = [ ('/etc/sfa/', [ 'config/aggregates.xml',
                              'config/registries.xml',
                              'config/default_config.xml',
                              'config/sfi_config',
                              'config/topology',
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
               ('/etc/init.d/', [ "init.d/%s"%x for x in initscripts ]),
               ('/usr/share/sfa/migrations', glob('sfa/storage/migrations/*.*') ),
               ('/usr/share/sfa/migrations/versions', glob('sfa/storage/migrations/versions/*') ),
               ('/usr/share/sfa/examples/', glob('sfa/examples/*' ) + [ 'cron.d/sfa.cron' ] ),
              ]

# add sfatables processors as data_files
processor_files = [f for f in glob('sfatables/processors/*') if os.path.isfile(f)]
data_files.append(('/etc/sfatables/processors/', processor_files))
processor_subdirs = [d for d in glob('sfatables/processors/*') if os.path.isdir(d)]
for d in processor_subdirs:
    etc_dir = os.path.join("/etc/sfatables/processors", os.path.basename(d))
    d_files = [f for f in glob(d + '/*') if os.path.isfile(f)]
    data_files.append((etc_dir, processor_files))

if sys.argv[1] in ['uninstall', 'remove', 'delete', 'clean']:
    python_path = sys.path
    site_packages_path = [ os.path.join(p,'sfa') for p in python_path if p.endswith('site-packages')]
    site_packages_path += [ os.path.join(p,'sfatables') for p in python_path if p.endswith('site-packages')]
    remove_dirs = ['/etc/sfa/', '/etc/sfatables'] + site_packages_path
    remove_bins = [ '/usr/bin/' + os.path.basename(bin) for bin in scripts ]
    remove_files = remove_bins + [ "/etc/init.d/%s"%x for x in initscripts ]

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
          packages = packages, 
          data_files = data_files,
          scripts = scripts,
          url="http://svn.planet-lab.org/wiki/SFATutorial",
          author="Thierry Parmentelat, Tony Mack, Scott Baker",
          author_email="thierry.parmentelat@inria.fr, tmack@princeton.cs.edu, smbaker@gmail.com",
          version=version_tag)

