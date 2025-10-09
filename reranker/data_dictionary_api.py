"""
Data Dictionary API Endpoints
Manages database schema information for MSSQL and PostgreSQL databases by RNI version
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from fastapi import APIRouter, HTTPException, Depends, Query, Form, File, UploadFile
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import csv
from io import StringIO

from config import get_settings
from schema_extraction_utils import extract_and_import_schema

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/data-dictionary", tags=["data-dictionary"])

# Pydantic models for API requests/responses
class RNIVersion(BaseModel):
    id: Optional[int] = None
    version_number: str
    version_name: Optional[str] = None
    description: Optional[str] = None
    release_date: Optional[date] = None
    is_active: bool = True

class DatabaseInstance(BaseModel):
    id: Optional[int] = None
    rni_version_id: int
    database_name: str
    database_type: str = Field(..., pattern="^(MSSQL|PostgreSQL)$")
    server_name: Optional[str] = None
    port: Optional[int] = None
    description: Optional[str] = None
    connection_string_template: Optional[str] = None
    is_active: bool = True

class DatabaseSchema(BaseModel):
    id: Optional[int] = None
    database_instance_id: int
    schema_name: str
    description: Optional[str] = None
    owner_name: Optional[str] = None

class DatabaseTable(BaseModel):
    id: Optional[int] = None
    schema_id: int
    table_name: str
    table_type: str = Field(default="TABLE", pattern="^(TABLE|VIEW|MATERIALIZED_VIEW)$")
    description: Optional[str] = None
    row_count: Optional[int] = None
    size_bytes: Optional[int] = None
    owner_name: Optional[str] = None
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    is_active: bool = True

class DatabaseColumn(BaseModel):
    id: Optional[int] = None
    table_id: int
    column_name: str
    ordinal_position: int
    data_type: str
    max_length: Optional[int] = None
    precision_value: Optional[int] = None
    scale_value: Optional[int] = None
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_identity: bool = False
    default_value: Optional[str] = None
    description: Optional[str] = None

class TableConstraint(BaseModel):
    id: Optional[int] = None
    table_id: int
    constraint_name: str
    constraint_type: str = Field(..., pattern="^(PRIMARY_KEY|FOREIGN_KEY|UNIQUE|CHECK|DEFAULT)$")
    column_names: List[str]
    referenced_table_id: Optional[int] = None
    referenced_column_names: Optional[List[str]] = None
    check_clause: Optional[str] = None
    is_active: bool = True

class TableIndex(BaseModel):
    id: Optional[int] = None
    table_id: int
    index_name: str
    index_type: str = Field(default="BTREE", pattern="^(BTREE|HASH|GIST|GIN|CLUSTERED|NONCLUSTERED)$")
    column_names: List[str]
    is_unique: bool = False
    is_primary: bool = False
    filter_condition: Optional[str] = None
    size_bytes: Optional[int] = None

class DatabaseObject(BaseModel):
    id: Optional[int] = None
    schema_id: int
    object_name: str
    object_type: str = Field(..., pattern="^(STORED_PROCEDURE|FUNCTION|TRIGGER|VIEW|SEQUENCE|TYPE)$")
    definition: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    return_type: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True

class SchemaChangeLog(BaseModel):
    id: Optional[int] = None
    rni_version_id: int
    database_instance_id: Optional[int] = None
    change_type: str = Field(..., pattern="^(CREATE|ALTER|DROP|RENAME)$")
    object_type: str
    object_name: str
    schema_name: Optional[str] = None
    change_description: Optional[str] = None
    sql_statement: Optional[str] = None
    impact_level: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    created_by: Optional[str] = None

class SchemaOverview(BaseModel):
    version_number: str
    version_name: Optional[str]
    database_name: str
    database_type: str
    schema_name: str
    table_name: str
    table_type: str
    table_description: Optional[str]
    row_count: Optional[int]
    column_count: int
    table_created_at: Optional[datetime]

class ColumnDetails(BaseModel):
    version_number: str
    database_name: str
    database_type: str
    schema_name: str
    table_name: str
    column_name: str
    ordinal_position: int
    data_type: str
    max_length: Optional[int]
    precision_value: Optional[int]
    scale_value: Optional[int]
    is_nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    is_identity: bool
    default_value: Optional[str]
    description: Optional[str]

def get_db_connection():
    """Get database connection with proper error handling."""
    try:
        return psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            cursor_factory=RealDictCursor
        )
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

# RNI Version Management
@router.get("/rni-versions", response_model=List[RNIVersion])
async def get_rni_versions(active_only: bool = Query(False, description="Filter to active versions only")):
    """Get all RNI versions."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = "SELECT * FROM rni_versions"
            if active_only:
                query += " WHERE is_active = true"
            query += " ORDER BY version_number DESC"
            
            cursor.execute(query)
            results = cursor.fetchall()
            return [RNIVersion(**row) for row in results]
    finally:
        conn.close()

