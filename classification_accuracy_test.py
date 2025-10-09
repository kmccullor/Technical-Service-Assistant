import psycopg2
import sys
sys.path.append('/app')
from config import get_settings

def test_classification_accuracy():
    """Test classification accuracy by examining specific documents"""
    
    settings = get_settings()
    conn = psycopg2.connect(
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
    )
    cur = conn.cursor()
    
    print("🎯 DETAILED CLASSIFICATION ACCURACY VALIDATION")
    print("=" * 80)
    
    # Test specific document patterns for accuracy
    test_cases = [
        {
            "pattern": "%Release Notes%",
            "expected_type": "release_notes",
            "description": "Release Notes Documents"
        },
        {
            "pattern": "%Installation Guide%",
            "expected_type": "installation_guide", 
            "description": "Installation Guide Documents"
        },
        {
            "pattern": "%User Guide%",
            "expected_type": "user_guide",
            "description": "User Guide Documents"
        },
        {
            "pattern": "%Integration Guide%",
            "expected_type": "integration_guide",
            "description": "Integration Guide Documents"
        },
        {
            "pattern": "%Security%",
            "expected_type": "security_guide",
            "description": "Security Guide Documents"
        },
        {
            "pattern": "%Reference Manual%",
            "expected_type": "reference_manual",
            "description": "Reference Manual Documents"
        }
    ]
    
    total_correct = 0
    total_documents = 0
    
    for test_case in test_cases:
        cur.execute("""
            SELECT file_name, document_type, classification_confidence, product_name, product_version
            FROM documents 
            WHERE file_name ILIKE %s
            ORDER BY classification_confidence DESC;
        """, (test_case["pattern"],))
        
        results = cur.fetchall()
        
        if not results:
            continue
            
        print(f"\n📋 {test_case['description']} ({len(results)} documents)")
        print("-" * 60)
        
        correct_classifications = 0
        for file_name, doc_type, confidence, product, version in results:
            is_correct = doc_type == test_case["expected_type"]
            total_documents += 1
            
            if is_correct:
                correct_classifications += 1
                total_correct += 1
                status = "✅"
            else:
                status = "❌"
            
            print(f"  {status} {file_name}")
            print(f"      Classified as: {doc_type} (expected: {test_case['expected_type']})")
            print(f"      Product: {product} v{version} | Confidence: {confidence:.2f}")
        
        accuracy = correct_classifications / len(results) * 100 if results else 0
        print(f"\n  📊 Category Accuracy: {correct_classifications}/{len(results)} ({accuracy:.1f}%)")
    
    # Overall classification accuracy
    overall_accuracy = total_correct / total_documents * 100 if total_documents > 0 else 0
    
    print(f"\n" + "=" * 80)
    print(f"🏆 OVERALL CLASSIFICATION ACCURACY")
    print(f"   Correct Classifications: {total_correct}/{total_documents}")
    print(f"   📈 Overall Accuracy: {overall_accuracy:.1f}%")
    
    if overall_accuracy >= 90:
        print(f"   🎉 EXCELLENT - Classification exceeds expectations")
    elif overall_accuracy >= 80:
        print(f"   ✅ VERY GOOD - Classification meets high standards")
    elif overall_accuracy >= 70:
        print(f"   ✅ GOOD - Classification meets standards")
    else:
        print(f"   ⚠️  NEEDS IMPROVEMENT - Classification below standards")
    
    # Check for misclassifications
    print(f"\n🔍 MISCLASSIFICATION ANALYSIS")
    cur.execute("""
        SELECT file_name, document_type, classification_confidence
        FROM documents 
        WHERE (
            (file_name ILIKE '%Release Notes%' AND document_type != 'release_notes') OR
            (file_name ILIKE '%Installation Guide%' AND document_type != 'installation_guide') OR
            (file_name ILIKE '%User Guide%' AND document_type != 'user_guide') OR
            (file_name ILIKE '%Integration Guide%' AND document_type != 'integration_guide') OR
            (file_name ILIKE '%Security%' AND document_type != 'security_guide') OR
            (file_name ILIKE '%Reference Manual%' AND document_type != 'reference_manual')
        )
        ORDER BY classification_confidence DESC;
    """)
    
    misclassifications = cur.fetchall()
    
    if misclassifications:
        print(f"   Found {len(misclassifications)} misclassifications:")
        for file_name, doc_type, confidence in misclassifications:
            print(f"   ❌ {file_name}")
            print(f"      Incorrectly classified as: {doc_type} (confidence: {confidence:.2f})")
    else:
        print(f"   ✅ No obvious misclassifications found!")
    
    cur.close()
    conn.close()
    
    return overall_accuracy

if __name__ == "__main__":
    accuracy = test_classification_accuracy()
    print(f"\nFinal Classification Accuracy: {accuracy:.1f}%")