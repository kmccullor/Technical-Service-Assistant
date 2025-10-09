# Sensus AMI Query Assistant Workflow Documentation

## Overview
This document outlines the complete workflow for using the Data Dictionary system to support employee requests for Sensus AMI Infrastructure database queries.

## Supported Databases

### Microsoft SQL Server
- **FlexnetDB**: Primary Sensus AMI database containing meter data, billing information, and infrastructure management

### PostgreSQL Databases  
- **AMDS**: Advanced Metering Data System for real-time meter reading and data processing
- **Router**: Communication management database for AMI network routing and device connectivity  
- **FWDL**: Firmware Download management system for device updates and version control

## Employee Request Workflow

### 1. Initial Request Assessment
When an employee requests help with database queries:

**ALWAYS ask for the RNI version if not provided:**
- "Which RNI version are you working with? (e.g., 2.1.0, 2.0.0, 1.1.0)"
- Available versions can be found at: `http://localhost:3000/data-dictionary` → "AMI Query Assistant" tab

### 2. Query Assistance Process

#### Using the Web Interface
1. Navigate to: `http://localhost:3000/data-dictionary`
2. Click on the **"AMI Query Assistant"** tab
3. Select the **RNI Version** from the dropdown
4. Select the **Database Name** (FlexnetDB, AMDS, Router, or FWDL)
5. Click **"Get Query Assistance"**

#### Using the API Directly
```bash
curl -X POST http://localhost:8008/api/data-dictionary/query-assistance \
  -H "Content-Type: application/json" \
  -d '{
    "rni_version": "2.1.0",
    "database_name": "FlexnetDB"
  }'
```

### 3. Response Scenarios

#### Scenario A: Data Dictionary Available ✅
**Response Status:** `data_dictionary_available`
- **Action:** Proceed with query development using available schema information
- **Available Information:** 
  - Schema names and table counts
  - Direct links to detailed schema documentation
  - Ready to assist with specific queries

#### Scenario B: Schema Extraction Needed ⚠️
**Response Status:** `schema_extraction_needed`
- **Action:** Database schema must be extracted first
- **Provided:** Database-specific extraction query
- **Next Steps:** Follow the extraction procedure below

#### Scenario C: Database Not Configured ❌
**Response Status:** `database_not_configured`
- **Action:** Database instance must be added to the data dictionary
- **Next Steps:** Configure the database instance first

#### Scenario D: Invalid RNI Version ❌
**Response Status:** `rni_version_not_found`
- **Action:** Verify and use a valid RNI version
- **Available Versions:** Check `/api/data-dictionary/rni-versions`

## Schema Upload Procedure

When schema extraction is needed (Scenario B above):

### Step 1: Get the Extraction Query
The system provides a database-specific extraction query that you must run on your database. Examples:

**For FlexnetDB (MSSQL):**
```sql
-- Sensus AMI FlexnetDB Schema Extraction Query (MSSQL)
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
-- ... (full query provided by system)
ORDER BY s.name, t.name, c.column_id;
```

**For AMDS/Router/FWDL (PostgreSQL):**
```sql
-- Sensus AMI [Database] Schema Extraction Query (PostgreSQL)
SELECT 
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attname AS column_name,
    t.typname AS data_type,
    -- ... (full query provided by system)
ORDER BY n.nspname, c.relname, a.attnum;
```

### Step 2: Execute the Query on Your Database
**⚠️ Important: You must have direct access to your database servers**

1. Copy the provided extraction query
2. Connect to your target database (FlexnetDB, AMDS, Router, or FWDL) using your SQL client
3. Execute the query in your database environment  
4. Export the query results as a CSV file

### Step 3: Upload Schema Data
**The system cannot access your database servers directly - you must upload the data**

1. Navigate to: `http://localhost:3000/data-dictionary` 
2. Click the **"Upload Schema"** button
3. Select your RNI version and database type
4. Upload the CSV file generated from Step 2
5. Or use the API endpoint: `/api/data-dictionary/upload-schema`

## API Endpoints Reference

### Core Endpoints
- **Query Assistance:** `POST /api/data-dictionary/query-assistance`
- **RNI Versions:** `GET /api/data-dictionary/rni-versions` 
- **Database Instances:** `GET /api/data-dictionary/database-instances`
- **Schema Upload:** `POST /api/data-dictionary/upload-schema` (File upload)
- **Health Check:** `GET /api/data-dictionary/health`

### Frontend Access
- **Main Interface:** `http://localhost:3000/data-dictionary`
- **AMI Assistant:** `http://localhost:3000/data-dictionary` → "AMI Query Assistant" tab
- **Upload Schema:** Click "Upload Schema" button → Follow guided process

## Best Practices for Employee Support

### 1. Always Validate Requirements
- ✅ Confirm RNI version
- ✅ Confirm database name (FlexnetDB, AMDS, Router, FWDL)
- ✅ Understand the specific query requirements

2. **Use the Systematic Approach**
1. Check if data dictionary exists for the version/database combination
2. If not available, provide extraction query for manual execution
3. Guide through the upload process with the generated CSV
4. Provide query guidance using available schema information

### 3. Common Error Handling
- **Missing RNI Version:** Guide to available versions
- **Invalid Database:** Clarify supported databases
- **Query Execution Issues:** Verify database access and SQL client configuration
- **Upload Issues:** Check CSV format, file size, and required columns
- **Access Problems:** Confirm user has database read permissions

## Example Employee Interaction

**Employee Request:** "I need to write a query for FlexnetDB to get all meter readings from last month."

**Your Response Process:**
1. **Ask:** "Which RNI version are you working with?"
2. **Employee:** "2.1.0"
3. **Check:** Use query assistance for RNI 2.1.0 + FlexnetDB
4. **If Available:** Provide schema information and query guidance
5. **If Not Available:** Provide extraction query and upload instructions
6. **Guide:** Walk through the CSV generation and upload process

## Troubleshooting

### Common Issues
1. **"Database connection failed"** → Check if services are running: `docker compose ps`
2. **"RNI version not found"** → Verify version exists: `curl http://localhost:8008/api/data-dictionary/rni-versions`
3. **"Schema extraction needed"** → Follow the extraction procedure above
4. **Frontend not loading** → Check frontend service: `docker logs rag-app`

### Service Health Checks
```bash
# Check all services
docker compose ps

# Test data dictionary health
curl http://localhost:8008/api/data-dictionary/health

# Test frontend accessibility  
curl -I http://localhost:3000/data-dictionary
```

## Integration with Existing Systems

The Data Dictionary system integrates with:
- **Existing PDF ingestion pipeline**: For documentation storage
- **RAG search system**: For intelligent query suggestions
- **Vector database**: For semantic schema search
- **Next.js frontend**: For unified user experience

## Security Considerations

- Database connection strings are stored securely
- No direct database credentials exposed in queries
- Schema extraction queries are read-only
- All API endpoints include proper error handling
- Frontend includes input validation and sanitization

---

**Last Updated:** September 29, 2025
**System Status:** Fully Operational
**Supported RNI Versions:** 1.0.0, 1.1.0, 2.0.0, 2.1.0, 2.2.0 (development)