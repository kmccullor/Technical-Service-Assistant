#!/usr/bin/env tsx

import { Pool } from 'pg'
import { readFileSync } from 'fs'
import { join } from 'path'

if (!process.env.DATABASE_URL) {
  console.error('DATABASE_URL environment variable is required')
  process.exit(1)
}

async function runMigrations() {
  const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
  })

  try {
    console.log('🔄 Running database migrations...')
    
    // Read and execute migration file
    const migrationPath = join(process.cwd(), 'lib', 'db', 'migrations', '001_initial.sql')
    const migrationSQL = readFileSync(migrationPath, 'utf-8')
    
    await pool.query(migrationSQL)
    
    console.log('✅ Migrations completed successfully')
  } catch (error) {
    console.error('❌ Migration failed:', error)
    process.exit(1)
  } finally {
    await pool.end()
  }
}

runMigrations()