@router.post("/rni-versions", response_model=RNIVersion)
async def create_rni_version(version: RNIVersion):
    """Create a new RNI version."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO rni_versions (version_number, version_name, description, release_date, is_active)
                VALUES (%(version_number)s, %(version_name)s, %(description)s, %(release_date)s, %(is_active)s)
                RETURNING *
            """, version.dict(exclude={'id'}))
            result = cursor.fetchone()
            conn.commit()
            return RNIVersion(**result)
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Version number already exists")
    finally:
        conn.close()

@router.put("/rni-versions/{version_id}", response_model=RNIVersion)
async def update_rni_version(version_id: int, version: RNIVersion):
    """Update an existing RNI version."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE rni_versions 
                SET version_number = %(version_number)s, version_name = %(version_name)s, 
                    description = %(description)s, release_date = %(release_date)s, 
                    is_active = %(is_active)s
                WHERE id = %(id)s
                RETURNING *
            """, {**version.dict(exclude={'id'}), 'id': version_id})
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="RNI version not found")
            conn.commit()
            return RNIVersion(**result)
    finally:
        conn.close()

# Database Instance Management
@router.get("/database-instances", response_model=List[DatabaseInstance])
async def get_database_instances(rni_version_id: Optional[int] = Query(None, description="Filter by RNI version")):
    """Get database instances, optionally filtered by RNI version."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = "SELECT * FROM database_instances"
            params = {}
            
            if rni_version_id:
                query += " WHERE rni_version_id = %(rni_version_id)s"
                params['rni_version_id'] = rni_version_id
                
            query += " ORDER BY database_name"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [DatabaseInstance(**row) for row in results]
    finally:
        conn.close()

@router.post("/database-instances", response_model=DatabaseInstance)
async def create_database_instance(instance: DatabaseInstance):
    """Create a new database instance."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO database_instances 
                (rni_version_id, database_name, database_type, server_name, port, description, connection_string_template, is_active)
                VALUES (%(rni_version_id)s, %(database_name)s, %(database_type)s, %(server_name)s, 
                        %(port)s, %(description)s, %(connection_string_template)s, %(is_active)s)
                RETURNING *
            """, instance.dict(exclude={'id'}))
            result = cursor.fetchone()
            conn.commit()
            return DatabaseInstance(**result)
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Database instance already exists for this RNI version")
    finally:
        conn.close()

# Schema Overview Endpoints
@router.get("/schema-overview", response_model=List[SchemaOverview])
async def get_schema_overview(
    version_number: Optional[str] = Query(None, description="Filter by version number"),
    database_name: Optional[str] = Query(None, description="Filter by database name"),
    schema_name: Optional[str] = Query(None, description="Filter by schema name")
):
    """Get comprehensive schema overview with filtering options."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = "SELECT * FROM v_schema_overview WHERE 1=1"
            params = {}
            
            if version_number:
                query += " AND version_number = %(version_number)s"
                params['version_number'] = version_number
            if database_name:
                query += " AND database_name = %(database_name)s"
                params['database_name'] = database_name
            if schema_name:
                query += " AND schema_name = %(schema_name)s"
                params['schema_name'] = schema_name
                
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [SchemaOverview(**row) for row in results]
    finally:
        conn.close()

