"""
File holding a class to define the table in the iotlab dedicated table.
The table is the SFA dtabase, therefore all the access mecanism
(session, engine...) is handled by alchemy.py.

..seealso:: alchemy.py
"""

from sfa.storage.model import Base
from sqlalchemy import Column, Integer, String



class LeaseTableXP (Base):
    """ SQL alchemy class to manipulate the rows of the lease_table table in the
    SFA database. Handles the records representation and creates.
    Table creation is made by the importer if it is not in the database yet.

    .. seealso:: init_tables in model.py, run in iotlabimporter.py

    """
    __tablename__ = 'lease_table'

    slice_hrn = Column(String)
    experiment_id = Column(Integer, primary_key=True)
    end_time = Column(Integer, nullable=False)

    def __init__(self, slice_hrn=None, experiment_id=None,  end_time=None):
        """
        Defines a row of the lease_table table
        """
        if slice_hrn:
            self.slice_hrn = slice_hrn
        if experiment_id:
            self.experiment_id = experiment_id
        if end_time:
            self.end_time = end_time

    def __repr__(self):
        """Prints the SQLAlchemy record to the format defined
        by the function.
        """
        result = "<lease_table : slice_hrn = %s , experiment_id %s \
            end_time = %s" % (self.slice_hrn, self.experiment_id,
            self.end_time)
        result += ">"
        return result
