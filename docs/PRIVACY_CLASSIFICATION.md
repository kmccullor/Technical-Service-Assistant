# Document Privacy Classification System

## Overview

The Technical Service Assistant now includes an advanced **document privacy classification system** that automatically detects confidential content and marks documents as either `public` or `private`. This system provides privacy-aware search capabilities and ensures sensitive information is properly protected.

## 🔒 **Privacy Classification Features**

### **Automatic Confidentiality Detection**
- **Keyword-based scanning**: Detects common confidentiality indicators
- **Pattern matching**: Uses regex patterns for complex confidentiality phrases  
- **Header/footer analysis**: Scans document headers and footers for classification markings
- **Case-insensitive detection**: Works regardless of text capitalization
- **Multi-language support**: Handles unicode and special characters

### **Database Schema Enhancements**
- **Privacy level columns**: Added to both `pdf_documents` and `document_chunks` tables
- **Privacy constraints**: Ensures only valid values ('public', 'private') are stored
- **Privacy indexes**: Optimized database queries for privacy filtering
- **Enhanced search functions**: Updated `match_document_chunks` with privacy filtering

### **API Privacy Filtering**
- **Request models updated**: All search requests now include `privacy_filter` parameter
- **Granular access control**: Filter by 'public', 'private', or 'all' content
- **Backward compatibility**: Defaults to 'public' access for existing functionality

## 📋 **Confidentiality Keywords Detected**

### **Direct Privacy Indicators**
- `confidential`, `private`, `restricted`, `classified`
- `proprietary`, `internal`, `sensitive`, `privileged`

### **Legal/Compliance Terms**
- `attorney-client`, `work product`, `trade secret`
- `proprietary information`

### **Business Sensitivity**
- `do not distribute`, `internal use only`, `not for distribution`
- `for internal use`, `company confidential`

### **Personal Information Indicators**
- `personally identifiable`, `pii`, `personal information`
- `social security number`, `ssn`, `credit card`

### **Data Classification**
- `top secret`, `secret`, `eyes only`, `need to know`

### **Pattern-Based Detection**
- `"confidential document"` - Documents explicitly marked as confidential
- `"do not share/distribute"` - Distribution restrictions
- `"for internal use only"` - Internal usage limitations
- `"not for public/external"` - External distribution restrictions
- `"strictly/highly confidential"` - Emphasis on confidentiality
- `"classification: private/confidential/restricted"` - Explicit classification markings

## 🏗️ **Database Schema Changes**

### **New Columns**
```sql
-- pdf_documents table
ALTER TABLE pdf_documents 
ADD COLUMN privacy_level text DEFAULT 'public' CHECK (privacy_level IN ('public', 'private'));

-- document_chunks table  
ALTER TABLE document_chunks 
ADD COLUMN privacy_level text DEFAULT 'public' CHECK (privacy_level IN ('public', 'private'));
```

### **New Indexes**
```sql
CREATE INDEX idx_document_chunks_privacy_level ON document_chunks(privacy_level);
CREATE INDEX idx_pdf_documents_privacy_level ON pdf_documents(privacy_level);
```

### **Enhanced Functions**
```sql
-- Updated search function with privacy filtering
CREATE OR REPLACE FUNCTION match_document_chunks (
  query_embedding vector(768),
  match_threshold float,
  match_count int,
  privacy_filter text DEFAULT 'public'  -- NEW PARAMETER
)

-- New privacy statistics function
CREATE OR REPLACE FUNCTION get_privacy_statistics()
RETURNS TABLE (privacy_level text, document_count bigint, chunk_count bigint)
```

## 🔄 **Processing Workflow**

### **1. Document Ingestion**
```
PDF Upload → Text Extraction → Confidentiality Detection → Privacy Classification → Chunk Storage
```

### **2. Privacy Detection Process**
1. **Text Analysis**: Scan entire document text for confidentiality indicators
2. **Keyword Matching**: Check against comprehensive keyword list
3. **Pattern Recognition**: Apply regex patterns for complex phrases
4. **Header/Footer Scanning**: Analyze first and last 5 lines for classification markings
5. **Classification Decision**: Mark as 'private' if any indicators found, otherwise 'public'

### **3. Database Storage**
- **Document Record**: Store with detected privacy level in `pdf_documents.privacy_level`
- **Chunk Records**: All chunks inherit document privacy level in `document_chunks.privacy_level`
- **Consistent Classification**: Ensures all chunks from a document have the same privacy level

## 🔍 **API Usage Examples**

### **Search with Privacy Filtering**
```bash
# Search only public documents (default)
curl -X POST http://localhost:8008/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "quarterly results", "privacy_filter": "public"}'

# Search only private/confidential documents
curl -X POST http://localhost:8008/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "strategic plans", "privacy_filter": "private"}'

# Search all documents (requires appropriate permissions)
curl -X POST http://localhost:8008/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "budget analysis", "privacy_filter": "all"}'
```

### **Hybrid Search with Privacy**
```bash
curl -X POST http://localhost:8008/api/hybrid-search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "confidential merger plans",
    "privacy_filter": "private",
    "confidence_threshold": 0.3
  }'
```

### **RAG Chat with Privacy Filtering**
```bash
curl -X POST http://localhost:8008/api/rag-chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are our internal policies?",
    "privacy_filter": "private",
    "max_context_chunks": 5
  }'
```

## 🧪 **Testing Framework**

