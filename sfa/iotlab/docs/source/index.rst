.. Iotlab SFA driver documentation master file, created by
   sphinx-quickstart on Tue Jul  2 11:53:15 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Iotlab SFA driver's documentation!
=============================================

===================
Code tree overview
===================

------
Driver
------

The Iotlab driver source code is under the folder /sfa, along with the other
testbeds driver folders. The /iotlab directory contains the necessary files
defining API for OAR, LDAP, the postgresql database as well as for the SFA
managers.

The OAR API enables the user to get information regarding nodes and jobs:
nodes and their properties (hostnames, radio and so on), jobs and the associated
username and nodes. These are used when querying the testbed about resources
and leases. In order to add a new node property in the iotlab Rspec format,
the new property must be defined and parsed beforehand from OAR in the OAR
API file.

In the LDAP file, the LDAPapi class supposes the unix schema is used.
If this class is reused in another context, it might not work without some bit
of customization. The naming (turning a hostname into a sfa hrn, a LDAP login
into a hrn ) is also done in this class.

The iotlabpostgres file defines a dedicated iotlab database, separated from the
SFA database. Its purpose is to hold information that we can't store anywhere
given the Iotlab architecture with OAR and LDAP, namely the association of a
job and the slice hrn for which the job is supposed to run. Indeed, one user
may register on another federated testbed then use his federated slice to book
iotlab nodes. In this case, an Iotlab LDAP account will be created. Later on,
when new users will be imported from the LDAP to the SFA database, an Iotlab
slice will be  created for each new user found in the LDAP. Thus leading us to
the situation where one user may have the possibility to use different slices
to book Iotlab nodes.

----------------------------
RSpec specific Iotlab format
----------------------------

There is a specific Iotlab Rspec format. It aims at displaying information that
is not hadled in the SFA Rspec format. Typically, it adds the nodes' mobility
and its mobility type, the hardware architecture as well as the radio
chipset used. This is done by defining a iotlabv1 rspec version format file
under /rspecs/versions. Definitions of an iotlab rspec lease, node and sliver
are done in the associated files under /rspecs/elements/versions.
If a property has to be added to the nodes in the Iotlab Rspec format, it
should be added in the iotlabv1Node file, using the other properties as example.

--------
Importer
--------

The iotlab importer task is to populate the SFA database with records created
from the information given by OAR and LDAP. Running the importer periodically
enables the SFA database to be in sync with the LDAP by deleting/ adding records
in the database corresponding to newly deleted/ added users in LDAP.



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

