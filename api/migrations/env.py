import os

from alembic import context
from sqlalchemy import create_engine

url = os.environ.get("DATABASE_URL")
if not url:
    raise RuntimeError("DATABASE_URL must be set to run migrations")

engine = create_engine(url)
with engine.connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
