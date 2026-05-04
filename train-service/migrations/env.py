from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, text
from alembic import context
import sys
from pathlib import Path

# Add app to path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.infra.db.base import Base

from app.infra.db.models import *

settings = get_settings()

# Alembic config object
config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata

# Debug: Print detected tables


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=settings.db_schema,
        include_schemas=True,  # ← Agregar
        include_object=include_object,  # ← Agregar
    )

    with context.begin_transaction():
        context.run_migrations()


def include_schema(name, schema_name, parent_names):
    """
    Filtra por nombre de esquema.
    Solo permite el esquema 'train'
    """
    return name == settings.db_schema  # 'train'


def include_object(object, name, type_, reflected, compare_to):
    """
    Filtra objetos de otros esquemas.
    Solo incluye objetos del esquema 'train'
    """
    # Obtener el esquema del objeto
    if reflected:
        # Para objetos existentes en la BD
        schema = getattr(object, 'schema', None)
    else:
        # Para objetos de los modelos
        schema = getattr(object, 'schema', None)
    
    # Solo incluir si el esquema es 'train' o None (para objetos sin esquema)
    if schema is not None and schema != settings.db_schema:
        return False
    
    # Excluir la tabla alembic_version de las comparaciones
    if type_ == 'table' and name == 'alembic_version':
        return False
    
    return True


def run_migrations_online():
    from sqlalchemy import create_engine

    engine = create_engine(
        settings.database_url, 
        poolclass=pool.NullPool,
        isolation_level="AUTOCOMMIT")

    with engine.connect() as connection:

        # Configurar search_path al esquema train
        connection.execute(text(f"SET search_path TO {settings.db_schema}"))

        context.configure(
            connection=connection,
            target_metadata=target_metadata,

            # Tabla de versiones en el esquema train
            version_table="alembic_version",
            version_table_schema=settings.db_schema,

            # Filtros para ignorar otros esquemas
            include_schemas=True,
            include_name=include_schema,  #filtrar por nombre de esquema
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()