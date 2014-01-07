#!/usr/bin/env python
import sys
import os
from sfa.iotlab.LDAPapi import LDAPapi
from difflib import SequenceMatcher

def parse_options():

    #arguments supplied
    if len(sys.argv) > 1 :
        options_list = sys.argv[1:]
        print options_list
        rspec_rep = options_list[0]
        return rspec_rep
    else:
    	print "Must supply Rspecs directory ",  sys.argv[1:]
    	return


rspec_dir = parse_options()
print "DIRECTORY SUPPLIED" , rspec_dir
rspec_filename_list = ['firexp_avakian_slice_iotlab.rspec',
'firexp_iotlab_slice_iotlab.rspec',
'iotlab_avakian_slice_iotlab2.rspec',
'iotlab_avakian_slice_plab.rspec',
'firexp_iotlab_slice_all.rspec',
'iotlab_avakian_slice_all.rspec',
'iotlab_avakian_slice_iotlab.rspec',
'iotlab_user_slice_iotlab.rspec',
'test_delete_all_leases.rspec']

rspec_filename_dict = {
	('iotlab_avakian', 'iotlab', 'allocate' ):
		"sfi.py allocate iotlab.avakian_slice " + rspec_dir + \
			'iotlab_avakian_slice_iotlab.rspec',

	('iotlab_avakian', 'iotlab2', 'allocate'):
		"sfi.py allocate iotlab.avakian_slice " + rspec_dir + \
		'iotlab_avakian_slice_iotlab2.rspec',

	('firexp_user','iotlab', 'allocate'):
		"sfi.py allocate firexp.flab.iotlab_slice " + rspec_dir + \
			'firexp_iotlab_slice_iotlab.rspec',

	('firexp_user', 'all', 'allocate'):
			"sfi.py allocate firexp.flab.iotlab_slice "+ rspec_dir + \
				'firexp_iotlab_slice_all.rspec',

	('iotlab_user', 'iotlab', 'allocate'):
		"sfi.py allocate iotlab.user_slice "+ rspec_dir + \
			'iotlab_user_slice_iotlab.rspec',

	('firexp_avakian','iotlab', 'allocate'):
		"sfi.py allocate firexp.flab.avakian_slice " + rspec_dir + \
			'firexp_avakian_slice_iotlab.rspec',

	('iotlab_avakian', 'plab', 'allocate') :
			"sfi.py allocate iotlab.avakian_slice " + rspec_dir + \
				'iotlab_avakian_slice_plab.rspec',

	('iotlab_avakian', 'all', 'allocate') :
	 "sfi.py allocate iotlab.avakian_slice " + rspec_dir + \
		'iotlab_avakian_slice_all.rspec',

    ('iotlab_avakian', 'iotlab', 'provision' ):
        "sfi.py provision iotlab.avakian_slice",

    ('iotlab_avakian', 'iotlab2', 'provision'):
        "sfi.py provision iotlab.avakian_slice",

    ('firexp_user','iotlab', 'provision'):
        "sfi.py provision firexp.flab.iotlab_slice",

    ('firexp_user', 'all', 'provision'):
            "sfi.py provision firexp.flab.iotlab_slice",

    ('iotlab_user', 'iotlab', 'provision'):
        "sfi.py provision iotlab.user_slice",

    ('firexp_avakian','iotlab', 'provision'):
        "sfi.py provision firexp.flab.avakian_slice",

    ('iotlab_avakian', 'plab', 'provision') :
            "sfi.py provision iotlab.avakian_slice",

    ('iotlab_avakian', 'all', 'provision') :
     "sfi.py provision iotlab.avakian_slice",

    ('iotlab_avakian', 'iotlab', 'describe' ):
        "sfi.py describe iotlab.avakian_slice iotlab_avakian_slice_iotlab.rspec",

    ('iotlab_avakian', 'iotlab2', 'describe'):
        "sfi.py describe iotlab.avakian_slice iotlab_avakian_slice_iotlab2.rspec",

    ('firexp_user','iotlab', 'describe'):
        "sfi.py describe firexp.flab.iotlab_slice firexp_iotlab_slice_iotlab.rspec",

    ('firexp_user', 'all', 'describe'):
            "sfi.py describe firexp.flab.iotlab_slice firexp_iotlab_slice_all.rspec",

    ('iotlab_user', 'iotlab', 'describe'):
        "sfi.py describe iotlab.user_slice iotlab_user_slice_iotlab.rspec",

    ('firexp_avakian','iotlab', 'describe'):
        "sfi.py describe firexp.flab.avakian_slice firexp_avakian_slice_iotlab.rspec",

    ('iotlab_avakian', 'plab', 'describe') :
            "sfi.py describe iotlab.avakian_slice iotlab_avakian_slice_plab.rspec",

    ('iotlab_avakian', 'all', 'describe') :
     "sfi.py describe iotlab.avakian_slice iotlab_avakian_slice_all.rspec"
	}

print rspec_filename_dict
# check if the firexp user (uid user) is already in LDAP
# in this is the case, delete it :
ldap_server = LDAPapi()
dn = 'uid=' + 'user' + ',' + ldap_server.baseDN
result = ldap_server.LdapSearch('(uid=user)', [])

if result != []:
	retval = ldap_server.LdapDelete(dn)
	print "deleting firexp user : ", retval

# Change the sfi config file to be able to start the experiment on the federated
# testbed with another identity and another slice
print "config sfi"
with open ("/root/.sfi/sfi_config", "r") as sfi_config:
	sfi_config_txt = [line for line in sfi_config]