@router.get("/column-details", response_model=List[ColumnDetails])
async def get_column_details(
    version_number: Optional[str] = Query(None, description="Filter by version number"),
    database_name: Optional[str] = Query(None, description="Filter by database name"),
    schema_name: Optional[str] = Query(None, description="Filter by schema name"),
    table_name: Optional[str] = Query(None, description="Filter by table name")
):
    """Get detailed column information with filtering options."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = "SELECT * FROM v_column_details WHERE 1=1"
            params = {}
            
            if version_number:
                query += " AND version_number = %(version_number)s"
                params['version_number'] = version_number
            if database_name:
                query += " AND database_name = %(database_name)s"
                params['database_name'] = database_name
            if schema_name:
                query += " AND schema_name = %(schema_name)s"
                params['schema_name'] = schema_name
            if table_name:
                query += " AND table_name = %(table_name)s"
                params['table_name'] = table_name
                
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [ColumnDetails(**row) for row in results]
    finally:
        conn.close()

# Database Tables Management
@router.get("/tables", response_model=List[DatabaseTable])
async def get_tables(schema_id: Optional[int] = Query(None, description="Filter by schema ID")):
    """Get database tables, optionally filtered by schema."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = "SELECT * FROM database_tables"
            params = {}
            
            if schema_id:
                query += " WHERE schema_id = %(schema_id)s"
                params['schema_id'] = schema_id
                
            query += " ORDER BY table_name"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [DatabaseTable(**row) for row in results]
    finally:
        conn.close()

@router.post("/tables", response_model=DatabaseTable)
async def create_table(table: DatabaseTable):
    """Create a new database table record."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO database_tables 
                (schema_id, table_name, table_type, description, row_count, size_bytes, 
                 owner_name, created_date, modified_date, is_active)
                VALUES (%(schema_id)s, %(table_name)s, %(table_type)s, %(description)s, 
                        %(row_count)s, %(size_bytes)s, %(owner_name)s, %(created_date)s, 
                        %(modified_date)s, %(is_active)s)
                RETURNING *
            """, table.dict(exclude={'id'}))
            result = cursor.fetchone()
            conn.commit()
            return DatabaseTable(**result)
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Table already exists in this schema")
    finally:
        conn.close()

# Columns Management
@router.get("/columns", response_model=List[DatabaseColumn])
async def get_columns(table_id: int = Query(..., description="Table ID to get columns for")):
    """Get columns for a specific table."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM database_columns WHERE table_id = %s ORDER BY ordinal_position",
                (table_id,)
            )
            results = cursor.fetchall()
            return [DatabaseColumn(**row) for row in results]
    finally:
        conn.close()

@router.post("/columns", response_model=DatabaseColumn)
async def create_column(column: DatabaseColumn):
    """Create a new database column record."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO database_columns 
                (table_id, column_name, ordinal_position, data_type, max_length, precision_value, 
                 scale_value, is_nullable, is_primary_key, is_foreign_key, is_identity, 
                 default_value, description)
                VALUES (%(table_id)s, %(column_name)s, %(ordinal_position)s, %(data_type)s, 
                        %(max_length)s, %(precision_value)s, %(scale_value)s, %(is_nullable)s, 
                        %(is_primary_key)s, %(is_foreign_key)s, %(is_identity)s, 
                        %(default_value)s, %(description)s)
                RETURNING *
            """, column.dict(exclude={'id'}))
            result = cursor.fetchone()
            conn.commit()
            return DatabaseColumn(**result)
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Column already exists in this table")
    finally:
        conn.close()

# Schema Change Log
@router.get("/change-log", response_model=List[SchemaChangeLog])
async def get_change_log(
    rni_version_id: Optional[int] = Query(None, description="Filter by RNI version"),
    limit: int = Query(100, ge=1, le=1000, description="Limit number of results")
):
    """Get schema change log entries."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = "SELECT * FROM schema_change_log"
            params = {}
            
            if rni_version_id:
                query += " WHERE rni_version_id = %(rni_version_id)s"
                params['rni_version_id'] = rni_version_id
                
            query += " ORDER BY created_at DESC LIMIT %(limit)s"
            params['limit'] = limit
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [SchemaChangeLog(**row) for row in results]
    finally:
        conn.close()

