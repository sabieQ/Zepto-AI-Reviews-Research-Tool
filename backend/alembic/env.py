from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.core.config import get_settings
from app.core.database import Base
from app.models import (  # noqa: F401 — register models
    Conversation,
    ConversationChunk,
    Dataset,
    LogEntry,
    Report,
    ResearchQuestion,
    Setting,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
settings = get_settings()
# Escape % for ConfigParser (passwords may contain %40 etc.)
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.database_url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": 15, "sslmode": "require"},
    )
    print("Connecting to database...")
    with connectable.connect() as connection:
        print("Connected. Ensuring extensions...")
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            print("Running migrations...")
            context.run_migrations()
        print("Migrations complete.")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
