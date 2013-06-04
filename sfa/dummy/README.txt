######################################  DUMMY TESTBED DRIVER FOR SFA ############################################

In order to make easy the adoption of SFA by the testbed owners, we decided to implement this DUMMY TESTBED DRIVER FOR SFA which represent one flavour of SFA (dummy).

Testbed owners deciding to wrap their testbed with SFA, can follow this small step-by-step guide to know how SFA works, how it interact with the testbed and what are the needed pieces to glue SFA and the testbed.


STEP-BY-STEP GUIDE :

1. Install SFA (http://svn.planet-lab.org/wiki/SFATutorialInstall#InstallingSFA) 
(On RPM based OS, the SFA sources go here : /usr/lib/python2.7/site-packages/sfa )

2. Launch the Dummy testbed XML-RPC API:

# python /usr/lib/python2.7/site-packages/sfa/dummy/dummy_testbed_api.py

3. Configure SFA to the "dummy" flavour as follow :

# sfa-config-tty
Enter command (u for usual changes, w to save, ? for help) u
== sfa_generic_flavour : [dummy] dummy ("dummy" flavour)
== sfa_interface_hrn : [pla] topdomain   (Choose your Authority name)           
== sfa_registry_root_auth : [pla] topdomain (Choose your Authority name)
== sfa_registry_host : [localhost] localhost
== sfa_aggregate_host : [localhost] localhost
== sfa_sm_host : [localhost] localhost
== sfa_db_host : [localhost] localhost
== sfa_dummy_url : [http://127.0.0.1:8080] 
Enter command (u for usual changes, w to save, ? for help) w
Wrote /etc/sfa/configs/site_config
Merged
	/etc/sfa/default_config.xml
and	/etc/sfa/configs/site_config
into	/etc/sfa/sfa_config
You might want to type 'r' (restart sfa), 'R' (reload sfa) or 'q' (quit)
Enter command (u for usual changes, w to save, ? for help) r
==================== Stopping sfa
Shutting down SFA                                          [  OK  ]
==================== Starting sfa
SFA: Checking for PostgreSQL server                        [  OK  ]
SFA: installing peer certs                                 [  OK  ]
SFA: Registry                                              [  OK  ]
SFA: Aggregate                                             [  OK  ]
SFA: SliceMgr                                              [  OK  ]
Enter command (u for usual changes, w to save, ? for help) q

5. Import Dummy testbed data to SFA (users, slices, nodes):

# sfaadmin.py reg import_registry

5. Create a user and a slice:

# sfaadmin.py reg register -t user -x topdomain.dummy.bob -k /root/.ssh/id_rsa.pub -e bob@dummy.net
# sfaadmin.py reg register -t slice -x topdomain.dummy.bob_slice -r topdomain.dummy.bob

6. Configure you SFI client (http://svn.planet-lab.org/wiki/SFATutorialConfigureSFA#ConfigureSFAClientSFI)
Example of sfi_config:
[sfi]
auth = topdomain.dummy
user = topdomain.dummy.bob
registry = http://localhost:12345/
sm = http://localhost:12346/

7. Make a test: 
update the following command with your already configured Authority name. 

# sfi.py list topdomain.dummy 

8. Now continue testing SFA, have a look at the dummy driver code and write your testbed driver for SFA... Enjoy.


