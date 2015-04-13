# -*- coding:utf-8 -*-
"""  PostGreSQL table management """

from sfa.storage.model import Base
from sqlalchemy import Column, Integer, String


class LeaseTable(Base):
    """ SQL alchemy class to manipulate the rows of the lease_table table in the
    SFA database. Table creation is made by the importer (iotlabimporter.py)
    if it is not in the database yet.

    As we don't have a link between a lease (OAR job submission) and a slice we
    store this information in database. We matched OAR job id and slice hrn.
    """
    # pylint:disable=R0903
    __tablename__ = 'lease_table'

    job_id = Column(Integer, primary_key=True)
    slice_hrn = Column(String)

    def __init__(self, job_id, slice_hrn):
        """
        Defines a row of the lease_table table
        """
        self.job_id = job_id
        self.slice_hrn = slice_hrn

    def __repr__(self):
        """Prints the SQLAlchemy record to the format defined
        by the function.
        """
        result = "job_id %s, slice_hrn = %s" % (self.job_id,
                                                self.slice_hrn)
        return result
