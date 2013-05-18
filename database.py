from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine import reflection
from sqlalchemy import create_engine
from sqlalchemy.schema import (
    MetaData,
    Table,
    DropTable,
    ForeignKeyConstraint,
    DropConstraint,
    )

engine = create_engine('sqlite:////tmp/test.db', convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
    # you will have to import them first before calling init_db()

    import models
    Base.metadata.create_all(bind=engine)


def force_drop_all():
	conn = engine.connect()

	# the transaction only applies if the DB supports
	# transactional DDL, i.e. Postgresql, MS SQL Server
	trans = conn.begin()

	inspector = reflection.Inspector.from_engine(engine)

	# gather all data first before dropping anything.
	# some DBs lock after things have been dropped in 
	# a transaction.

	metadata = MetaData()

	tbs = []
	all_fks = []

	for table_name in inspector.get_table_names():
	    fks = []
	    for fk in inspector.get_foreign_keys(table_name):
	        if not fk['name']:
	            continue
	        fks.append(
	            ForeignKeyConstraint((),(),name=fk['name'])
	            )
	    t = Table(table_name,metadata,*fks)
	    tbs.append(t)
	    all_fks.extend(fks)

	for fkc in all_fks:
	    conn.execute(DropConstraint(fkc))

	for table in tbs:
	    conn.execute(DropTable(table))

	trans.commit()