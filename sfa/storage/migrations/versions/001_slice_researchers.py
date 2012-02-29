# this move is about adding a slice x users many to many relation ship for modelling 
# regular "membership" of users in a slice

from sqlalchemy import Table, MetaData, Column, ForeignKey
from sqlalchemy import Integer, String

metadata=MetaData()

# this is needed my migrate so it can locate 'records.record_id'
records = \
    Table ( 'records', metadata,
            Column ('record_id', Integer, primary_key=True),
            )

# slice x user (researchers) association
slice_researcher_table = \
    Table ( 'slice_researcher', metadata,
            Column ('slice_id', Integer, ForeignKey ('records.record_id'), primary_key=True),
            Column ('researcher_id', Integer, ForeignKey ('records.record_id'), primary_key=True),
            )

def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    slice_researcher_table.create()

def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    slice_researcher_table.drop()
