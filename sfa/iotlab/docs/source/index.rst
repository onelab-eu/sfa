.. Iotlab SFA driver documentation master file, created by
   sphinx-quickstart on Tue Jul  2 11:53:15 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Iotlab SFA driver's documentation!
=============================================

===================
Code tree overview
===================

------------
Installation
------------
**Using git**

git clone git://git.onelab.eu/sfa.git
cd sfa
git checkout <version>
make version
python setup.py install

<version> can be either geni-v2 or geni-v3.
------
Driver
------
**Folder**:/sfa/sfa/iotlab/

The Iotlab driver source code is under the folder /sfa, along with the other
testbeds driver folders. The /iotlab directory contains the necessary files
defining API for OAR, LDAP, the postgresql table which is hosted in the SFA
database as well as for the SFA managers.

The OAR API enables the user to get information regarding nodes and jobs:
nodes properties (hostnames, radio, mobility type, position with GPS
coordinates  and so on), jobs and the associated username and nodes.
These are used when querying the testbed about resources
and leases. In order to add a new node property in the iotlab Rspec format,
the new property must be defined and parsed beforehand from OAR in the OAR
API file.

In the LDAP file, the LDAPapi class supposes the unix schema is used.
If this class is reused in another context, it might not work without some bit
of customization. The naming (turning a hostname into a sfa hrn, a LDAP login
into a hrn ) is also done in this class.

The iotlabpostgres file defines a dedicated lease table, hosted in the SFA
database (in SFA version geni-v3) or in a separated and dedicated Iotlab
database(in SFA geni-v2). Its purpose is to hold information that we
can't store anywhere given the Iotlab architecture with OAR and LDAP, namely the
association of a job and the slice hrn for which the job is supposed to run.
Indeed, one user may register on another federated testbed then use his
federated slice to book iotlab nodes. In this case, an Iotlab LDAP account will
be created. Later on, when new users will be imported from the LDAP to the SFA
database, an Iotlab slice will be  created for each new user found in the LDAP.
Thus leading us to the situation where one user may have the possibility to use
different slices to book Iotlab nodes.

----------------------------
RSpec specific Iotlab format
----------------------------
**Folder**:/sfa/rspecs/versions , /sfa/rpecs/elements

There is a specific Iotlab Rspec format. It aims at displaying information that
is not hadled in the SFA Rspec format. Typically, it adds the nodes' mobility
and its mobility type, the hardware architecture as well as the radio
chipset used. This is done by defining a iotlabv1 rspec version format file
under /rspecs/versions. Definitions of an iotlab rspec lease, node and sliver
are done in the associated files under /rspecs/elements/versions.
If a property has to be added to the nodes in the Iotlab Rspec format, it
should be added in the iotlabv1Node file, using the other properties as example.

Future work:
The Rspec format has to be validated and stored on a website, as the header
of the return Rspec defines it, which is not the case with the Iotlab rspec
format. It has been discussed with Mohamed Larabi (Inria Sophia) once, never to
be mentionned again. Although this does not prevent the SFA server from working,
maybe it would be nice to be completely compliantand clean in this aspect also.
-SA Dec 2013-

--------
Importer
--------
**Folder**: /sfa/importer/

The iotlab importer task is to populate the SFA database with records created
from the information given by OAR and LDAP. Running the importer periodically
enables the SFA database to be in sync with the LDAP by deleting/ adding records
in the database corresponding to newly deleted/ added users in LDAP.

--------------
Documentation
--------------
**Folder** : /sfa/sfa/iotlab/docs

Thsi folder contains the sphinx files needed to generate this documentation.
As of Dec 2013, and because of the SFA database connexion methods, generating
the documentation fails if the database is not accessible. In this case,
Iotlabimporter will not be documented.
A possible workaround is to build the documentation on the SFA server hosting
the SFA database (which is not a really clean way to this...).
To ngenerate the documentation, do "make html" in the /docs folder, where the
Makefile is located. The package python-sphinx must be installed in order
for this command to work.


--------
Testing
--------
Two scripts have been written to help with the testing. One is dedicated for
testing the Iotlab driver, OAR and LDAP classes. The second is to check if the
client commands work well.

**Folder** : /sfa/testbeds/iotlab/tests

* driver_tests.py : python script to test OAR, LDAP and Iotlabdriver/ IotlabShell
  methods. Modify the script to add more tests if needed.

    **starting the script** :python ./driver_tests <-option value> <option>
    example : python ./driver_tests -10 OAR (10 is the job_id in this case)
    option can be : OAR, sql, shell, LDAP , driver, all.

* sfi_client_tests.py : python script to test all the sfi client commands :
  resources, list, allocate (geni-v3), provision(geni-v3), resources, show, status
  and delete. In the geni-v2 branch, this script uses create_sliver instead.

    **starting the script** : python ./sfi_client_tests.py <absolute path to the
    rspecs>.
    The Rspecs are included in the git repository under ./sfa/testbeds/iotlab/tests/tests_rspecs.



.. toctree::
   :maxdepth: 2

Code Documentation
==================

.. toctree::
   :maxdepth: 2

   iotlab.rst
   versions.rst
   importer.rst



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

