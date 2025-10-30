"""
Database Connection Service for Schema Extraction
Connects to MSSQL and PostgreSQL databases to extract schema information
"""

import logging
import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

try:
    import pyodbc
    MSSQL_AVAILABLE = True
except ImportError:
    MSSQL_AVAILABLE = False
    logging.warning("pyodbc not available - MSSQL connections disabled")

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

@dataclass
class DatabaseConnection:
    """Database connection configuration."""
    database_type: str  # 'MSSQL' or 'PostgreSQL'
    server: str
    port: int
    database: str
    username: str
    password: str
    schema: Optional[str] = None
    connection_timeout: int = 30

@dataclass
class TableInfo:
    """Table information structure."""
    schema_name: str
    table_name: str
    table_type: str  # 'TABLE', 'VIEW', 'MATERIALIZED_VIEW'
    description: Optional[str] = None
    row_count: Optional[int] = None
    size_bytes: Optional[int] = None
    owner: Optional[str] = None
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None

@dataclass
class ColumnInfo:
    """Column information structure."""
    column_name: str
    ordinal_position: int
    data_type: str
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_identity: bool = False
    default_value: Optional[str] = None
    description: Optional[str] = None

@dataclass
class ConstraintInfo:
    """Constraint information structure."""
    constraint_name: str
    constraint_type: str  # 'PRIMARY_KEY', 'FOREIGN_KEY', 'UNIQUE', 'CHECK', 'DEFAULT'
    column_names: List[str]
    referenced_table: Optional[str] = None
    referenced_schema: Optional[str] = None
    referenced_columns: Optional[List[str]] = None
    check_clause: Optional[str] = None

@dataclass
class IndexInfo:
    """Index information structure."""
    index_name: str
    index_type: str  # 'BTREE', 'HASH', 'CLUSTERED', 'NONCLUSTERED', etc.
    column_names: List[str]
    is_unique: bool = False
    is_primary: bool = False
    filter_condition: Optional[str] = None
    size_bytes: Optional[int] = None

