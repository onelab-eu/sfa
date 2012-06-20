# this move is about adding a authority x user many to many relation ship for modelling PIs
# that is to say users who can vouch for other users in the authority, and can create slices

from sqlalchemy import Table, MetaData, Column, ForeignKey
from sqlalchemy import Integer, String

metadata=MetaData()

# this is needed by migrate so it can locate 'records.record_id'
records = \
    Table ( 'records', metadata,
            Column ('record_id', Integer, primary_key=True),
            )

# authority x user (PIs) association
authority_pi_table = \
    Table ( 'authority_pi', metadata,
            Column ('authority_id', Integer, ForeignKey ('records.record_id'), primary_key=True),
            Column ('pi_id', Integer, ForeignKey ('records.record_id'), primary_key=True),
            )

def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    authority_pi_table.create()

def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    authority_pi_table.drop()