@router.post("/change-log", response_model=SchemaChangeLog)
async def create_change_log_entry(log_entry: SchemaChangeLog):
    """Create a new schema change log entry."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO schema_change_log 
                (rni_version_id, database_instance_id, change_type, object_type, object_name, 
                 schema_name, change_description, sql_statement, impact_level, created_by)
                VALUES (%(rni_version_id)s, %(database_instance_id)s, %(change_type)s, 
                        %(object_type)s, %(object_name)s, %(schema_name)s, %(change_description)s, 
                        %(sql_statement)s, %(impact_level)s, %(created_by)s)
                RETURNING *
            """, log_entry.dict(exclude={'id'}))
            result = cursor.fetchone()
            conn.commit()
            return SchemaChangeLog(**result)
    finally:
        conn.close()

# Schema Comparison
@router.get("/compare-schemas")
async def compare_schemas(
    version1: str = Query(..., description="First version number to compare"),
    version2: str = Query(..., description="Second version number to compare"),
    database_name: Optional[str] = Query(None, description="Filter by database name")
):
    """Compare database schemas between two RNI versions."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Get schema comparison data
            query = """
                WITH version1_data AS (
                    SELECT schema_name, table_name, column_name, data_type, is_nullable
                    FROM v_column_details 
                    WHERE version_number = %(version1)s
                    AND (%(database_name)s IS NULL OR database_name = %(database_name)s)
                ),
                version2_data AS (
                    SELECT schema_name, table_name, column_name, data_type, is_nullable
                    FROM v_column_details 
                    WHERE version_number = %(version2)s
                    AND (%(database_name)s IS NULL OR database_name = %(database_name)s)
                )
                SELECT 
                    'ADDED' as change_type,
                    v2.schema_name, v2.table_name, v2.column_name, v2.data_type, v2.is_nullable
                FROM version2_data v2
                LEFT JOIN version1_data v1 ON v2.schema_name = v1.schema_name 
                    AND v2.table_name = v1.table_name AND v2.column_name = v1.column_name
                WHERE v1.column_name IS NULL
                
                UNION ALL
                
                SELECT 
                    'REMOVED' as change_type,
                    v1.schema_name, v1.table_name, v1.column_name, v1.data_type, v1.is_nullable
                FROM version1_data v1
                LEFT JOIN version2_data v2 ON v1.schema_name = v2.schema_name 
                    AND v1.table_name = v2.table_name AND v1.column_name = v2.column_name
                WHERE v2.column_name IS NULL
                
                UNION ALL
                
                SELECT 
                    'MODIFIED' as change_type,
                    v2.schema_name, v2.table_name, v2.column_name, v2.data_type, v2.is_nullable
                FROM version1_data v1
                JOIN version2_data v2 ON v1.schema_name = v2.schema_name 
                    AND v1.table_name = v2.table_name AND v1.column_name = v2.column_name
                WHERE v1.data_type != v2.data_type OR v1.is_nullable != v2.is_nullable
                
                ORDER BY schema_name, table_name, column_name
            """
            
            cursor.execute(query, {
                'version1': version1,
                'version2': version2,
                'database_name': database_name
            })
            results = cursor.fetchall()
            
            return {
                'version1': version1,
                'version2': version2,
                'database_name': database_name,
                'changes': results
            }
    finally:
        conn.close()

# Schema Extraction Endpoints
class SchemaExtractionRequest(BaseModel):
    rni_version_id: int
    database_type: str = Field(..., pattern="^(MSSQL|PostgreSQL)$")
    server: str
    port: int
    database: str
    username: str
    password: str
    schema_name: Optional[str] = None
    created_by: Optional[str] = None

@router.post("/extract-schema")
async def extract_schema(extraction_request: SchemaExtractionRequest):
    """Extract schema from a live database and import into data dictionary."""
    try:
        result = extract_and_import_schema(
            rni_version_id=extraction_request.rni_version_id,
            database_type=extraction_request.database_type,
            server=extraction_request.server,
            port=extraction_request.port,
            database=extraction_request.database,
            username=extraction_request.username,
            password=extraction_request.password,
            schema_name=extraction_request.schema_name,
            created_by=extraction_request.created_by
        )
        
        if result['status'] == 'success':
            return {
                "status": "success",
                "message": f"Schema extracted and imported successfully from {extraction_request.server}/{extraction_request.database}",
                "extraction_time": result['extraction_time'],
                "import_time": result['import_time'],
                "duration_seconds": result['duration_seconds'],
                "statistics": result['statistics']
            }
        else:
            raise HTTPException(status_code=500, detail=result['error'])
            
    except Exception as e:
        logger.error(f"Schema extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Schema extraction failed: {str(e)}")

@router.get("/extraction-status/{rni_version_id}")
async def get_extraction_status(rni_version_id: int):
    """Get status of schema extractions for an RNI version."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Get database instances for this RNI version
            cursor.execute("""
                SELECT 
                    di.*,
                    COUNT(DISTINCT ds.id) as schema_count,
                    COUNT(DISTINCT dt.id) as table_count,
                    COUNT(DISTINCT dc.id) as column_count,
                    MAX(di.updated_at) as last_updated
                FROM database_instances di
                LEFT JOIN database_schemas ds ON di.id = ds.database_instance_id
                LEFT JOIN database_tables dt ON ds.id = dt.schema_id
                LEFT JOIN database_columns dc ON dt.id = dc.table_id
                WHERE di.rni_version_id = %s
                GROUP BY di.id
                ORDER BY di.database_name
            """, (rni_version_id,))
            
            instances = cursor.fetchall()
            
            # Get recent change log entries
            cursor.execute("""
                SELECT * FROM schema_change_log 
                WHERE rni_version_id = %s 
                ORDER BY created_at DESC 
                LIMIT 10
            """, (rni_version_id,))
            
            recent_changes = cursor.fetchall()
            
            return {
                "rni_version_id": rni_version_id,
                "database_instances": instances,
                "recent_changes": recent_changes,
                "total_instances": len(instances),
                "timestamp": datetime.now()
            }
    finally:
        conn.close()