### **Automated Tests**
```bash
# Run privacy classification tests
pytest tests/test_privacy_classification.py -v

# Run database integration tests  
pytest tests/test_privacy_integration.py -v

# Run all privacy-related tests
pytest tests/ -k "privacy" -v
```

### **Manual Testing**
```bash
# Interactive privacy testing script
python scripts/test_privacy_classification.py

# Test specific document
echo "This is a CONFIDENTIAL business plan" | python -c "
import sys
sys.path.append('/app')
from pdf_processor.pdf_utils import detect_confidentiality
print(detect_confidentiality(sys.stdin.read()))
"
```

### **Database Migration Testing**
```bash
# Apply migration
psql -d technical_service -f migrations/003_add_privacy_level.sql

# Verify schema changes
python scripts/verify_privacy_schema.py
```

## 📊 **Privacy Statistics**

### **Get Privacy Distribution**
```sql
-- Get document count by privacy level
SELECT * FROM get_privacy_statistics();

-- Manual query for detailed stats
SELECT 
  d.privacy_level,
  COUNT(DISTINCT d.id) as document_count,
  COUNT(c.id) as chunk_count,
  AVG(LENGTH(c.content)) as avg_chunk_size
FROM pdf_documents d
LEFT JOIN document_chunks c ON d.id = c.document_id
GROUP BY d.privacy_level;
```

## 🛡️ **Security Considerations**

### **Data Protection**
- **Default Public**: All documents default to 'public' unless confidentiality is detected
- **Conservative Classification**: Errs on the side of caution - better to mark public content as private than expose private content
- **Immutable Classification**: Once classified as private, documents maintain that status
- **Audit Trail**: All privacy classifications are logged for compliance

### **Access Control**
- **Role-based Filtering**: API endpoints respect privacy filters based on user permissions
- **Search Isolation**: Private content only accessible with explicit privacy_filter='private' or 'all'
- **Web Search Fallback**: Only uses public web sources when private content is insufficient

### **Compliance Features**
- **Keyword Customization**: Privacy detection keywords can be extended for industry-specific compliance
- **Classification Override**: Manual privacy level adjustments supported via database updates
- **Privacy Reporting**: Built-in functions for compliance reporting and auditing

## 🔧 **Configuration Options**

### **Environment Variables**
```bash
# Enable/disable privacy classification (future enhancement)
ENABLE_PRIVACY_CLASSIFICATION=true

# Custom confidentiality keywords file (future enhancement)  
PRIVACY_KEYWORDS_FILE=/app/config/custom_privacy_keywords.txt

# Default privacy level for ambiguous documents (future enhancement)
DEFAULT_PRIVACY_LEVEL=public
```

### **Keyword Customization**
The confidentiality detection function can be extended with industry-specific or organization-specific keywords by modifying the `confidentiality_keywords` list in `pdf_processor/pdf_utils.py`.

## 📈 **Performance Impact**

### **Processing Overhead**
- **Text Analysis**: Adds ~50-100ms per document for confidentiality detection
- **Database Storage**: Minimal overhead with indexed privacy columns
- **Search Performance**: Optimized with privacy-level indexes

### **Memory Usage**
- **Keyword Matching**: Negligible memory impact
- **Pattern Recognition**: Compiled regex patterns cached for efficiency

## 🚀 **Future Enhancements**

### **Planned Features**
- **Machine Learning Classification**: Train ML models for more sophisticated privacy detection
- **Multi-level Classification**: Support for multiple classification levels (public, internal, confidential, secret)
- **Dynamic Reclassification**: Periodic re-evaluation of document privacy levels
- **Privacy Policy Integration**: Automatic classification based on organizational privacy policies
- **Audit Dashboard**: Web interface for privacy classification monitoring and management

### **API Enhancements**
- **Privacy Level Override**: Admin endpoints for manual privacy level adjustment
- **Batch Reclassification**: Bulk privacy level updates for existing documents
- **Privacy Metrics**: Detailed privacy classification analytics and reporting

## 📚 **Related Documentation**

- **Database Schema**: See `migrations/003_add_privacy_level.sql` for complete schema changes
- **API Reference**: Updated endpoint documentation with privacy filtering parameters
- **Testing Guide**: Comprehensive test suite in `tests/test_privacy_*.py`
- **Configuration**: Privacy settings in `config.py` and environment variables

## 🎯 **Best Practices**

### **For Users**
- **Review Classifications**: Periodically review automatically classified documents
- **Explicit Marking**: Use clear confidentiality markings in document headers/footers
- **Consistent Terminology**: Use standard confidentiality terms for reliable detection

### **For Administrators**
- **Regular Audits**: Review privacy classification statistics and accuracy
- **Keyword Updates**: Keep confidentiality keywords current with organizational changes
- **Access Monitoring**: Monitor usage of privacy filtering in search APIs
- **Backup Strategy**: Ensure privacy classifications are included in database backups

## 📞 **Support**

For questions about the privacy classification system:
- **Configuration Issues**: Check `config.py` and environment variables
- **Detection Problems**: Run `scripts/test_privacy_classification.py` for diagnostics
- **Database Issues**: Verify migration with `tests/test_privacy_integration.py`
- **API Issues**: Test endpoints with provided curl examples

---

**The document privacy classification system provides enterprise-grade confidentiality protection while maintaining the flexibility and performance of the Technical Service Assistant.**