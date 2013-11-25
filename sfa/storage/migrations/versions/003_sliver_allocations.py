from sqlalchemy import Table, MetaData, Column
from sqlalchemy import Integer, String

metadata=MetaData()
sliver_allocation_table = \
    Table ( 'sliver_allocation', metadata,
            Column('sliver_id', String, primary_key=True),
            Column('client_id', String),
            Column('component_id', String),
            Column('slice_urn', String),
            Column('allocation_state', String),
          )

def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    sliver_allocation_table.create()

def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    sliver_allocation_table.drop()
