# Log Analysis & Issue Resolution Guide

## 🔍 **Automated Log Analysis**

The morning checklist now includes comprehensive log analysis that automatically:

### **Enhanced Daily Checklist Features:**

#### 📊 **Critical Issue Detection**
- **Network Connectivity Issues**: DNS resolution failures to Ollama instances
- **Model Loading Problems**: Missing or inaccessible AI models  
- **Database Errors**: Schema violations and connection failures
- **Processing Pipeline Failures**: Document ingestion breakdowns
- **Performance Issues**: Memory/resource warnings

#### 🎯 **Specific Issue Tracking**
- **PDF Processor**: Tracks embedding failures, network errors, DB connection issues
- **Database**: Monitors constraint violations and missing columns
- **Ollama Instances**: Verifies model availability across all 4 containers
- **Redis Cache**: Detects memory configuration problems

#### 🛠️ **Automated Recommendations**
- **Immediate Actions**: Exact commands to fix critical issues
- **Root Cause Analysis**: Identifies underlying problems
- **Impact Assessment**: Shows what functionality is affected
- **Priority Levels**: Critical vs Warning issue classification

## 🚨 **Common Issues & Fixes**

### **Critical Issues (Stop Development)**

#### **Network Connectivity Failures**
```bash
# Symptoms: PDF processor cannot resolve Ollama hostnames
# Impact: Document processing completely broken
# Fix:
docker compose restart pdf_processor
docker network inspect technical-service-assistant_default
# If issues persist:
docker compose down && docker compose up -d
```

#### **Missing AI Models** 
```bash
# Symptoms: Ollama instances have no models loaded
# Impact: Embedding generation and AI classification failing
# Fix:
docker exec ollama-server-1 ollama pull nomic-embed-text:v1.5
docker exec ollama-server-1 ollama pull mistral:7b
# Repeat for servers 2, 3, 4
```

#### **Database Connection Failures**
```bash
# Symptoms: Cannot connect to pgvector database (vector_db)
# Impact: Documents cannot be stored / retrieval fails
# Fix:
docker compose restart pgvector pdf_processor
# Check connectivity (correct DB target):
docker exec -it pgvector psql -U postgres -d vector_db -c "SELECT 1;"
```

### **Warning Issues (Monitor/Schedule)**

#### **Database Schema Problems**
```bash
# Symptoms: Column missing errors, constraint violations
# Impact: Ingestion failures / chat retrieval degraded
# Fix (inspect in proper DB):
docker exec -it pgvector psql -U postgres -d vector_db -c "\d+ document_chunks;"
# If severe and cannot reconcile with migrations:
make recreate-db  # DESTRUCTIVE - backup first!
```

#### **Redis Memory Configuration**
```bash
# Symptoms: Memory overcommit warnings
# Impact: Performance degradation
# Fix:
sudo sysctl vm.overcommit_memory=1
echo 'vm.overcommit_memory = 1' | sudo tee -a /etc/sysctl.conf
```

## 📋 **Updated Daily Commands**

### **Complete Morning Routine**
```bash
make morning
```
Now includes:
- Docker service comparison
- Detailed log analysis with issue counts
- Specific recommendations for each problem
- Automated fix suggestions

### **Quick Log Analysis**
```bash
make check-logs
```
Shows:
- Error/warning counts by container
- Recent network connectivity issues
- Embedding generation failures
- Database schema problems

### **Advanced Analysis**
```bash
./scripts/analyze_logs.sh
```
Provides:
- Root cause analysis
- Performance impact assessment
- Step-by-step fix procedures
- System health scoring

## 🎯 **Issue Priority Matrix**

| Issue Type | Threshold | Action |
|------------|-----------|--------|
| Network Issues | >0 | **CRITICAL** - Stop development |
| Model Loading | >0 | **CRITICAL** - Fix immediately |
| PDF Processor Errors | >100 | **CRITICAL** - System failure |
| Database Errors | >2 | **WARNING** - Schedule fix |
| Redis Warnings | >0 | **INFO** - Optimize when convenient |

## 📊 **Log Analysis Output**

The enhanced checklist provides:

### **Issue Breakdown**
- Network Issues: DNS resolution failures
- Model Loading Issues: Missing AI models  
- PDF Processor Errors: Total error count
- Database Errors: Schema/constraint problems
- Redis Warnings: Memory configuration

### **System Status**
- **🔴 Critical**: Major functionality broken
- **🟡 Caution**: Performance/feature impacts
- **🟢 Ready**: All systems operational

### **Automated Recommendations**
- Exact commands to run
- Expected outcomes
- Verification steps
- Prevention strategies

## 🔧 **Integration with Development**

**Before ANY development work:**
1. Run `make morning`
2. Review issue recommendations
3. Fix critical issues (🔴) immediately
4. Plan warning issue (🟡) resolution
5. Only proceed when system shows 🟢

This ensures a **stable foundation** for all development activities and prevents working on broken infrastructure.