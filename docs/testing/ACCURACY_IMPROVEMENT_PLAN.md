# Technical Service Assistant - Accuracy Improvement Plan
# Target: Increase Overall Accuracy from 72.7% to 95%+

## Phase 2A Results (Completed - 2025-09-21)

### Summary
Phase 2A focused on surgical accuracy uplifts via enhanced query expansion and extended security document pattern coverage. These changes eliminated the last high-impact failing case and pushed overall weighted accuracy above the 95% milestone sooner than originally projected for Phase 2.

### Implemented Enhancements
1. Enhanced Query Expansion (`reranker.app.expand_query_with_synonyms`)
    - Product synonym bundles (FlexNet, ESM, RNI, MultiSpeak, PPA)
    - Problem trigger enrichment (problems/issues/errors/failures/trouble/broken)
    - Context-aware activation/configuration enrichment (conditional troubleshooting vs setup expansions)
    - Controlled domain expansions (top 2 per domain key, global cap of 6 added terms)
2. Security Classification Pattern Extension
    - Added compliance/governance and threat/risk pattern groups (future-proofing security_guide detection)
    - Removed duplicate legacy `SECURITY_DOCUMENT_PATTERNS` definition to avoid accidental overrides
3. Validation Parity
    - `validate_accuracy.py` updated to mirror production query expansion logic (Phase 2A parity)
    - `CHANGELOG.md` Unreleased section documents metrics and rationale

### Measured Impact (from `validate_accuracy.py` run)
| Component              | Baseline | Pre-Phase 2A | Post-Phase 2A | Delta (Phase 2A) |
|------------------------|----------|--------------|---------------|------------------|
| Security Classification| 42.9%    | 100.0%       | 100.0%        | +0.0 pp          |
| Query Expansion        | 55.0%    | 83.3%        | 100.0%        | +16.7 pp         |
| Metadata Extraction    | 22.6%    | 85.8%        | 85.8%         | +0.0 pp          |
| Overall Weighted       | 72.7%    | 89.9%        | 95.7%         | +5.8 pp          |

Milestone Exceeded: Overall 95.7% > 95% target.

### Key Win
Resolved failing troubleshooting expansion case: "license activation problems" now expands with licensing + diagnostic terms (troubleshoot, debug, error, key).

### Risk & Residual Gaps
- Current expansion still purely lexical (no semantic weighting) → potential over-expansion in rare edge cases.
- Security patterns rely on regex escalation; future noise risk if pattern base grows unsupervised.

### Decision
Advance to Phase 2B focusing on precision improvements (quality weighting, adaptive control) rather than further brute-force recall.

---

## Current Performance Analysis

### **Semantic Search Accuracy: 80.3% → Target: 95%+**

**Current Issues Identified:**
1. **FlexNet ESM Query Failure (55.0% accuracy)**
   - Product recognition confusion between RNI vs FlexNet vs ESM
   - Search fails to distinguish between product families
   - Keywords not properly weighted for non-RNI products

2. **Document Type Matching (Average 70% across tests)**
   - Some queries return installation guides when user guides expected
   - Cross-category relevance scoring needs refinement

**Root Cause Analysis:**
- Embedding model (nomic-embed-text) may not capture product-specific terminology optimally
- Query expansion not handling product family synonyms
- Metadata weighting not integrated into similarity scoring

### **Document Classification Accuracy: 85.7% → Target: 98%+**

**Specific Misclassifications Found:**
1. **Security Document Confusion (42.9% accuracy)**
   - "Hardware Security Module Installation Guide" → Classified as "installation_guide" instead of "security_guide"
   - "System Security User Guide" → Correctly classified as "security_guide"
   - Pattern: Documents with dual purpose (security + installation) create ambiguity

2. **User Guide Edge Cases (82.4% accuracy)**
   - "System Security User Guide" → Sometimes classified as "security_guide" vs "user_guide"
   - Pattern: Documents with domain-specific purposes create classification conflicts

**Root Cause Analysis:**
- AI classification relies too heavily on primary document type patterns
- Fallback rule-based classification lacks nuanced pattern recognition
- Document content analysis not weighted sufficiently vs filename patterns

### **Metadata Extraction Score: 61.3% → Target: 90%+**

**Critical Gaps:**
1. **Title Extraction: 22.6%** → Target: 85%+
2. **Document Number Extraction: 22.6%** → Target: 80%+
3. **Publisher Information: 22.6%** → Target: 75%+

**Root Cause Analysis:**
- Pattern-based extraction too simplistic for varied document layouts
- OCR not utilized for document header/footer extraction
- Document structure analysis insufficient for complex PDF layouts

## Improvement Strategies

### **1. Enhanced AI Classification System**