class DatabaseSchemaExtractor:
    """Extracts schema information from databases."""

    def __init__(self):
        """Initialize the schema extractor."""
        pass

    def connect_postgresql(self, conn_config: DatabaseConnection) -> psycopg2.extensions.connection:
        """Create PostgreSQL connection."""
        try:
            connection_string = (
                f"host={conn_config.server} "
                f"port={conn_config.port} "
                f"database={conn_config.database} "
                f"user={conn_config.username} "
                f"password={conn_config.password} "
                f"connect_timeout={conn_config.connection_timeout}"
            )

            conn = psycopg2.connect(connection_string, cursor_factory=RealDictCursor)
            logger.info(f"Connected to PostgreSQL: {conn_config.server}:{conn_config.port}/{conn_config.database}")
            return conn

        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            raise

    def connect_mssql(self, conn_config: DatabaseConnection) -> Any:
        """Create MSSQL connection."""
        if not MSSQL_AVAILABLE:
            raise RuntimeError("pyodbc not available - cannot connect to MSSQL")

        try:
            # Build connection string for SQL Server
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={conn_config.server},{conn_config.port};"
                f"DATABASE={conn_config.database};"
                f"UID={conn_config.username};"
                f"PWD={conn_config.password};"
                f"Connection Timeout={conn_config.connection_timeout};"
            )

            conn = pyodbc.connect(conn_str)
            logger.info(f"Connected to MSSQL: {conn_config.server}:{conn_config.port}/{conn_config.database}")
            return conn

        except Exception as e:
            logger.error(f"MSSQL connection failed: {e}")
            raise

    def extract_postgresql_schema(self, conn_config: DatabaseConnection, schema_name: Optional[str] = None) -> Dict[str, Any]:
        """Extract complete schema information from PostgreSQL database."""
        conn = self.connect_postgresql(conn_config)

        try:
            with conn.cursor() as cursor:
                schema_filter = schema_name or conn_config.schema or 'public'

                # Get schemas
                schemas = self._get_postgresql_schemas(cursor, schema_filter)

                # Get tables for each schema
                tables = {}
                for schema in schemas:
                    schema_tables = self._get_postgresql_tables(cursor, schema)

                    # Get columns, constraints, and indexes for each table
                    for table in schema_tables:
                        table_name = f"{schema}.{table.table_name}"

                        # Get columns
                        columns = self._get_postgresql_columns(cursor, schema, table.table_name)

                        # Get constraints
                        constraints = self._get_postgresql_constraints(cursor, schema, table.table_name)

                        # Get indexes
                        indexes = self._get_postgresql_indexes(cursor, schema, table.table_name)

                        tables[table_name] = {
                            'table_info': table,
                            'columns': columns,
                            'constraints': constraints,
                            'indexes': indexes
                        }

                return {
                    'database_type': 'PostgreSQL',
                    'server': conn_config.server,
                    'database': conn_config.database,
                    'schemas': schemas,
                    'tables': tables,
                    'extraction_time': datetime.now()
                }

        finally:
            conn.close()

    def extract_mssql_schema(self, conn_config: DatabaseConnection, schema_name: Optional[str] = None) -> Dict[str, Any]:
        """Extract complete schema information from MSSQL database."""
        if not MSSQL_AVAILABLE:
            raise RuntimeError("pyodbc not available - cannot extract MSSQL schema")

        conn = self.connect_mssql(conn_config)

        try:
            cursor = conn.cursor()
            schema_filter = schema_name or conn_config.schema or 'dbo'

            # Get schemas
            schemas = self._get_mssql_schemas(cursor, schema_filter)

            # Get tables for each schema
            tables = {}
            for schema in schemas:
                schema_tables = self._get_mssql_tables(cursor, schema)

                # Get columns, constraints, and indexes for each table
                for table in schema_tables:
                    table_name = f"{schema}.{table.table_name}"

                    # Get columns
                    columns = self._get_mssql_columns(cursor, schema, table.table_name)

                    # Get constraints
                    constraints = self._get_mssql_constraints(cursor, schema, table.table_name)

                    # Get indexes
                    indexes = self._get_mssql_indexes(cursor, schema, table.table_name)

                    tables[table_name] = {
                        'table_info': table,
                        'columns': columns,
                        'constraints': constraints,
                        'indexes': indexes
                    }

            return {
                'database_type': 'MSSQL',
                'server': conn_config.server,
                'database': conn_config.database,
                'schemas': schemas,
                'tables': tables,
                'extraction_time': datetime.now()
            }

        finally:
            conn.close()

    # PostgreSQL-specific methods
    def _get_postgresql_schemas(self, cursor, schema_filter: str) -> List[str]:
        """Get PostgreSQL schemas."""
        if schema_filter == '*':
            cursor.execute("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                ORDER BY schema_name
            """)
        else:
            cursor.execute("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name = %s
            """, (schema_filter,))

        return [row['schema_name'] for row in cursor.fetchall()]

    def _get_postgresql_tables(self, cursor, schema_name: str) -> List[TableInfo]:
        """Get PostgreSQL tables and views."""
        cursor.execute("""
            SELECT
                t.table_name,
                t.table_type,
                pg_size_pretty(pg_total_relation_size(c.oid)) as size_pretty,
                pg_total_relation_size(c.oid) as size_bytes,
                n.nspowner::regrole as owner,
                obj_description(c.oid) as description
            FROM information_schema.tables t
            LEFT JOIN pg_class c ON c.relname = t.table_name
            LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE t.table_schema = %s
            AND t.table_type IN ('BASE TABLE', 'VIEW', 'MATERIALIZED VIEW')
            ORDER BY t.table_name
        """, (schema_name,))

        tables = []
        for row in cursor.fetchall():
            # Get row count for tables (not views)
            row_count = None
            if row['table_type'] == 'BASE TABLE':
                try:
                    cursor.execute(f"SELECT COUNT(*) as count FROM {schema_name}.{row['table_name']}")
                    row_count = cursor.fetchone()['count']
                except Exception as e:
                    # Skip if we can't count rows due to permissions or other issues
                    pass

            tables.append(TableInfo(
                schema_name=schema_name,
                table_name=row['table_name'],
                table_type=row['table_type'],
                description=row['description'],
                row_count=row_count,
                size_bytes=row['size_bytes'],
                owner=str(row['owner']) if row['owner'] else None
            ))

        return tables

    def _get_postgresql_columns(self, cursor, schema_name: str, table_name: str) -> List[ColumnInfo]:
        """Get PostgreSQL column information."""
        cursor.execute("""
            SELECT
                c.column_name,
                c.ordinal_position,
                c.data_type,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                c.is_nullable::boolean,
                c.column_default,
                col_description(pgc.oid, c.ordinal_position) as description,
                CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key,
                CASE WHEN fk.column_name IS NOT NULL THEN true ELSE false END as is_foreign_key,
                CASE WHEN c.column_default LIKE 'nextval%' THEN true ELSE false END as is_identity
            FROM information_schema.columns c
            LEFT JOIN pg_class pgc ON pgc.relname = c.table_name
            LEFT JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace AND pgn.nspname = c.table_schema
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku ON tc.constraint_name = ku.constraint_name
                WHERE tc.table_schema = %s AND tc.table_name = %s AND tc.constraint_type = 'PRIMARY KEY'
            ) pk ON pk.column_name = c.column_name
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku ON tc.constraint_name = ku.constraint_name
                WHERE tc.table_schema = %s AND tc.table_name = %s AND tc.constraint_type = 'FOREIGN KEY'
            ) fk ON fk.column_name = c.column_name
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position
        """, (schema_name, table_name, schema_name, table_name, schema_name, table_name))

        columns = []
        for row in cursor.fetchall():
            columns.append(ColumnInfo(
                column_name=row['column_name'],
                ordinal_position=row['ordinal_position'],
                data_type=row['data_type'],
                max_length=row['character_maximum_length'],
                precision=row['numeric_precision'],
                scale=row['numeric_scale'],
                is_nullable=row['is_nullable'],
                is_primary_key=row['is_primary_key'],
                is_foreign_key=row['is_foreign_key'],
                is_identity=row['is_identity'],
                default_value=row['column_default'],
                description=row['description']
            ))

        return columns

    def _get_postgresql_constraints(self, cursor, schema_name: str, table_name: str) -> List[ConstraintInfo]:
        """Get PostgreSQL constraint information."""
        cursor.execute("""
            SELECT
                tc.constraint_name,
                tc.constraint_type,
                STRING_AGG(kcu.column_name, ',' ORDER BY kcu.ordinal_position) as column_names,
                ccu.table_schema as referenced_schema,
                ccu.table_name as referenced_table,
                STRING_AGG(ccu.column_name, ',' ORDER BY kcu.ordinal_position) as referenced_columns,
                cc.check_clause
            FROM information_schema.table_constraints tc
            LEFT JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            LEFT JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
            LEFT JOIN information_schema.check_constraints cc
                ON tc.constraint_name = cc.constraint_name
            WHERE tc.table_schema = %s AND tc.table_name = %s
            GROUP BY tc.constraint_name, tc.constraint_type, ccu.table_schema, ccu.table_name, cc.check_clause
        """, (schema_name, table_name))

        constraints = []
        for row in cursor.fetchall():
            constraints.append(ConstraintInfo(
                constraint_name=row['constraint_name'],
                constraint_type=row['constraint_type'].upper(),
                column_names=row['column_names'].split(',') if row['column_names'] else [],
                referenced_schema=row['referenced_schema'],
                referenced_table=row['referenced_table'],
                referenced_columns=row['referenced_columns'].split(',') if row['referenced_columns'] else None,
                check_clause=row['check_clause']
            ))

        return constraints

    def _get_postgresql_indexes(self, cursor, schema_name: str, table_name: str) -> List[IndexInfo]:
        """Get PostgreSQL index information."""
        cursor.execute("""
            SELECT
                i.indexname as index_name,
                CASE
                    WHEN i.indexdef LIKE '%UNIQUE%' THEN true
                    ELSE false
                END as is_unique,
                CASE
                    WHEN c.contype = 'p' THEN true
                    ELSE false
                END as is_primary,
                pg_size_pretty(pg_relation_size(quote_ident(i.schemaname)||'.'||quote_ident(i.indexname))) as size_pretty,
                pg_relation_size(quote_ident(i.schemaname)||'.'||quote_ident(i.indexname)) as size_bytes,
                i.indexdef
            FROM pg_indexes i
            LEFT JOIN pg_constraint c ON c.conname = i.indexname
            WHERE i.schemaname = %s AND i.tablename = %s
        """, (schema_name, table_name))

        indexes = []
        for row in cursor.fetchall():
            # Extract column names from index definition (simplified)
            index_def = row['indexdef']
            # This is a simplified extraction - in practice, you might need more sophisticated parsing
            column_start = index_def.find('(')
            column_end = index_def.find(')')
            column_names = []
            if column_start > 0 and column_end > column_start:
                columns_str = index_def[column_start+1:column_end]
                column_names = [col.strip() for col in columns_str.split(',')]

            indexes.append(IndexInfo(
                index_name=row['index_name'],
                index_type='BTREE',  # Default for PostgreSQL
                column_names=column_names,
                is_unique=row['is_unique'],
                is_primary=row['is_primary'],
                size_bytes=row['size_bytes']
            ))

        return indexes

    # MSSQL-specific methods (simplified implementations)
    def _get_mssql_schemas(self, cursor, schema_filter: str) -> List[str]:
        """Get MSSQL schemas."""
        if schema_filter == '*':
            cursor.execute("""
                SELECT name
                FROM sys.schemas
                WHERE name NOT IN ('sys', 'INFORMATION_SCHEMA', 'guest', 'db_owner', 'db_accessadmin',
                                  'db_securityadmin', 'db_ddladmin', 'db_backupoperator', 'db_datareader',
                                  'db_datawriter', 'db_denydatareader', 'db_denydatawriter')
                ORDER BY name
            """)
        else:
            cursor.execute("SELECT name FROM sys.schemas WHERE name = ?", (schema_filter,))

        return [row[0] for row in cursor.fetchall()]

    def _get_mssql_tables(self, cursor, schema_name: str) -> List[TableInfo]:
        """Get MSSQL tables and views."""
        cursor.execute("""
            SELECT
                t.name as table_name,
                CASE t.type
                    WHEN 'U' THEN 'BASE TABLE'
                    WHEN 'V' THEN 'VIEW'
                    ELSE 'OTHER'
                END as table_type,
                ep.value as description,
                p.rows as row_count,
                s.name as schema_name
            FROM sys.tables t
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            LEFT JOIN sys.extended_properties ep ON ep.major_id = t.object_id AND ep.minor_id = 0 AND ep.name = 'MS_Description'
            LEFT JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
            WHERE s.name = ?
            ORDER BY t.name
        """, (schema_name,))

        tables = []
        for row in cursor.fetchall():
            tables.append(TableInfo(
                schema_name=schema_name,
                table_name=row[0],
                table_type=row[1],
                description=row[2] if len(row) > 2 else None,
                row_count=row[3] if len(row) > 3 else None
            ))

        return tables

    def _get_mssql_columns(self, cursor, schema_name: str, table_name: str) -> List[ColumnInfo]:
        """Get MSSQL column information (simplified)."""
        cursor.execute("""
            SELECT
                c.name as column_name,
                c.column_id as ordinal_position,
                t.name as data_type,
                c.max_length,
                c.precision,
                c.scale,
                c.is_nullable,
                c.is_identity,
                dc.definition as default_value,
                ep.value as description
            FROM sys.columns c
            INNER JOIN sys.types t ON c.user_type_id = t.user_type_id
            INNER JOIN sys.tables tb ON c.object_id = tb.object_id
            INNER JOIN sys.schemas s ON tb.schema_id = s.schema_id
            LEFT JOIN sys.default_constraints dc ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
            LEFT JOIN sys.extended_properties ep ON ep.major_id = c.object_id AND ep.minor_id = c.column_id AND ep.name = 'MS_Description'
            WHERE s.name = ? AND tb.name = ?
            ORDER BY c.column_id
        """, (schema_name, table_name))

        columns = []
        for row in cursor.fetchall():
            columns.append(ColumnInfo(
                column_name=row[0],
                ordinal_position=row[1],
                data_type=row[2],
                max_length=row[3] if row[3] != -1 else None,
                precision=row[4] if row[4] > 0 else None,
                scale=row[5] if row[5] > 0 else None,
                is_nullable=bool(row[6]),
                is_identity=bool(row[7]),
                default_value=row[8],
                description=row[9]
            ))

        return columns

    def _get_mssql_constraints(self, cursor, schema_name: str, table_name: str) -> List[ConstraintInfo]:
        """Get MSSQL constraint information (simplified)."""
        # This would need more complex queries for full constraint information
        return []

    def _get_mssql_indexes(self, cursor, schema_name: str, table_name: str) -> List[IndexInfo]:
        """Get MSSQL index information (simplified)."""
        # This would need more complex queries for full index information
        return []

# Global extractor instance
schema_extractor = DatabaseSchemaExtractor()