from sqlalchemy import Table, MetaData, Column, ForeignKey
from sqlalchemy import Integer, String
from sfa.storage.model import SliverAllocation

metadata=MetaData()

def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    SliverAllocation.create()

def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    SliverAllocation.drop()