#### **A. Multi-Model Classification Approach**
```python
# Implement hierarchical classification
def enhanced_document_classification(text: str, filename: str) -> Dict[str, Any]:
    # Primary classification: Document type
    primary_type = classify_primary_type(text, filename)

    # Secondary classification: Domain specialization
    domain_tags = classify_domain_specialization(text)

    # Tertiary classification: Audience and purpose
    audience_type = classify_target_audience(text)

    # Combine with confidence weighting
    return combine_classifications(primary_type, domain_tags, audience_type)

# Example: "RNI Hardware Security Module Installation Guide"
# Primary: installation_guide (0.9)
# Domain: [security, hardware] (0.8, 0.7)
# Audience: technical_administrators (0.85)
# Final: installation_guide with security specialization
```

#### **B. Enhanced Pattern Recognition**
```python
# Advanced pattern matching for complex document types
ENHANCED_CLASSIFICATION_PATTERNS = {
    'security_installation_guide': {
        'patterns': [
            r'hardware security module.*installation',
            r'security.*installation.*guide',
            r'hsm.*installation'
        ],
        'primary_type': 'installation_guide',
        'specialization': 'security',
        'confidence_boost': 0.15
    },
    'system_security_guide': {
        'patterns': [
            r'system security.*user guide',
            r'security.*user guide',
            r'security guide'
        ],
        'primary_type': 'security_guide',
        'specialization': 'system_administration',
        'confidence_boost': 0.2
    }
}
```

### **2. Advanced Metadata Extraction Pipeline**

#### **A. Multi-Stage Content Analysis**
```python
def enhanced_metadata_extraction(pdf_path: str, text: str) -> Dict[str, Any]:
    # Stage 1: PDF Structure Analysis
    structure_metadata = extract_pdf_structure(pdf_path)

    # Stage 2: OCR Header/Footer Extraction
    header_footer_data = extract_headers_footers_ocr(pdf_path)

    # Stage 3: Content Pattern Analysis
    content_patterns = analyze_content_patterns(text)

    # Stage 4: Cross-Reference Validation
    validated_metadata = cross_validate_metadata(
        structure_metadata, header_footer_data, content_patterns
    )

    return validated_metadata

def extract_pdf_structure(pdf_path: str) -> Dict[str, Any]:
    """Extract title, document info, and metadata from PDF structure"""
    import fitz
    doc = fitz.open(pdf_path)

    # Extract PDF metadata
    pdf_metadata = doc.metadata

    # Extract first page for title detection
    first_page = doc[0]

    # Analyze text blocks for title identification
    blocks = first_page.get_text("dict")["blocks"]

    # Find largest font size text (likely title)
    title_candidates = find_title_candidates(blocks)

    return {
        'pdf_title': pdf_metadata.get('title'),
        'pdf_subject': pdf_metadata.get('subject'),
        'pdf_creator': pdf_metadata.get('creator'),
        'extracted_title': select_best_title(title_candidates),
        'document_info': pdf_metadata
    }
```

#### **B. OCR-Enhanced Extraction**
```python
def extract_headers_footers_ocr(pdf_path: str) -> Dict[str, Any]:
    """Use OCR for header/footer text extraction"""
    import fitz
    from PIL import Image
    import pytesseract

    doc = fitz.open(pdf_path)

    # Extract header regions (top 10% of pages)
    header_text = []
    footer_text = []

    for page_num in range(min(3, len(doc))):  # First 3 pages
        page = doc[page_num]
        pix = page.get_pixmap()

        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Extract header region (top 15%)
        header_height = int(img.height * 0.15)
        header_img = img.crop((0, 0, img.width, header_height))
        header_text.append(pytesseract.image_to_string(header_img))

        # Extract footer region (bottom 10%)
        footer_top = int(img.height * 0.9)
        footer_img = img.crop((0, footer_top, img.width, img.height))
        footer_text.append(pytesseract.image_to_string(footer_img))

    return {
        'header_text': ' '.join(header_text),
        'footer_text': ' '.join(footer_text),
        'extracted_doc_numbers': extract_doc_numbers(' '.join(header_text + footer_text)),
        'extracted_versions': extract_versions(' '.join(header_text + footer_text))
    }
```

### **3. Hybrid Search Enhancement**

