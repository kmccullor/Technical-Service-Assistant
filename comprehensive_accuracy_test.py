import json
import sys
import time
from typing import List

import psycopg2
import requests

sys.path.append("/app")
from config import get_settings

settings = get_settings()


def get_embedding(text: str) -> List[float]:
    """Get embedding from Ollama with fallback across instances"""
    ollama_instances = [
        "http://ollama-server-1:11434/api/embeddings",
        "http://ollama-server-2:11434/api/embeddings",
        "http://ollama-server-3:11434/api/embeddings",
        "http://ollama-server-4:11434/api/embeddings",
    ]

    for url in ollama_instances:
        try:
            response = requests.post(url, json={"model": "nomic-embed-text:v1.5", "prompt": text}, timeout=10)
            response.raise_for_status()
            embedding = response.json().get("embedding")
            if embedding:
                return embedding
        except Exception as e:
            print(f"Warning: Failed to get embedding from {url}: {e}")
            continue

    raise Exception("Failed to get embedding from all Ollama instances")


def test_semantic_search_accuracy():
    """Test semantic search accuracy with known queries and expected document types"""

    test_queries = [
        {
            "query": "How to install RNI security features and configure certificates?",
            "expected_types": ["installation_guide", "security_guide"],
            "expected_products": ["RNI"],
            "keywords": ["install", "security", "certificate", "configuration"],
        },
        {
            "query": "RNI user administration and system management procedures",
            "expected_types": ["user_guide", "reference_manual"],
            "expected_products": ["RNI"],
            "keywords": ["user", "admin", "system", "management"],
        },
        {
            "query": "FlexNet ESM device manager configuration and setup",
            "expected_types": ["user_guide", "installation_guide"],
            "expected_products": ["FlexNet", "ESM"],
            "keywords": ["device", "manager", "configuration", "setup"],
        },
        {
            "query": "Microsoft Active Directory integration with RNI system",
            "expected_types": ["integration_guide"],
            "expected_products": ["RNI"],
            "keywords": ["microsoft", "active directory", "integration"],
        },
        {
            "query": "Latest RNI 4.16 release notes and new features",
            "expected_types": ["release_notes"],
            "expected_products": ["RNI"],
            "keywords": ["release", "notes", "4.16", "features"],
        },
        {
            "query": "Hardware security module installation and configuration",
            "expected_types": ["installation_guide", "security_guide"],
            "expected_products": ["RNI"],
            "keywords": ["hardware", "security", "module", "HSM"],
        },
    ]

    conn = psycopg2.connect(
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
    )
    cur = conn.cursor()

    print("🎯 SEMANTIC SEARCH ACCURACY TEST")
    print("=" * 80)

    total_tests = len(test_queries)
    passed_tests = 0
    accuracy_scores = []

    for i, test in enumerate(test_queries, 1):
        print(f"\n🔍 Test {i}/{total_tests}: {test['query']}")
        print("-" * 60)

        try:
            # Get embedding for query
            start_time = time.time()
            query_embedding = get_embedding(test["query"])
            embedding_time = time.time() - start_time

            # Perform vector similarity search
            search_start = time.time()
            cur.execute(
                """
                SELECT
                    d.file_name,
                    d.document_type,
                    d.product_name,
                    d.product_version,
                    d.classification_confidence,
                    dc.content,
                    dc.embedding <=> %s::vector as distance
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> %s::vector
                LIMIT 10;
            """,
                (query_embedding, query_embedding),
            )

            results = cur.fetchall()
            search_time = time.time() - search_start

            print(f"⏱️  Query time: {embedding_time:.2f}s embedding + {search_time:.3f}s search")

            # Analyze results
            doc_types_found = set()
            products_found = set()
            distances = []
            keyword_matches = 0

            print(f"\n📊 Top 5 Results:")
            for j, (file_name, doc_type, product, version, confidence, content, distance) in enumerate(results[:5], 1):
                doc_types_found.add(doc_type)
                products_found.add(product)
                distances.append(distance)

                # Check keyword matches in content
                content_lower = content.lower()
                matches = sum(1 for keyword in test["keywords"] if keyword.lower() in content_lower)
                keyword_matches += matches

                print(f"  {j}. {file_name}")
                print(f"     Type: {doc_type} | Product: {product} {version} | Distance: {distance:.4f}")
                print(f"     Keywords matched: {matches}/{len(test['keywords'])}")
                print(f"     Content preview: {content[:100]}...")

            # Calculate accuracy metrics
            type_accuracy = len(set(test["expected_types"]) & doc_types_found) / len(test["expected_types"])
            product_accuracy = len(set(test["expected_products"]) & products_found) / len(test["expected_products"])
            avg_distance = sum(distances) / len(distances) if distances else 1.0
            keyword_accuracy = keyword_matches / (len(test["keywords"]) * 5)  # 5 results checked

            # Overall accuracy score (weighted)
            overall_accuracy = (
                type_accuracy * 0.4
                + product_accuracy * 0.3  # 40% weight on document type accuracy
                + (1 - avg_distance) * 0.2  # 30% weight on product accuracy
                + keyword_accuracy  # 20% weight on semantic similarity (lower distance = higher accuracy)
                * 0.1  # 10% weight on keyword matching
            )

            accuracy_scores.append(overall_accuracy)

            print(f"\n📈 Accuracy Metrics:")
            print(
                f"   Document Type: {type_accuracy:.1%} ({len(set(test['expected_types']) & doc_types_found)}/{len(test['expected_types'])} types matched)"
            )
            print(
                f"   Product Match: {product_accuracy:.1%} ({len(set(test['expected_products']) & products_found)}/{len(test['expected_products'])} products matched)"
            )
            print(f"   Semantic Similarity: {(1-avg_distance):.1%} (avg distance: {avg_distance:.4f})")
            print(f"   Keyword Relevance: {keyword_accuracy:.1%} ({keyword_matches} matches in top 5)")
            print(f"   🎯 Overall Accuracy: {overall_accuracy:.1%}")

            # Pass/fail criteria (70% threshold)
            if overall_accuracy >= 0.7:
                print(f"   ✅ PASS")
                passed_tests += 1
            else:
                print(f"   ❌ FAIL (below 70% threshold)")

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            accuracy_scores.append(0.0)

    # Final summary
    print(f"\n" + "=" * 80)
    print(f"🏆 SEMANTIC SEARCH ACCURACY SUMMARY")
    print(f"   Tests Passed: {passed_tests}/{total_tests} ({passed_tests/total_tests:.1%})")
    print(f"   Average Accuracy: {sum(accuracy_scores)/len(accuracy_scores):.1%}")
    print(f"   Min Accuracy: {min(accuracy_scores):.1%}")
    print(f"   Max Accuracy: {max(accuracy_scores):.1%}")

    if passed_tests >= total_tests * 0.8:  # 80% pass rate
        print(f"   🎉 OVERALL RESULT: EXCELLENT - Search accuracy meets production standards")
    elif passed_tests >= total_tests * 0.6:  # 60% pass rate
        print(f"   ⚠️  OVERALL RESULT: GOOD - Search accuracy acceptable with room for improvement")
    else:
        print(f"   🚨 OVERALL RESULT: POOR - Search accuracy needs significant improvement")

    cur.close()
    conn.close()
    return accuracy_scores