# Bulk Operations
@router.post("/bulk-extract")
async def bulk_extract_schemas(extraction_requests: List[SchemaExtractionRequest]):
    """Extract schemas from multiple databases in bulk."""
    results = []
    
    for request in extraction_requests:
        try:
            result = extract_and_import_schema(
                rni_version_id=request.rni_version_id,
                database_type=request.database_type,
                server=request.server,
                port=request.port,
                database=request.database,
                username=request.username,
                password=request.password,
                schema_name=request.schema_name,
                created_by=request.created_by
            )
            
            results.append({
                "database": f"{request.server}/{request.database}",
                "status": result['status'],
                "statistics": result.get('statistics', {}),
                "error": result.get('error', None)
            })
            
        except Exception as e:
            results.append({
                "database": f"{request.server}/{request.database}",
                "status": "error",
                "error": str(e)
            })
    
    return {
        "total_requests": len(extraction_requests),
        "successful": len([r for r in results if r['status'] == 'success']),
        "failed": len([r for r in results if r['status'] == 'error']),
        "results": results
    }

# Health check for data dictionary
@router.get("/health")
async def health_check():
    """Health check for data dictionary API."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as version_count FROM rni_versions")
            result = cursor.fetchone()
            return {
                "status": "healthy",
                "rni_versions_count": result['version_count'],
                "timestamp": datetime.now()
            }
    finally:
        conn.close()


# Query assistance endpoints for Sensus AMI
@router.post("/query-assistance")
async def query_assistance(request: dict):
    """
    Provide query assistance for Sensus AMI databases.
    Checks if data dictionary exists for requested RNI version/database.
    If not available, provides extraction query to get schema information.
    """
    rni_version = request.get('rni_version')
    database_name = request.get('database_name')
    
    if not rni_version:
        raise HTTPException(status_code=400, detail="RNI version is required. Please specify which version (e.g., 2.1.0, 2.0.0, etc.)")
    
    if not database_name:
        raise HTTPException(status_code=400, detail="Database name is required. Supported: FlexnetDB (MSSQL), AMDS, Router, FWDL (PostgreSQL)")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if RNI version exists
            cursor.execute(
                "SELECT id FROM rni_versions WHERE version_number = %s",
                (rni_version,)
            )
            version_row = cursor.fetchone()
            if not version_row:
                return {
                    "status": "rni_version_not_found",
                    "message": f"RNI version {rni_version} not found. Available versions can be retrieved from /api/data-dictionary/rni-versions",
                    "available_versions_endpoint": "/api/data-dictionary/rni-versions"
                }
            
            rni_version_id = version_row['id']
            
            # Check if database instance exists for this RNI version
            cursor.execute(
                """SELECT di.id, di.database_type, di.server_name, di.port 
                   FROM database_instances di 
                   WHERE di.rni_version_id = %s AND di.database_name = %s""",
                (rni_version_id, database_name)
            )
            instance_row = cursor.fetchone()
            
            if not instance_row:
                return {
                    "status": "database_not_configured",
                    "message": f"Database {database_name} not configured for RNI version {rni_version}",
                    "recommended_action": "Add database instance first using /api/data-dictionary/database-instances",
                    "extraction_needed": True
                }
            
            # Check if we have schema information for this database
            cursor.execute(
                """SELECT COUNT(*) as schema_count 
                   FROM database_schemas ds 
                   WHERE ds.database_instance_id = %s""",
                (instance_row['id'],)
            )
            schema_count = cursor.fetchone()['schema_count']
            
            if schema_count == 0:
                # Generate extraction query based on database type
                extraction_query = generate_extraction_query(instance_row['database_type'], database_name)
                return {
                    "status": "schema_extraction_needed",
                    "message": f"No schema information available for {database_name} on RNI version {rni_version}",
                    "database_type": instance_row['database_type'],
                    "extraction_query": extraction_query,
                    "instructions": "Run the extraction query on your database and use /api/data-dictionary/extract-schema to import the results"
                }
            
            # Schema exists - provide summary
            cursor.execute(
                """SELECT ds.schema_name, COUNT(dt.id) as table_count
                   FROM database_schemas ds
                   LEFT JOIN database_tables dt ON ds.id = dt.schema_id
                   WHERE ds.database_instance_id = %s
                   GROUP BY ds.id, ds.schema_name""",
                (instance_row['id'],)
            )
            schemas = cursor.fetchall()
            
            return {
                "status": "data_dictionary_available",
                "message": f"Data dictionary available for {database_name} on RNI version {rni_version}",
                "database_type": instance_row['database_type'],
                "schemas_available": [{"schema_name": s['schema_name'], "table_count": s['table_count']} for s in schemas],
                "query_endpoint": f"/api/data-dictionary/database-schemas?database_instance_id={instance_row['id']}"
            }
            
    finally:
        conn.close()


def generate_extraction_query(database_type: str, database_name: str) -> str:
    """Generate appropriate extraction query based on database type."""
    
    if database_type.upper() == "MSSQL":
        return f"""-- Sensus AMI {database_name} Schema Extraction Query (MSSQL)