#### **A. Query Understanding and Expansion**
```python
def enhanced_query_processing(query: str) -> Dict[str, Any]:
    """Advanced query processing for better semantic matching"""

    # Extract key entities from query
    entities = extract_query_entities(query)

    # Expand query with synonyms and related terms
    expanded_query = expand_query_with_synonyms(query, entities)

    # Weight terms by importance
    weighted_terms = assign_term_weights(expanded_query, entities)

    return {
        'original_query': query,
        'expanded_query': expanded_query,
        'entities': entities,
        'weighted_terms': weighted_terms
    }

PRODUCT_SYNONYMS = {
    'rni': ['regional network interface', 'rni system', 'sensus rni'],
    'flexnet': ['flexnet system', 'flex net', 'flexnet communication'],
    'esm': ['enhanced supervisory message', 'flexnet esm', 'supervisory message'],
    'multispeak': ['multi speak', 'multispeak protocol', 'ms protocol']
}

def expand_query_with_synonyms(query: str, entities: List[str]) -> str:
    """Expand query with product and technical synonyms"""
    expanded = query.lower()

    for entity in entities:
        if entity in PRODUCT_SYNONYMS:
            synonyms = PRODUCT_SYNONYMS[entity]
            # Add OR clause with synonyms
            expanded += f" OR {' OR '.join(synonyms)}"

    return expanded
```

#### **B. Metadata-Weighted Search**
```python
def metadata_weighted_search(query_embedding: List[float], metadata_filters: Dict) -> List[Dict]:
    """Combine vector similarity with metadata relevance scoring"""

    # Base vector similarity search
    base_results = vector_similarity_search(query_embedding, limit=20)

    # Apply metadata scoring
    enhanced_results = []
    for result in base_results:
        metadata_score = calculate_metadata_relevance(result, metadata_filters)

        # Combine vector distance with metadata relevance
        combined_score = (
            (1 - result['distance']) * 0.7 +  # Vector similarity (70%)
            metadata_score * 0.3               # Metadata relevance (30%)
        )

        result['combined_score'] = combined_score
        enhanced_results.append(result)

    # Re-rank by combined score
    return sorted(enhanced_results, key=lambda x: x['combined_score'], reverse=True)

def calculate_metadata_relevance(result: Dict, query_metadata: Dict) -> float:
    """Calculate metadata relevance score"""
    score = 0.0

    # Product match bonus
    if query_metadata.get('product') == result.get('product_name'):
        score += 0.3

    # Document type match bonus
    if query_metadata.get('doc_type') == result.get('document_type'):
        score += 0.25

    # Version proximity bonus
    version_score = calculate_version_proximity(
        query_metadata.get('version'), result.get('product_version')
    )
    score += version_score * 0.2

    # Privacy level match
    if query_metadata.get('privacy') == result.get('privacy_level'):
        score += 0.1

    return min(score, 1.0)
```

### **4. Advanced AI Model Integration**

#### **A. Fine-tuned Classification Models**
```python
# Implement domain-specific fine-tuning for technical documents
def train_technical_document_classifier():
    """Fine-tune base model on technical documentation corpus"""

    training_data = [
        {
            'text': 'RNI Hardware Security Module Installation Guide content...',
            'labels': {
                'primary_type': 'installation_guide',
                'specialization': 'security',
                'product': 'RNI',
                'audience': 'technical_administrators'
            }
        },
        # ... more training examples
    ]

    # Use transformer model with technical vocabulary
    model = AutoModelForSequenceClassification.from_pretrained(
        'microsoft/DialoGPT-medium'  # Or similar technical model
    )

    # Fine-tune on technical documentation patterns
    trained_model = fine_tune_model(model, training_data)

    return trained_model
```

#### **B. Ensemble Classification Approach**
```python
def ensemble_classification(text: str, filename: str) -> Dict[str, Any]:
    """Use multiple models for consensus-based classification"""

    # Model 1: Filename-based classification
    filename_result = classify_by_filename(filename)

    # Model 2: Content-based classification
    content_result = classify_by_content(text)

    # Model 3: Fine-tuned technical document classifier
    technical_result = classify_by_technical_model(text)

    # Model 4: Rule-based pattern matching
    pattern_result = classify_by_patterns(text, filename)

    # Ensemble voting with confidence weighting
    final_classification = ensemble_vote([
        (filename_result, 0.2),
        (content_result, 0.3),
        (technical_result, 0.35),
        (pattern_result, 0.15)
    ])

    return final_classification
```

### **5. Real-time Learning and Feedback**

#### **A. User Feedback Integration**
```python
def implement_feedback_learning():
    """Learn from user search behavior and feedback"""

    # Track search result clicks and relevance
    search_analytics = {
        'query': 'RNI security installation',
        'clicked_results': ['doc_id_1', 'doc_id_3'],
        'not_clicked': ['doc_id_2', 'doc_id_4'],
        'user_rating': 4.2,
        'timestamp': datetime.now()
    }

    # Use feedback to adjust ranking algorithms
    adjust_ranking_weights(search_analytics)

    # Update classification confidence based on user corrections
    update_classification_confidence(search_analytics)
```

