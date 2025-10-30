"""
Schema Extraction Utilities
Provides utilities to extract and update data dictionary from live databases
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import asdict

import psycopg2
from psycopg2.extras import RealDictCursor

from database_schema_extractor import (
    DatabaseSchemaExtractor, DatabaseConnection,
    TableInfo, ColumnInfo, ConstraintInfo, IndexInfo
)
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class SchemaImporter:
    """Imports extracted schema information into the data dictionary."""

    def __init__(self):
        self.extractor = DatabaseSchemaExtractor()

    def get_db_connection(self):
        """Get connection to the data dictionary database."""
        try:
            conn = psycopg2.connect(
                host=settings.db_host,
                port=settings.db_port,
                database=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
            )
            return conn
        except Exception as e:
            logger.error(f"Data dictionary database connection failed: {e}")
            raise

    def import_database_schema(
        self,
        rni_version_id: int,
        conn_config: DatabaseConnection,
        schema_name: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract and import complete database schema into data dictionary.

        Args:
            rni_version_id: ID of the RNI version
            conn_config: Database connection configuration
            schema_name: Specific schema to extract (None for all)
            created_by: User performing the import

        Returns:
            Dictionary with import results and statistics
        """
        start_time = datetime.now()

        try:
            # Extract schema information
            if conn_config.database_type == 'PostgreSQL':
                schema_data = self.extractor.extract_postgresql_schema(conn_config, schema_name)
            elif conn_config.database_type == 'MSSQL':
                schema_data = self.extractor.extract_mssql_schema(conn_config, schema_name)
            else:
                raise ValueError(f"Unsupported database type: {conn_config.database_type}")

            # Import into data dictionary
            import_stats = self._import_schema_data(
                rni_version_id=rni_version_id,
                schema_data=schema_data,
                conn_config=conn_config,
                created_by=created_by
            )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return {
                'status': 'success',
                'duration_seconds': duration,
                'extraction_time': schema_data['extraction_time'],
                'import_time': end_time,
                'statistics': import_stats,
                'database_type': conn_config.database_type,
                'server': conn_config.server,
                'database': conn_config.database
            }

        except Exception as e:
            logger.error(f"Schema import failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'database_type': conn_config.database_type,
                'server': conn_config.server,
                'database': conn_config.database
            }

    def _import_schema_data(
        self,
        rni_version_id: int,
        schema_data: Dict[str, Any],
        conn_config: DatabaseConnection,
        created_by: Optional[str] = None
    ) -> Dict[str, int]:
        """Import extracted schema data into data dictionary tables."""

        conn = self.get_db_connection()
        stats = {
            'database_instances': 0,
            'schemas': 0,
            'tables': 0,
            'columns': 0,
            'constraints': 0,
            'indexes': 0,
            'change_log_entries': 0
        }

        try:
            with conn.cursor() as cursor:
                # Create or get database instance
                database_instance_id = self._create_database_instance(
                    cursor, rni_version_id, conn_config, schema_data
                )
                stats['database_instances'] = 1

                # Process each schema
                for schema_name in schema_data['schemas']:
                    schema_id = self._create_database_schema(
                        cursor, database_instance_id, schema_name
                    )
                    stats['schemas'] += 1

                    # Process tables in this schema
                    schema_tables = {k: v for k, v in schema_data['tables'].items()
                                   if k.startswith(f"{schema_name}.")}

                    for table_key, table_data in schema_tables.items():
                        table_info = table_data['table_info']

                        # Create table record
                        table_id = self._create_database_table(
                            cursor, schema_id, table_info
                        )
                        stats['tables'] += 1

                        # Create columns
                        for column_info in table_data['columns']:
                            self._create_database_column(
                                cursor, table_id, column_info
                            )
                            stats['columns'] += 1

                        # Create constraints
                        for constraint_info in table_data['constraints']:
                            self._create_table_constraint(
                                cursor, table_id, constraint_info
                            )
                            stats['constraints'] += 1

                        # Create indexes
                        for index_info in table_data['indexes']:
                            self._create_table_index(
                                cursor, table_id, index_info
                            )
                            stats['indexes'] += 1

                # Create change log entry
                self._create_change_log_entry(
                    cursor, rni_version_id, database_instance_id,
                    'CREATE', 'SCHEMA_IMPORT', f"Complete schema import for {conn_config.database}",
                    created_by=created_by
                )
                stats['change_log_entries'] = 1

                conn.commit()
                logger.info(f"Schema import completed successfully: {stats}")

        except Exception as e:
            conn.rollback()
            logger.error(f"Schema import transaction failed: {e}")
            raise
        finally:
            conn.close()

        return stats

    def _create_database_instance(
        self, cursor, rni_version_id: int, conn_config: DatabaseConnection, schema_data: Dict[str, Any]
    ) -> int:
        """Create or update database instance record."""
        cursor.execute("""
            INSERT INTO database_instances
            (rni_version_id, database_name, database_type, server_name, port, description, is_active)
            VALUES (%(rni_version_id)s, %(database_name)s, %(database_type)s, %(server_name)s,
                    %(port)s, %(description)s, %(is_active)s)
            ON CONFLICT (rni_version_id, database_name, database_type)
            DO UPDATE SET
                server_name = EXCLUDED.server_name,
                port = EXCLUDED.port,
                description = EXCLUDED.description,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """, {
            'rni_version_id': rni_version_id,
            'database_name': conn_config.database,
            'database_type': conn_config.database_type,
            'server_name': conn_config.server,
            'port': conn_config.port,
            'description': f"Auto-imported {conn_config.database_type} database",
            'is_active': True
        })

        result = cursor.fetchone()
        return result['id']

    def _create_database_schema(self, cursor, database_instance_id: int, schema_name: str) -> int:
        """Create or update database schema record."""
        cursor.execute("""
            INSERT INTO database_schemas (database_instance_id, schema_name, description)
            VALUES (%(database_instance_id)s, %(schema_name)s, %(description)s)
            ON CONFLICT (database_instance_id, schema_name)
            DO UPDATE SET
                description = EXCLUDED.description,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """, {
            'database_instance_id': database_instance_id,
            'schema_name': schema_name,
            'description': f"Auto-imported schema: {schema_name}"
        })

        result = cursor.fetchone()
        return result['id']

    def _create_database_table(self, cursor, schema_id: int, table_info: TableInfo) -> int:
        """Create or update database table record."""
        cursor.execute("""
            INSERT INTO database_tables
            (schema_id, table_name, table_type, description, row_count, size_bytes,
             owner_name, created_date, modified_date, is_active)
            VALUES (%(schema_id)s, %(table_name)s, %(table_type)s, %(description)s,
                    %(row_count)s, %(size_bytes)s, %(owner_name)s, %(created_date)s,
                    %(modified_date)s, %(is_active)s)
            ON CONFLICT (schema_id, table_name)
            DO UPDATE SET
                table_type = EXCLUDED.table_type,
                description = EXCLUDED.description,
                row_count = EXCLUDED.row_count,
                size_bytes = EXCLUDED.size_bytes,
                owner_name = EXCLUDED.owner_name,
                created_date = EXCLUDED.created_date,
                modified_date = EXCLUDED.modified_date,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """, {
            'schema_id': schema_id,
            'table_name': table_info.table_name,
            'table_type': table_info.table_type,
            'description': table_info.description,
            'row_count': table_info.row_count,
            'size_bytes': table_info.size_bytes,
            'owner_name': table_info.owner,
            'created_date': table_info.created_date,
            'modified_date': table_info.modified_date,
            'is_active': True
        })

        result = cursor.fetchone()
        return result['id']

    def _create_database_column(self, cursor, table_id: int, column_info: ColumnInfo) -> int:
        """Create or update database column record."""
        cursor.execute("""
            INSERT INTO database_columns
            (table_id, column_name, ordinal_position, data_type, max_length, precision_value,
             scale_value, is_nullable, is_primary_key, is_foreign_key, is_identity,
             default_value, description)
            VALUES (%(table_id)s, %(column_name)s, %(ordinal_position)s, %(data_type)s,
                    %(max_length)s, %(precision_value)s, %(scale_value)s, %(is_nullable)s,
                    %(is_primary_key)s, %(is_foreign_key)s, %(is_identity)s,
                    %(default_value)s, %(description)s)
            ON CONFLICT (table_id, column_name)
            DO UPDATE SET
                ordinal_position = EXCLUDED.ordinal_position,
                data_type = EXCLUDED.data_type,
                max_length = EXCLUDED.max_length,
                precision_value = EXCLUDED.precision_value,
                scale_value = EXCLUDED.scale_value,
                is_nullable = EXCLUDED.is_nullable,
                is_primary_key = EXCLUDED.is_primary_key,
                is_foreign_key = EXCLUDED.is_foreign_key,
                is_identity = EXCLUDED.is_identity,
                default_value = EXCLUDED.default_value,
                description = EXCLUDED.description,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """, {
            'table_id': table_id,
            'column_name': column_info.column_name,
            'ordinal_position': column_info.ordinal_position,
            'data_type': column_info.data_type,
            'max_length': column_info.max_length,
            'precision_value': column_info.precision,
            'scale_value': column_info.scale,
            'is_nullable': column_info.is_nullable,
            'is_primary_key': column_info.is_primary_key,
            'is_foreign_key': column_info.is_foreign_key,
            'is_identity': column_info.is_identity,
            'default_value': column_info.default_value,
            'description': column_info.description
        })

        result = cursor.fetchone()
        return result['id']

    def _create_table_constraint(self, cursor, table_id: int, constraint_info: ConstraintInfo) -> int:
        """Create or update table constraint record."""
        cursor.execute("""
            INSERT INTO table_constraints
            (table_id, constraint_name, constraint_type, column_names, referenced_table_id,
             referenced_column_names, check_clause, is_active)
            VALUES (%(table_id)s, %(constraint_name)s, %(constraint_type)s, %(column_names)s,
                    %(referenced_table_id)s, %(referenced_column_names)s, %(check_clause)s, %(is_active)s)
            ON CONFLICT (table_id, constraint_name)
            DO UPDATE SET
                constraint_type = EXCLUDED.constraint_type,
                column_names = EXCLUDED.column_names,
                referenced_table_id = EXCLUDED.referenced_table_id,
                referenced_column_names = EXCLUDED.referenced_column_names,
                check_clause = EXCLUDED.check_clause,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """, {
            'table_id': table_id,
            'constraint_name': constraint_info.constraint_name,
            'constraint_type': constraint_info.constraint_type,
            'column_names': constraint_info.column_names,
            'referenced_table_id': None,  # Would need to resolve this
            'referenced_column_names': constraint_info.referenced_columns,
            'check_clause': constraint_info.check_clause,
            'is_active': True
        })

        result = cursor.fetchone()
        return result['id']

    def _create_table_index(self, cursor, table_id: int, index_info: IndexInfo) -> int:
        """Create or update table index record."""
        cursor.execute("""
            INSERT INTO table_indexes
            (table_id, index_name, index_type, column_names, is_unique, is_primary,
             filter_condition, size_bytes)
            VALUES (%(table_id)s, %(index_name)s, %(index_type)s, %(column_names)s,
                    %(is_unique)s, %(is_primary)s, %(filter_condition)s, %(size_bytes)s)
            ON CONFLICT (table_id, index_name)
            DO UPDATE SET
                index_type = EXCLUDED.index_type,
                column_names = EXCLUDED.column_names,
                is_unique = EXCLUDED.is_unique,
                is_primary = EXCLUDED.is_primary,
                filter_condition = EXCLUDED.filter_condition,
                size_bytes = EXCLUDED.size_bytes,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """, {
            'table_id': table_id,
            'index_name': index_info.index_name,
            'index_type': index_info.index_type,
            'column_names': index_info.column_names,
            'is_unique': index_info.is_unique,
            'is_primary': index_info.is_primary,
            'filter_condition': index_info.filter_condition,
            'size_bytes': index_info.size_bytes
        })

        result = cursor.fetchone()
        return result['id']

    def _create_change_log_entry(
        self, cursor, rni_version_id: int, database_instance_id: int,
        change_type: str, object_type: str, change_description: str,
        created_by: Optional[str] = None
    ):
        """Create a change log entry."""
        cursor.execute("""
            INSERT INTO schema_change_log
            (rni_version_id, database_instance_id, change_type, object_type, object_name,
             change_description, impact_level, created_by)
            VALUES (%(rni_version_id)s, %(database_instance_id)s, %(change_type)s,
                    %(object_type)s, %(object_name)s, %(change_description)s,
                    %(impact_level)s, %(created_by)s)
        """, {
            'rni_version_id': rni_version_id,
            'database_instance_id': database_instance_id,
            'change_type': change_type,
            'object_type': object_type,
            'object_name': 'FULL_SCHEMA',
            'change_description': change_description,
            'impact_level': 'MEDIUM',
            'created_by': created_by or 'system'
        })

    async def import_csv_schema(
        self,
        rni_version_id: int,
        database_name: str,
        database_type: str,
        csv_data: List[Dict[str, Any]],
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Import schema information from CSV data into the data dictionary."""

        logger.info(f"Starting CSV schema import for {database_name} (RNI version {rni_version_id})")

        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Find or create database instance
                cursor.execute(
                    """SELECT id FROM database_instances
                       WHERE rni_version_id = %s AND database_name = %s""",
                    (rni_version_id, database_name)
                )
                db_instance = cursor.fetchone()

                if not db_instance:
                    # Create database instance
                    cursor.execute(
                        """INSERT INTO database_instances
                           (rni_version_id, database_name, database_type, description, is_active)
                           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                        (rni_version_id, database_name, database_type,
                         f"Imported from CSV upload", True)
                    )
                    db_instance = cursor.fetchone()

                database_instance_id = db_instance['id']

                # Group data by schema and table
                schemas = {}
                for row in csv_data:
                    schema_name = row.get('schema_name', 'dbo')
                    table_name = row.get('table_name')

                    if schema_name not in schemas:
                        schemas[schema_name] = {}
                    if table_name not in schemas[schema_name]:
                        schemas[schema_name][table_name] = []

                    schemas[schema_name][table_name].append(row)

                # Import schemas, tables, and columns
                total_schemas = 0
                total_tables = 0
                total_columns = 0

                for schema_name, tables in schemas.items():
                    # Create or get schema
                    cursor.execute(
                        """INSERT INTO database_schemas
                           (database_instance_id, schema_name, description)
                           VALUES (%s, %s, %s)
                           ON CONFLICT (database_instance_id, schema_name)
                           DO UPDATE SET schema_name = EXCLUDED.schema_name
                           RETURNING id""",
                        (database_instance_id, schema_name, f"Schema from CSV import")
                    )
                    schema_id = cursor.fetchone()['id']
                    total_schemas += 1

                    for table_name, columns in tables.items():
                        # Create or get table
                        cursor.execute(
                            """INSERT INTO database_tables
                               (schema_id, table_name, table_type, description)
                               VALUES (%s, %s, %s, %s)
                               ON CONFLICT (schema_id, table_name)
                               DO UPDATE SET table_type = EXCLUDED.table_type
                               RETURNING id""",
                            (schema_id, table_name, 'TABLE', f"Table from CSV import")
                        )
                        table_id = cursor.fetchone()['id']
                        total_tables += 1

                        # Import columns
                        for i, column_data in enumerate(columns):
                            cursor.execute(
                                """INSERT INTO database_columns
                                   (table_id, column_name, ordinal_position, data_type,
                                    max_length, precision_value, scale_value, is_nullable,
                                    is_primary_key, is_identity, default_value, description)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                   ON CONFLICT (table_id, column_name)
                                   DO UPDATE SET
                                       data_type = EXCLUDED.data_type,
                                       is_nullable = EXCLUDED.is_nullable,
                                       is_primary_key = EXCLUDED.is_primary_key""",
                                (
                                    table_id,
                                    column_data.get('column_name'),
                                    i + 1,  # ordinal_position
                                    column_data.get('data_type'),
                                    self._safe_int(column_data.get('max_length')),
                                    self._safe_int(column_data.get('precision')),
                                    self._safe_int(column_data.get('scale')),
                                    self._safe_bool(column_data.get('is_nullable')),
                                    self._safe_bool(column_data.get('is_primary_key')),
                                    self._safe_bool(column_data.get('is_identity')),
                                    column_data.get('default_value'),
                                    column_data.get('column_description')
                                )
                            )
                            total_columns += 1

                # Create change log entry
                change_description = f"CSV schema import: {total_schemas} schemas, {total_tables} tables, {total_columns} columns"
                self._create_change_log_entry(
                    cursor, rni_version_id, database_instance_id,
                    'CREATE', 'SCHEMA', change_description, created_by
                )

                conn.commit()

                return {
                    "schemas_imported": total_schemas,
                    "tables_imported": total_tables,
                    "columns_imported": total_columns,
                    "database_instance_id": database_instance_id
                }

        except Exception as e:
            conn.rollback()
            logger.error(f"CSV schema import failed: {e}")
            raise
        finally:
            conn.close()

    def _safe_int(self, value) -> Optional[int]:
        """Safely convert value to int."""
        if value is None or value == '':
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _safe_bool(self, value) -> bool:
        """Safely convert value to bool."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 't')
        if isinstance(value, int):
            return bool(value)
        return False

# API endpoint for schema extraction
def extract_and_import_schema(
    rni_version_id: int,
    database_type: str,
    server: str,
    port: int,
    database: str,
    username: str,
    password: str,
    schema_name: Optional[str] = None,
    created_by: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract schema from a database and import into data dictionary.

    This function can be called from the API or used as a utility function.
    """
    conn_config = DatabaseConnection(
        database_type=database_type,
        server=server,
        port=port,
        database=database,
        username=username,
        password=password,
        schema=schema_name
    )

    importer = SchemaImporter()
    return importer.import_database_schema(
        rni_version_id=rni_version_id,
        conn_config=conn_config,
        schema_name=schema_name,
        created_by=created_by
    )

# Global schema importer instance
schema_importer = SchemaImporter()