-- Run this query to extract schema information for data dictionary import

SELECT 
    s.name AS schema_name,
    t.name AS table_name,
    c.name AS column_name,
    ty.name AS data_type,
    c.max_length,
    c.precision,
    c.scale,
    c.is_nullable,
    c.is_identity,
    CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key,
    ISNULL(cc.definition, '') AS default_value,
    ISNULL(ep.value, '') AS column_description
FROM sys.tables t
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
INNER JOIN sys.columns c ON t.object_id = c.object_id
INNER JOIN sys.types ty ON c.user_type_id = ty.user_type_id
LEFT JOIN (
    SELECT 
        ic.object_id,
        ic.column_id,
        c.name AS column_name
    FROM sys.indexes i
    INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
    INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
    WHERE i.is_primary_key = 1
) pk ON t.object_id = pk.object_id AND c.column_id = pk.column_id
LEFT JOIN sys.default_constraints cc ON c.default_object_id = cc.object_id
LEFT JOIN sys.extended_properties ep ON t.object_id = ep.major_id AND c.column_id = ep.minor_id AND ep.name = 'MS_Description'
WHERE t.type = 'U'  -- User tables only
ORDER BY s.name, t.name, c.column_id;"""

    else:  # PostgreSQL
        return f"""-- Sensus AMI {database_name} Schema Extraction Query (PostgreSQL)