with open("/root/.sfi/sfi_config_iotlab", "r") as sfi_config_iotlab:
	sfi_config_iotlab_txt = [line for line in sfi_config_iotlab]

with open("/root/.sfi/sfi_config_firexp", "r") as sfi_config_firexp:
	sfi_config_firexp_txt  =  [line for line in sfi_config_firexp]
# check that we are using the iotlab sfi configuration
result1 = SequenceMatcher(None, sfi_config_txt, sfi_config_iotlab_txt)

result2 = SequenceMatcher(None, sfi_config_txt, sfi_config_firexp_txt)

if result1.ratio() != 1.0:
	os.system('cp /root/.sfi/sfi_config_iotlab /root/.sfi/sfi_config')

os.system('cat /root/.sfi/sfi_config')
os.system('rm /root/tests_rspecs/iotlab_devlille_OUTPUT.rspec')

print " =================    SFI.PY LIST IOTLAB        ============="
os.system('sfi.py list iotlab')


print " =================    SFI.PY RESOURCES          ============="
raw_input("Press Enter to continue...")
os.system('sfi.py resources')


print " ================= SFI.PY RESOURCES -R IOTLAB        ============="
raw_input("Press Enter to continue...")
os.system('sfi.py resources -r iotlab')


print " =================    SFI.PY RESOURCES -L ALL      ============="
raw_input("Press Enter to continue...")
os.system('sfi.py resources -l all')

print " ================= SFI.PY RESOURCES -R IOTLAB -L ALL ============="
raw_input("Press Enter to continue...")
os.system('sfi.py resources -r iotlab -l all')

# print " ================= SFI.PY RESOURCES -O  output rspec ==========="
# os.system('sfi.py resources -o /root/tests_rspecs/iotlab_devlille_OUTPUT.rspec')

print " ================= SFI.PY RESOURCES -L LEASES  ============="
raw_input("Press Enter to continue...")
os.system('sfi.py resources -l leases')


print " =================    SFI.PY SHOW USER   ============="
raw_input("Press Enter to continue...")
os.system('sfi.py show iotlab.avakian')

print " =================    SFI.PY SHOW NODE   ============="
os.system('sfi.py show iotlab.m3-3.devgrenoble.iot-lab.info')



print " =================    SFI.PY STATUS SLICE   ============="
os.system('sfi.py status iotlab.avakian_slice')

print " =================    SFI.PY ALLOCATE SLICE  on iotlab only  ============="
raw_input("Press Enter to continue...")
os.system( rspec_filename_dict[('iotlab_avakian','iotlab' , 'allocate')])


print " =================    SFI.PY PROVISION SLICE  on iotlab only  ============="
raw_input("Press Enter to continue...")
os.system( rspec_filename_dict[('iotlab_avakian','iotlab' , 'provision')])


print " =================    SFI.PY DESCRIBE SLICE  on iotlab only  ============="
raw_input("Press Enter to continue...")
os.system( rspec_filename_dict[('iotlab_avakian','iotlab' , 'describe')])


print " ================= SFI.PY RESOURCES -l all iotlab.avakian_slice ============="
raw_input("Press Enter to continue...")
os.system('sfi.py resources -l all iotlab.avakian_slice')


print " =================    SFI.PY DELETE SLICE   ============="
raw_input("Press Enter to continue...")
os.system('sfi.py delete iotlab.avakian_slice')


print " =================    SFI.PY ALLOCATE SLICE  on iotlab and firexp  ============="
raw_input("Press Enter to continue...")
os.system(rspec_filename_dict[('iotlab_avakian','all', 'allocate')])


print " ================= SFI.PY RESOURCES -l all -r iotlab iotlab.avakian_slice ============="
raw_input("Press Enter to continue...")
os.system('sfi.py resources -l all -r iotlab iotlab.avakian_slice')


print " =================SFI.PY RESOURCES -L LEASES -R IOTLAB ============== "
os.system('sfi.py resources -r iotlab -l leases')


print " =================    SFI.PY DELETE SLICE   ============="
raw_input("Press Enter to continue...")
os.system('sfi.py delete iotlab.avakian_slice')

print "\r\n \r\n"

print " *********changing to firexp sfi config ***************"
os.system('cp /root/.sfi/sfi_config_firexp /root/.sfi/sfi_config')



print " =================    SFI.PY ALLOCATE SLICE  on iotlab and firexp  ============="
raw_input("Press Enter to continue...")
os.system(rspec_filename_dict[('firexp_user','all', 'allocate')])

print " =================    SFI.PY DESCRIBE SLICE  on iotlab and firexp  ============="
raw_input("Press Enter to continue...")
os.system(rspec_filename_dict[('firexp_user','all', 'describe')])

print " =================    SFI.PY PROVISION SLICE  on iotlab and firexp  ============="
raw_input("Press Enter to continue...")
os.system(rspec_filename_dict[('firexp_user','all', 'provision')])


print " =================    SFI.PY SHOW SLICE   ============="
raw_input("Press Enter to continue...")
os.system('sfi.py show firexp.flab.iotlab_slice')


print " ================= SFI.PY RESOURCES -l leases firexp.flab.iotlab_slice ============="
raw_input("Press Enter to continue...")
os.system('sfi.py resources -l leases firexp.flab.iotlab_slice')


print " ================= SFI.PY RESOURCES firexp.flab.iotlab_slice  ============="
raw_input("Press Enter to continue...")
os.system('sfi.py resources firexp.flab.iotlab_slice')




