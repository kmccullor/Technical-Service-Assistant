# Sensus AMI Query Assistant - Quick Reference

## 🔄 Employee Request Workflow

### Step 1: Always Ask for RNI Version
**If not provided, ask:** "Which RNI version are you working with?"
- Available: 1.0.0, 1.1.0, 2.0.0, 2.1.0, 2.2.0

### Step 2: Identify Database  
**Supported Sensus AMI Databases:**
- **FlexnetDB** (Microsoft SQL Server) - Primary AMI database
- **AMDS** (PostgreSQL) - Advanced Metering Data System  
- **Router** (PostgreSQL) - Communication management
- **FWDL** (PostgreSQL) - Firmware Download management

### Step 3: Check Data Dictionary Status
**Use AMI Query Assistant:**
- Web: `http://localhost:3000/data-dictionary` → "AMI Query Assistant" tab
- API: `POST /api/data-dictionary/query-assistance`

## 📋 Response Types

| Status | Icon | Action Required |
|--------|------|-----------------|
| ✅ **data_dictionary_available** | 🟢 | Ready for queries - provide schema info |
| ⚠️ **schema_extraction_needed** | 🟡 | Run extraction query & upload CSV |  
| ❌ **database_not_configured** | 🔴 | Add database instance |
| ❌ **rni_version_not_found** | 🔴 | Use valid RNI version |

## 🚀 Quick Commands

```bash
# Check system health
curl http://localhost:8008/api/data-dictionary/health

# Get available RNI versions
curl http://localhost:8008/api/data-dictionary/rni-versions

# Query assistance example
curl -X POST http://localhost:8008/api/data-dictionary/query-assistance \
  -H "Content-Type: application/json" \
  -d '{"rni_version": "2.1.0", "database_name": "FlexnetDB"}'
```

## 🔧 When Schema Upload is Needed

1. **Copy** the provided extraction query
2. **Connect** to your database server
3. **Execute** query in your SQL client
4. **Export** results as CSV file
5. **Upload** via "Upload Schema" button

## 🎯 Key Points

- **Always validate RNI version first**
- **Manual process**: User must run queries and upload results
- **No direct database access**: System cannot connect to user databases
- **Supported databases**: FlexnetDB, AMDS, Router, FWDL
- **Frontend available**: Easy-to-use web interface with guided upload
- **API available**: For automation and integration

---
**Quick Access:** http://localhost:3000/data-dictionary → AMI Query Assistant