def test_metadata_extraction_accuracy():
    """Test accuracy of metadata extraction and classification"""

    conn = psycopg2.connect(
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
    )
    cur = conn.cursor()

    print(f"\n📋 METADATA EXTRACTION ACCURACY TEST")
    print("=" * 80)

    # Test 1: Classification Distribution
    cur.execute(
        """
        SELECT document_type, COUNT(*) as count, AVG(classification_confidence) as avg_confidence
        FROM documents
        GROUP BY document_type
        ORDER BY count DESC;
    """
    )
    type_distribution = cur.fetchall()

    print(f"\n📊 Document Type Distribution:")
    total_docs = sum(count for _, count, _ in type_distribution)
    for doc_type, count, avg_conf in type_distribution:
        percentage = count / total_docs * 100
        print(f"   {doc_type:<20} {count:>3} docs ({percentage:>5.1f}%) - Avg Confidence: {avg_conf or 0:.2f}")

    # Test 2: Product Recognition Accuracy
    cur.execute(
        """
        SELECT product_name, product_version, COUNT(*) as count
        FROM documents
        WHERE product_name != 'unknown'
        GROUP BY product_name, product_version
        ORDER BY count DESC;
    """
    )
    product_distribution = cur.fetchall()

    print(f"\n🏷️  Product Recognition Results:")
    for product, version, count in product_distribution[:10]:
        print(f"   {product} v{version:<10} {count:>3} docs")

    # Test 3: Metadata Completeness
    cur.execute(
        """
        SELECT
            COUNT(*) as total_docs,
            COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as has_title,
            COUNT(CASE WHEN version IS NOT NULL AND version != '' THEN 1 END) as has_version,
            COUNT(CASE WHEN doc_number IS NOT NULL AND doc_number != '' THEN 1 END) as has_doc_number,
            COUNT(CASE WHEN publisher IS NOT NULL AND publisher != '' THEN 1 END) as has_publisher,
            COUNT(CASE WHEN array_length(product_family, 1) > 0 THEN 1 END) as has_product_family,
            COUNT(CASE WHEN array_length(service_lines, 1) > 0 THEN 1 END) as has_service_lines,
            COUNT(CASE WHEN array_length(audiences, 1) > 0 THEN 1 END) as has_audiences
        FROM documents;
    """
    )
    completeness = cur.fetchone()

    print(f"\n🎯 Metadata Completeness Analysis:")
    if completeness:
        total = completeness[0]
        fields = [
            ("Title", completeness[1]),
            ("Version", completeness[2]),
            ("Doc Number", completeness[3]),
            ("Publisher", completeness[4]),
            ("Product Family", completeness[5]),
            ("Service Lines", completeness[6]),
            ("Audiences", completeness[7]),
        ]

        for field_name, count in fields:
            percentage = count / total * 100
            print(f"   {field_name:<15} {count:>3}/{total} ({percentage:>5.1f}%)")

    # Test 4: Privacy Classification
    cur.execute(
        """
        SELECT privacy_level, COUNT(*) as count
        FROM documents
        GROUP BY privacy_level;
    """
    )
    privacy_distribution = cur.fetchall()

    print(f"\n🔒 Privacy Classification:")
    for privacy, count in privacy_distribution:
        percentage = count / total_docs * 100
        print(f"   {privacy:<10} {count:>3} docs ({percentage:>5.1f}%)")

    # Test 5: Sample Quality Check
    cur.execute(
        """
        SELECT file_name, document_type, product_name, product_version,
               classification_confidence, title, version
        FROM documents
        WHERE classification_confidence > 0.8
        ORDER BY classification_confidence DESC
        LIMIT 5;
    """
    )
    high_confidence_samples = cur.fetchall()

    print(f"\n⭐ High-Confidence Classification Examples:")
    for file_name, doc_type, product, version, confidence, title, extracted_version in high_confidence_samples:
        print(f"   📄 {file_name}")
        print(f"      Type: {doc_type} | Product: {product} v{version} | Confidence: {confidence:.2f}")
        print(f"      Title: {title or 'Not extracted'}")
        print(f"      Version: {extracted_version or 'Not extracted'}")

    # Calculate overall metadata quality score
    title_score = completeness[1] / total * 100
    version_score = completeness[2] / total * 100
    product_family_score = completeness[5] / total * 100
    classification_score = len([c for _, _, c in type_distribution if c and c > 0.7]) / len(type_distribution) * 100

    overall_metadata_score = (title_score + version_score + product_family_score + classification_score) / 4

    print(f"\n🏆 METADATA QUALITY SUMMARY:")
    print(f"   Title Extraction: {title_score:.1f}%")
    print(f"   Version Extraction: {version_score:.1f}%")
    print(f"   Product Family: {product_family_score:.1f}%")
    print(f"   Classification Quality: {classification_score:.1f}%")
    print(f"   📊 Overall Metadata Score: {overall_metadata_score:.1f}%")

    if overall_metadata_score >= 80:
        print(f"   🎉 EXCELLENT - Metadata extraction exceeds expectations")
    elif overall_metadata_score >= 60:
        print(f"   ✅ GOOD - Metadata extraction meets standards")
    else:
        print(f"   ⚠️  NEEDS IMPROVEMENT - Metadata extraction below standards")

    cur.close()
    conn.close()
    return overall_metadata_score


