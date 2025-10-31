-- Data Dictionary Schema Migration
-- Stores database schema information for MSSQL and PostgreSQL databases by RNI version

-- RNI Versions table to track different system versions
CREATE TABLE IF NOT EXISTS rni_versions (
    id SERIAL PRIMARY KEY,
    version_number VARCHAR(50) NOT NULL UNIQUE,
    version_name VARCHAR(100),
    description TEXT,
    release_date DATE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Database instances table (different databases within an RNI version)
CREATE TABLE IF NOT EXISTS database_instances (
    id SERIAL PRIMARY KEY,
    rni_version_id INTEGER REFERENCES rni_versions(id) ON DELETE CASCADE,
    database_name VARCHAR(100) NOT NULL,
    database_type VARCHAR(20) NOT NULL CHECK (database_type IN ('MSSQL', 'PostgreSQL')),
    server_name VARCHAR(255),
    port INTEGER,
    description TEXT,
    connection_string_template TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(rni_version_id, database_name, database_type)
);

-- Database schemas table (schemas within databases)
CREATE TABLE IF NOT EXISTS database_schemas (
    id SERIAL PRIMARY KEY,
    database_instance_id INTEGER REFERENCES database_instances(id) ON DELETE CASCADE,
    schema_name VARCHAR(100) NOT NULL,
    description TEXT,
    owner_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(database_instance_id, schema_name)
);

-- Database tables information
CREATE TABLE IF NOT EXISTS database_tables (
    id SERIAL PRIMARY KEY,
    schema_id INTEGER REFERENCES database_schemas(id) ON DELETE CASCADE,
    table_name VARCHAR(128) NOT NULL,
    table_type VARCHAR(20) DEFAULT 'TABLE' CHECK (table_type IN ('TABLE', 'VIEW', 'MATERIALIZED_VIEW')),
    description TEXT,
    row_count BIGINT,
    size_bytes BIGINT,
    owner_name VARCHAR(100),
    created_date TIMESTAMP,
    modified_date TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(schema_id, table_name)
);

-- Database columns information
CREATE TABLE IF NOT EXISTS database_columns (
    id SERIAL PRIMARY KEY,
    table_id INTEGER REFERENCES database_tables(id) ON DELETE CASCADE,
    column_name VARCHAR(128) NOT NULL,
    ordinal_position INTEGER NOT NULL,
    data_type VARCHAR(100) NOT NULL,
    max_length INTEGER,
    precision_value INTEGER,
    scale_value INTEGER,
    is_nullable BOOLEAN NOT NULL DEFAULT true,
    is_primary_key BOOLEAN DEFAULT false,
    is_foreign_key BOOLEAN DEFAULT false,
    is_identity BOOLEAN DEFAULT false,
    default_value TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_id, column_name)
);

-- Primary keys and constraints
CREATE TABLE IF NOT EXISTS table_constraints (
    id SERIAL PRIMARY KEY,
    table_id INTEGER REFERENCES database_tables(id) ON DELETE CASCADE,
    constraint_name VARCHAR(128) NOT NULL,
    constraint_type VARCHAR(20) NOT NULL CHECK (constraint_type IN ('PRIMARY_KEY', 'FOREIGN_KEY', 'UNIQUE', 'CHECK', 'DEFAULT')),
    column_names TEXT[], -- Array of column names
    referenced_table_id INTEGER REFERENCES database_tables(id),
    referenced_column_names TEXT[],
    check_clause TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_id, constraint_name)
);

-- Database indexes
CREATE TABLE IF NOT EXISTS table_indexes (
    id SERIAL PRIMARY KEY,
    table_id INTEGER REFERENCES database_tables(id) ON DELETE CASCADE,
    index_name VARCHAR(128) NOT NULL,
    index_type VARCHAR(20) DEFAULT 'BTREE' CHECK (index_type IN ('BTREE', 'HASH', 'GIST', 'GIN', 'CLUSTERED', 'NONCLUSTERED')),
    column_names TEXT[] NOT NULL, -- Array of column names
    is_unique BOOLEAN DEFAULT false,
    is_primary BOOLEAN DEFAULT false,
    filter_condition TEXT,
    size_bytes BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(table_id, index_name)
);

