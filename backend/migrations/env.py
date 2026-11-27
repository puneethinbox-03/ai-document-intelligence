from alembic import context
from sqlalchemy import create_engine, pool

from app.core.database import DATABASE_URL
from app.models.base import Base

# Import every model so all tables are registered in Base.metadata.
import app.models.user
import app.models.user_session
import app.models.auth_token
import app.models.document
import app.models.chat
import app.models.message
import app.models.processing_job
import app.models.audit_event
import app.models.usage_event
import app.models.processing_outbox


config = context.config

# SQLAlchemy metadata used by Alembic autogeneration.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate migration SQL without opening a database connection."""

    url = DATABASE_URL.render_as_string(hide_password=False)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using an active PostgreSQL connection."""

    connectable = create_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )

            with context.begin_transaction():
                context.run_migrations()

    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