def test_vector_database_performance():
    """Test vector database performance and index efficiency"""

    conn = psycopg2.connect(
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
    )
    cur = conn.cursor()

    print(f"\n⚡ VECTOR DATABASE PERFORMANCE TEST")
    print("=" * 80)

    # Test 1: Embedding Coverage
    cur.execute(
        """
        SELECT
            COUNT(*) as total_chunks,
            COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as embedded_chunks,
            AVG(content_length) as avg_chunk_length,
            MIN(content_length) as min_chunk_length,
            MAX(content_length) as max_chunk_length
        FROM document_chunks;
    """
    )
    chunk_stats = cur.fetchone()

    print(f"📦 Chunk Statistics:")
    if chunk_stats:
        total, embedded, avg_len, min_len, max_len = chunk_stats
        coverage = embedded / total * 100 if total > 0 else 0
        print(f"   Total Chunks: {total:,}")
        print(f"   Embedded Chunks: {embedded:,} ({coverage:.1f}% coverage)")
        print(f"   Chunk Length: {avg_len:.0f} avg, {min_len}-{max_len} range")

        if coverage >= 99:
            print(f"   ✅ EXCELLENT - Near-perfect embedding coverage")
        elif coverage >= 95:
            print(f"   ✅ GOOD - High embedding coverage")
        else:
            print(f"   ⚠️  WARNING - Low embedding coverage")

    # Test 2: Index Performance
    test_query = "RNI security configuration and installation procedures"
    try:
        query_embedding = get_embedding(test_query)

        # Test query performance with EXPLAIN ANALYZE
        start_time = time.time()
        cur.execute(
            """
            EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
            SELECT dc.content, dc.embedding <=> %s::vector as distance
            FROM document_chunks dc
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> %s::vector
            LIMIT 10;
        """,
            (query_embedding, query_embedding),
        )

        explain_result = cur.fetchone()
        query_time = time.time() - start_time

        print(f"\n🔍 Query Performance Analysis:")
        print(f"   Query Time: {query_time:.3f}s")

        if explain_result and explain_result[0]:
            explain_data = explain_result[0][0]
            execution_time = explain_data.get("Execution Time", 0)
            planning_time = explain_data.get("Planning Time", 0)

            print(f"   Planning Time: {planning_time:.2f}ms")
            print(f"   Execution Time: {execution_time:.2f}ms")

            # Check if HNSW index is being used
            plan_str = json.dumps(explain_data)
            if "hnsw" in plan_str.lower():
                print(f"   ✅ HNSW Index: ACTIVE (optimal performance)")
            else:
                print(f"   ⚠️  HNSW Index: NOT DETECTED (may impact performance)")

            if execution_time < 10:  # Under 10ms is excellent
                print(f"   ⚡ Performance: EXCELLENT (sub-10ms)")
            elif execution_time < 100:  # Under 100ms is good
                print(f"   ✅ Performance: GOOD")
            else:
                print(f"   ⚠️  Performance: SLOW (over 100ms)")

    except Exception as e:
        print(f"   ❌ Performance test failed: {e}")

    # Test 3: Database Statistics
    cur.execute(
        """
        SELECT
            schemaname, tablename, attname, n_distinct, correlation
        FROM pg_stats
        WHERE tablename IN ('documents', 'document_chunks')
            AND attname IN ('document_type', 'product_name', 'embedding')
        ORDER BY tablename, attname;
    """
    )
    stats = cur.fetchall()

    print(f"\n📈 Database Statistics:")
    for schema, table, column, n_distinct, correlation in stats:
        print(f"   {table}.{column}: {n_distinct} distinct values, correlation: {correlation or 0:.3f}")

    # Test 4: Storage Efficiency
    cur.execute(
        """
        SELECT
            pg_size_pretty(pg_total_relation_size('documents')) as documents_size,
            pg_size_pretty(pg_total_relation_size('document_chunks')) as chunks_size,
            pg_size_pretty(pg_database_size(current_database())) as total_db_size;
    """
    )
    size_stats = cur.fetchone()

    print(f"\n💾 Storage Usage:")
    if size_stats:
        print(f"   Documents Table: {size_stats[0]}")
        print(f"   Chunks Table: {size_stats[1]}")
        print(f"   Total Database: {size_stats[2]}")

    cur.close()
    conn.close()