-- Stored procedures, functions, and other database objects
CREATE TABLE IF NOT EXISTS database_objects (
    id SERIAL PRIMARY KEY,
    schema_id INTEGER REFERENCES database_schemas(id) ON DELETE CASCADE,
    object_name VARCHAR(128) NOT NULL,
    object_type VARCHAR(50) NOT NULL CHECK (object_type IN ('STORED_PROCEDURE', 'FUNCTION', 'TRIGGER', 'VIEW', 'SEQUENCE', 'TYPE')),
    definition TEXT,
    parameters JSONB, -- Store parameter information as JSON
    return_type VARCHAR(100),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(schema_id, object_name, object_type)
);

-- Data dictionary change log for version tracking
CREATE TABLE IF NOT EXISTS schema_change_log (
    id SERIAL PRIMARY KEY,
    rni_version_id INTEGER REFERENCES rni_versions(id),
    database_instance_id INTEGER REFERENCES database_instances(id),
    change_type VARCHAR(20) NOT NULL CHECK (change_type IN ('CREATE', 'ALTER', 'DROP', 'RENAME')),
    object_type VARCHAR(50) NOT NULL,
    object_name VARCHAR(255) NOT NULL,
    schema_name VARCHAR(100),
    change_description TEXT,
    sql_statement TEXT,
    impact_level VARCHAR(20) DEFAULT 'MEDIUM' CHECK (impact_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Custom data dictionary metadata (for business rules, documentation, etc.)
CREATE TABLE IF NOT EXISTS data_dictionary_metadata (
    id SERIAL PRIMARY KEY,
    rni_version_id INTEGER REFERENCES rni_versions(id),
    object_type VARCHAR(50) NOT NULL, -- 'DATABASE', 'SCHEMA', 'TABLE', 'COLUMN', etc.
    object_id INTEGER NOT NULL, -- Reference to the specific object
    metadata_key VARCHAR(100) NOT NULL,
    metadata_value TEXT,
    metadata_type VARCHAR(20) DEFAULT 'TEXT' CHECK (metadata_type IN ('TEXT', 'JSON', 'URL', 'FILE')),
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(object_type, object_id, metadata_key)
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_database_instances_rni_version ON database_instances(rni_version_id);
CREATE INDEX IF NOT EXISTS idx_database_schemas_instance ON database_schemas(database_instance_id);
CREATE INDEX IF NOT EXISTS idx_database_tables_schema ON database_tables(schema_id);
CREATE INDEX IF NOT EXISTS idx_database_columns_table ON database_columns(table_id);
CREATE INDEX IF NOT EXISTS idx_table_constraints_table ON table_constraints(table_id);
CREATE INDEX IF NOT EXISTS idx_table_indexes_table ON table_indexes(table_id);
CREATE INDEX IF NOT EXISTS idx_database_objects_schema ON database_objects(schema_id);
CREATE INDEX IF NOT EXISTS idx_schema_change_log_version ON schema_change_log(rni_version_id);
CREATE INDEX IF NOT EXISTS idx_data_dictionary_metadata_object ON data_dictionary_metadata(object_type, object_id);

-- Insert some sample RNI versions
INSERT INTO rni_versions (version_number, version_name, description, release_date, is_active)
VALUES
    ('1.0.0', 'Initial Release', 'First version of RNI system with basic AMI functionality', '2023-01-15', false),
    ('1.1.0', 'Enhanced AMI', 'Added advanced meter reading capabilities and reporting', '2023-06-20', false),
    ('2.0.0', 'Major Upgrade', 'Complete system overhaul with new architecture', '2024-01-30', false),
    ('2.1.0', 'Current Production', 'Latest stable release with security updates', '2024-08-15', true),
    ('2.2.0', 'Development', 'Next release in development with new features', '2025-12-01', false)
ON CONFLICT (version_number) DO NOTHING;

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to automatically update the updated_at column
CREATE TRIGGER update_rni_versions_updated_at BEFORE UPDATE ON rni_versions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_database_instances_updated_at BEFORE UPDATE ON database_instances FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_database_schemas_updated_at BEFORE UPDATE ON database_schemas FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_database_tables_updated_at BEFORE UPDATE ON database_tables FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_database_columns_updated_at BEFORE UPDATE ON database_columns FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_table_constraints_updated_at BEFORE UPDATE ON table_constraints FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_table_indexes_updated_at BEFORE UPDATE ON table_indexes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_database_objects_updated_at BEFORE UPDATE ON database_objects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_data_dictionary_metadata_updated_at BEFORE UPDATE ON data_dictionary_metadata FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- View for complete schema overview
CREATE OR REPLACE VIEW v_schema_overview AS
SELECT
    rv.version_number,
    rv.version_name,
    di.database_name,
    di.database_type,
    ds.schema_name,
    dt.table_name,
    dt.table_type,
    dt.description as table_description,
    dt.row_count,
    COUNT(dc.id) as column_count,
    dt.created_at as table_created_at
FROM rni_versions rv
JOIN database_instances di ON rv.id = di.rni_version_id
JOIN database_schemas ds ON di.id = ds.database_instance_id
JOIN database_tables dt ON ds.id = dt.schema_id
LEFT JOIN database_columns dc ON dt.id = dc.table_id
WHERE rv.is_active = true AND di.is_active = true AND dt.is_active = true
GROUP BY rv.version_number, rv.version_name, di.database_name, di.database_type,
         ds.schema_name, dt.table_name, dt.table_type, dt.description, dt.row_count, dt.created_at
ORDER BY rv.version_number, di.database_name, ds.schema_name, dt.table_name;

-- View for detailed column information
CREATE OR REPLACE VIEW v_column_details AS
SELECT
    rv.version_number,
    di.database_name,
    di.database_type,
    ds.schema_name,
    dt.table_name,
    dc.column_name,
    dc.ordinal_position,
    dc.data_type,
    dc.max_length,
    dc.precision_value,
    dc.scale_value,
    dc.is_nullable,
    dc.is_primary_key,
    dc.is_foreign_key,
    dc.is_identity,
    dc.default_value,
    dc.description
FROM rni_versions rv
JOIN database_instances di ON rv.id = di.rni_version_id
JOIN database_schemas ds ON di.id = ds.database_instance_id
JOIN database_tables dt ON ds.id = dt.schema_id
JOIN database_columns dc ON dt.id = dc.table_id
WHERE rv.is_active = true AND di.is_active = true AND dt.is_active = true
ORDER BY rv.version_number, di.database_name, ds.schema_name, dt.table_name, dc.ordinal_position;

COMMENT ON TABLE rni_versions IS 'Stores RNI (system) version information';
COMMENT ON TABLE database_instances IS 'Database instances for each RNI version';
COMMENT ON TABLE database_schemas IS 'Database schemas within each instance';
COMMENT ON TABLE database_tables IS 'Tables and views within each schema';
COMMENT ON TABLE database_columns IS 'Column definitions for each table';
COMMENT ON TABLE table_constraints IS 'Primary keys, foreign keys, and other constraints';
COMMENT ON TABLE table_indexes IS 'Database indexes for performance optimization';
COMMENT ON TABLE database_objects IS 'Stored procedures, functions, and other database objects';
COMMENT ON TABLE schema_change_log IS 'Tracks all schema changes across versions';
COMMENT ON TABLE data_dictionary_metadata IS 'Custom metadata and business rules for database objects';
