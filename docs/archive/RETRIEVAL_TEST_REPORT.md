# 🔍 Technical Service Assistant - Retrieval Test Report

**Test Date:** 2025-09-16T12:31:09.383319
**Total Documents:** 9
**Total Questions Tested:** 160

## 📊 Overall Performance Metrics

| Metric | Score | Grade |
|--------|-------|-------|
| **Recall@1** | 0.487 | 🥉 Fair |
| **Recall@5** | 0.719 | 🥉 Fair |
| **Recall@10** | 0.812 | 🥉 Fair |
| **Avg Similarity** | -10.809 | ❌ Poor |

## ⚡ Performance Metrics

- **Average Embedding Time:** 0.051s
- **Average Search Time:** 0.025s
- **Average Total Time:** 0.076s

## 📚 Document-Level Results

### 📖 RNI 4.16.1 Release Notes.pdf

**Chunks:** 200 | **Questions:** 20 | **Successful Tests:** 20

| Metric | Score |
|--------|-------|
| Recall@1 | 0.550 |
| Recall@5 | 0.750 |
| Recall@10 | 0.750 |
| Avg Similarity | -9.311 |
| Avg Response Time | 0.072s |

#### Sample Questions Tested:
1. What is the title of the document?
2. On what date was the General Availability (GA) release for RNI 4.16.1 made?
3. Who holds the copyright for this document?
4. Where is Sensus USA located?
5. What phone number can be used to contact Sensus USA?

### 📖 RNI 4.16 Base Station Security User Guide.pdf

**Chunks:** 3 | **Questions:** 20 | **Successful Tests:** 20

| Metric | Score |
|--------|-------|
| Recall@1 | 0.250 |
| Recall@5 | 0.400 |
| Recall@10 | 0.450 |
| Avg Similarity | -5.839 |
| Avg Response Time | 0.073s |

#### Sample Questions Tested:
1. What software is required to view the RNI 4.16 Base Station Security User Guide?
2. When was the latest update made to the RNI 4.16 Base Station Security User Guide? (Assuming the document includes a revision date)
3. Where can I download a compatible PDF reader for viewing the RNI 4.16 Base Station Security User Guide?
4. How do I open a protected PDF file like the RNI 4.16 Base Station Security User Guide?
5. Why is the RNI 4.16 Base Station Security User Guide protected?

### 📖 RNI 4.16 ESM User Guide.pdf

**Chunks:** 226 | **Questions:** 20 | **Successful Tests:** 20

| Metric | Score |
|--------|-------|
| Recall@1 | 0.200 |
| Recall@5 | 0.600 |
| Recall@10 | 0.850 |
| Avg Similarity | -11.137 |
| Avg Response Time | 0.077s |

#### Sample Questions Tested:
1. What is the title of the document?
2. What does FlexNet ESM stand for?
3. What is the revision number of the current version of this guide?
4. When was the guide last updated (latest revision)?
5. Where can you find the description of the changes made in the 3.1 revision?

### 📖 RNI 4.16 Hardware Security Module Installation Guide.pdf

**Chunks:** 227 | **Questions:** 20 | **Successful Tests:** 20

| Metric | Score |
|--------|-------|
| Recall@1 | 0.400 |
| Recall@5 | 0.700 |
| Recall@10 | 0.750 |
| Avg Similarity | -10.175 |
| Avg Response Time | 0.076s |

#### Sample Questions Tested:
1. What is the title of the document?
2. What is the revision number of the initial version of the document?
3. On what date was the initial version of the document released?
4. How many times has the document been revised as of the given content?
5. What was updated in the RNI 3.1 revision?

### 📖 RNI 4.16 Key Management Integration Guide.pdf

**Chunks:** 153 | **Questions:** 20 | **Successful Tests:** 20

| Metric | Score |
|--------|-------|
| Recall@1 | 0.500 |
| Recall@5 | 0.950 |
| Recall@10 | 0.950 |
| Avg Similarity | -12.575 |
| Avg Response Time | 0.075s |

#### Sample Questions Tested:
1. What is the title of the document?
2. In what year was the initial version of this guide released?
3. On which date was the guide updated for RNI 4.0?
4. When was the guide updated for RNI 4.1?
5. What is the revision number of the initial version of the guide?

### 📖 RNI 4.16 Microsoft Active Directory Integration Guide.pdf

**Chunks:** 127 | **Questions:** 20 | **Successful Tests:** 20

| Metric | Score |
|--------|-------|
| Recall@1 | 0.550 |
| Recall@5 | 0.600 |
| Recall@10 | 0.800 |
| Avg Similarity | -11.471 |
| Avg Response Time | 0.078s |

#### Sample Questions Tested:
1. What is the title of the document?
2. What is the revision number of the document?
3. When was the first revision of the document made?
4. What changes were made in the first revision of the document?
5. When was the second revision of the document made?

### 📖 RNI 4.16 Reports Operation Reference Manual.pdf

**Chunks:** 849 | **Questions:** 20 | **Successful Tests:** 20

| Metric | Score |
|--------|-------|
| Recall@1 | 0.650 |
| Recall@5 | 0.900 |
| Recall@10 | 1.000 |
| Avg Similarity | -15.452 |
| Avg Response Time | 0.080s |

#### Sample Questions Tested:
1. What is the title of the document?
2. How many revisions does this document have?
3. When was the document first updated?
4. What was added to the document with Revision 12?
5. How was the BackfillReport details updated in Revision 15?

### 📖 RNI 4.16 System Security User Guide.pdf

**Chunks:** 205 | **Questions:** 20 | **Successful Tests:** 20

| Metric | Score |
|--------|-------|
| Recall@1 | 0.800 |
| Recall@5 | 0.850 |
| Recall@10 | 0.950 |
| Avg Similarity | -10.511 |
| Avg Response Time | 0.078s |

#### Sample Questions Tested:
1. What was the first revision date of the RNI System Security User Guide?
2. In what month and year was the guide updated for RNI 3.1 SP2?
3. How many revisions does the RNI System Security User Guide have as of AUG-10023-26?
4. When was the guide updated for RNI 2.1.0?
5. What is the latest version of RNI that the guide was updated for, as per the revision history?


## 🎯 Key Findings

### ✅ Strengths
- Decent recall performance
- Good semantic matching
- Fast response times < 1s

### 🔄 Areas for Improvement
- Consider improving chunking strategy for better Recall@1
- Optimize embedding model or add reranking for better similarity scores


## 🛠️ Recommendations

1. **Embedding Quality**: Current nomic-embed-text model performing adequately
2. **Retrieval Performance**: Needs improvement recall rates
3. **Performance**: Excellent response times

---
*Report generated by Technical Service Assistant Test Suite*