def run_comprehensive_accuracy_test():
    """Run all accuracy tests and provide overall assessment"""

    print("🧪 TECHNICAL SERVICE ASSISTANT - COMPREHENSIVE ACCURACY TEST")
    print("=" * 80)
    print(f"Test Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("Testing enhanced pgvector database with semantic search capabilities")

    # Run all test suites
    semantic_scores = test_semantic_search_accuracy()
    metadata_score = test_metadata_extraction_accuracy()
    test_vector_database_performance()

    # Calculate overall system accuracy
    avg_semantic_score = sum(semantic_scores) / len(semantic_scores) * 100
    overall_accuracy = avg_semantic_score * 0.6 + metadata_score * 0.4  # Weight semantic search higher

    print(f"\n" + "🎯" + "=" * 78)
    print(f"📊 FINAL ACCURACY ASSESSMENT")
    print(f"   Semantic Search Accuracy: {avg_semantic_score:.1f}%")
    print(f"   Metadata Extraction Score: {metadata_score:.1f}%")
    print(f"   📈 OVERALL SYSTEM ACCURACY: {overall_accuracy:.1f}%")

    if overall_accuracy >= 85:
        grade = "A+ EXCELLENT"
        assessment = "🏆 Production-ready with exceptional accuracy"
    elif overall_accuracy >= 75:
        grade = "A- VERY GOOD"
        assessment = "✅ Production-ready with high accuracy"
    elif overall_accuracy >= 65:
        grade = "B+ GOOD"
        assessment = "✅ Suitable for production with minor improvements"
    elif overall_accuracy >= 55:
        grade = "B- ACCEPTABLE"
        assessment = "⚠️  Usable but needs accuracy improvements"
    else:
        grade = "C NEEDS WORK"
        assessment = "🚨 Requires significant accuracy improvements"

    print(f"   🎓 Grade: {grade}")
    print(f"   📝 Assessment: {assessment}")
    print("=" * 80)

    return overall_accuracy


if __name__ == "__main__":
    try:
        overall_score = run_comprehensive_accuracy_test()
        exit_code = 0 if overall_score >= 70 else 1
        exit(exit_code)
    except Exception as e:
        print(f"❌ Test suite failed with error: {e}")
        exit(1)