-- Run this query to extract schema information for data dictionary import

SELECT 
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attname AS column_name,
    t.typname AS data_type,
    CASE WHEN a.attlen > 0 THEN a.attlen ELSE a.atttypmod - 4 END AS max_length,
    0 AS precision,  -- PostgreSQL specific handling would go here
    0 AS scale,      -- PostgreSQL specific handling would go here
    NOT a.attnotnull AS is_nullable,
    CASE WHEN a.attidentity != '' THEN true ELSE false END AS is_identity,
    CASE WHEN pk.attname IS NOT NULL THEN true ELSE false END AS is_primary_key,
    COALESCE(ad.adsrc, '') AS default_value,
    COALESCE(d.description, '') AS column_description
FROM pg_class c
JOIN pg_namespace n ON c.relnamespace = n.oid
JOIN pg_attribute a ON c.oid = a.attrelid
JOIN pg_type t ON a.atttypid = t.oid
LEFT JOIN pg_attrdef ad ON a.attrelid = ad.adrelid AND a.attnum = ad.adnum
LEFT JOIN pg_description d ON c.oid = d.objoid AND a.attnum = d.objsubid
LEFT JOIN (
    SELECT 
        i.indrelid,
        a.attname,
        a.attnum
    FROM pg_index i
    JOIN pg_attribute a ON i.indrelid = a.attrelid AND a.attnum = ANY(i.indkey)
    WHERE i.indisprimary = true
) pk ON c.oid = pk.indrelid AND a.attnum = pk.attnum
WHERE c.relkind = 'r'  -- Regular tables only
  AND n.nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
  AND a.attnum > 0     -- Exclude system columns
  AND NOT a.attisdropped
ORDER BY n.nspname, c.relname, a.attnum;"""


# Schema upload endpoint
@router.post("/upload-schema")
async def upload_schema(
    rni_version_id: int = Form(...),
    database_type: str = Form(...),
    database_name: str = Form(...),
    created_by: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Upload a CSV file containing database schema information.
    """
    # Validate file type
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")
    
    # Validate database_type
    if database_type not in ['MSSQL', 'PostgreSQL']:
        raise HTTPException(status_code=400, detail="Database type must be MSSQL or PostgreSQL")
    
    try:
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # Parse CSV
        csv_reader = csv.DictReader(StringIO(csv_content))
        rows = list(csv_reader)
        
        if not rows:
            raise HTTPException(status_code=400, detail="CSV file is empty")
        
        # Validate required columns
        required_columns = {
            'schema_name', 'table_name', 'column_name', 'data_type', 
            'is_nullable', 'is_primary_key'
        }
        
        if not required_columns.issubset(set(rows[0].keys())):
            missing_columns = required_columns - set(rows[0].keys())
            raise HTTPException(
                status_code=400, 
                detail=f"CSV missing required columns: {', '.join(missing_columns)}"
            )
        
        # Process the data using schema extraction utils
        from schema_extraction_utils import SchemaImporter
        
        importer = SchemaImporter()
        result = await importer.import_csv_schema(
            rni_version_id=rni_version_id,
            database_name=database_name,
            database_type=database_type,
            csv_data=rows,
            created_by=created_by
        )
        
        return {
            "status": "success",
            "message": f"Schema uploaded successfully for {database_name}",
            "statistics": {
                "tables": result.get("tables_imported", 0),
                "columns": result.get("columns_imported", 0),
                "schemas": result.get("schemas_imported", 0)
            }
        }
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid CSV file encoding. Please use UTF-8.")
    except csv.Error as e:
        raise HTTPException(status_code=400, detail=f"CSV parsing error: {str(e)}")
    except Exception as e:
        logger.error(f"Schema upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Schema upload failed: {str(e)}")