.. cortexlab_sfa_driver documentation master file, created by
   sphinx-quickstart on Mon Nov 18 12:11:50 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to cortexlab_sfa_driver's documentation!
================================================

===================
Code tree overview
===================

------
Driver
------

The Cortexlab driver source code is under the folder /sfa, along with the other
testbeds driver folders. The /cortexlab directory contains the necessary files
defining API for LDAP, the postgresql database as well as for the SFA
managers.

CortexlabShell
--------------

**fill missing code in this class**

This class contains methods to check reserved nodes, leases and launch/delete
experiments on the testbed. Methods interacting with the testbed have
to be completed.

Cortexlabnodes
---------------

**fill missing code in this class**

CortexlabQueryTestbed class's goal is to get information from the testbed
about the site and its nodes.
There are two types of information about the nodes:

* their properties : hostname, radio type, position, site, node_id and so on.
 (For a complete list of properties, please refer to the method
 get_all_nodes in cortexlabnodes.py).

* their availability, whether the node is currently in use, in a scheduled experiment
 in the future or available. The availability of the nodes can be managed by a
 scheduler or a database. The node's availabity status is  modified when it is
 added to/ deleted from an experiment. In SFA, this corresponds to
 creating/deleting a lease involving this node.

Currently, CortexlabQueryTestbed is merely a skeleton of methods that have to be
implemented with the real testbed API in order to provide the functionality
they were designed for (see the cortxlabnodes file for further information
on which methods have to be completed).


In the LDAP file, the LDAPapi class is based on the unix schema.
If this class is reused in another context, it might not work without some bit
of customization. The naming (turning a hostname into a sfa hrn, a LDAP login
into a hrn ) is also done in this class.

The cortexlabpostgres file defines a dedicated cortexlab database, separated from the
SFA database. Its purpose is to hold information that we can't store anywhere
given the Cortexlab architecture with OAR and LDAP, namely the association of a
job and the slice hrn for which the job is supposed to run. Indeed, one user
may register on another federated testbed then use his federated slice to book
cortexlab nodes. In this case, an Cortexlab LDAP account will be created. Later on,
when new users will be imported from the LDAP to the SFA database, a Cortexlab
slice will be  created for each new user found in the LDAP. Thus leading us to
the situation where one user may have the possibility to use different slices
to book Cortexlab nodes.

Contents:

.. toctree::
   :maxdepth: 2



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