#### **B. Continuous Model Improvement**
```python
def continuous_improvement_pipeline():
    """Automated model retraining pipeline"""

    # Collect performance metrics
    weekly_metrics = calculate_weekly_performance()

    # Identify degradation patterns
    if weekly_metrics['accuracy'] < threshold:
        # Retrain with new data
        retrain_models_with_feedback()

        # A/B test new model
        deploy_model_for_testing()

        # Monitor improvement
        track_model_performance()
```

## Implementation Priority and Timeline

### **Phase 1: High-Impact Quick Wins (2-3 weeks)**
1. **Enhanced Pattern Recognition** for security documents
2. **OCR Header/Footer Extraction** for titles and document numbers
3. **Query Synonym Expansion** for product families
4. **Metadata Weighting** in search results

**Expected Improvement:** 72.7% → 85%

### **Phase 2B: Precision & Adaptive Expansion (2-3 weeks)**
Refines recall wins from Phase 2A into balanced precision.
1. **Semantic Expansion Weighting**: Score candidate added terms by cosine similarity to original query embedding; drop low-signal (< similarity threshold) additions.
2. **Adaptive Expansion Controller**: Dynamic cap (2–6 terms) based on query length, specificity (entity count), and presence of problem triggers.
3. **Context-Aware Suppression**: If retrieval top-K already dense in product synonyms (>= X variants in top 5), suppress further synonym repetition to reduce redundancy.
4. **Retrieval Metrics Instrumentation**: Log per-query expansion contribution: added_term_count, retention_rate (terms used in matched chunks), and lift@K (delta relevant chunks vs no-expansion shadow query).
5. **Security Pattern Quality Audit**: Add pattern tagging + false-positive sampling harness (weekly) to prevent drift.

**Expected Improvement:** Maintain ≥95% overall while reducing average added terms by 20–30% without recall loss.

### **Phase 2C: Ensemble & Metadata Fusion (3-4 weeks)**
1. **Lightweight Ensemble Classification**: Blend filename pattern score + content keyword density + shallow embedding centroid similarity.
2. **Metadata-Weighted Hybrid Ranking**: Introduce combined_score = 0.7 * vector_sim + 0.2 * rerank_score + 0.1 * metadata_alignment.
3. **Dynamic Relevance Thresholding**: Adjust rerank cutoff based on entropy of similarity distribution (avoids forcing low-signal chunks).
4. **Structured Title Confidence Model**: Gradient-based heuristic using font size differentials + lexical quality scoring.

**Expected Improvement:** 95.7% → 96.8–97.3% (diminishing returns territory) with improved answer precision.

### **Phase 3: Learning and Optimization (6-8 weeks)**
1. **User Feedback Integration**
2. **Continuous Learning Pipeline**
3. **Advanced Query Understanding**
4. **Performance Monitoring and Auto-tuning**

**Expected Improvement:** 92% → 97%+

## Expected Final Performance Targets

### **Semantic Search Accuracy: 95%+**
- Perfect product family recognition
- Enhanced document type matching
- Context-aware query understanding

### **Document Classification Accuracy: 98%+**
- Resolved security document ambiguity
- Ensemble consensus-based classification
- Fine-tuned domain-specific models

### **Metadata Extraction Score: 90%+**
- OCR-enhanced title extraction (85%+)
- Improved document number detection (80%+)
- Better publisher and version extraction

### **Overall System Accuracy: 97%+**
- Production-ready for critical applications
- Minimal manual correction required
- Self-improving through user feedback

## Resource Requirements

### **Technical Infrastructure**
- OCR service integration (Tesseract/Cloud Vision)
- Model training compute resources
- Extended vector storage for ensemble results
- Real-time feedback processing pipeline

### **Development Effort**
- 2-3 developers for 8-12 weeks
- Machine learning engineer for model fine-tuning
- DevOps support for production deployment
- QA testing for accuracy validation

This comprehensive improvement plan addresses all identified accuracy gaps with specific, implementable solutions that will achieve near-perfect accuracy while maintaining production performance.

---
### Cross References
- See `CHANGELOG.md` (Unreleased Phase 2A) for concise release notes.
- See `validate_accuracy.py` for parity implementation of expansion logic (keep synchronized with `reranker/app.py`).
- Query expansion test harness: `test_query_expansion.py` includes previously failing troubleshooting case.

### Maintenance Notes
- When modifying expansion logic: update both production + validation + test harness to avoid metric drift.
- Add semantic filtering before adding new lexical synonym sets to mitigate dilution risk.
- Schedule weekly audit job (future) to sample top 50 expanded queries and compute precision@K deltas.
