import psycopg2
import requests
import sys
sys.path.append('/app')
from config import get_settings

settings = get_settings()

def get_embedding(text: str) -> list:
    """Get embedding from Ollama"""
    try:
        response = requests.post(
            "http://ollama-server-1:11434/api/embeddings",
            json={"model": "nomic-embed-text:v1.5", "prompt": text},
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("embedding")
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None

def test_vector_search():
    """Test the enhanced vector search capabilities"""
    try:
        # Connect to database
        conn = psycopg2.connect(
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            host=settings.db_host,
            port=settings.db_port,
        )
        cur = conn.cursor()
        
        # Test query
        query = "How to install RNI security features?"
        print(f"Testing vector search for: '{query}'")
        
        # Get embedding for query
        query_embedding = get_embedding(query)
        if not query_embedding:
            print("Failed to get query embedding")
            return
            
        print(f"Query embedding dimensions: {len(query_embedding)}")
        
        # Perform vector similarity search
        cur.execute("""
            SELECT 
                d.file_name,
                d.document_type,
                d.product_name,
                d.product_version,
                dc.content,
                dc.embedding <=> %s::vector as distance
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> %s::vector
            LIMIT 5;
        """, (query_embedding, query_embedding))
        
        results = cur.fetchall()
        
        print(f"\nTop 5 search results:")
        print("=" * 80)
        
        for i, (file_name, doc_type, product, version, content, distance) in enumerate(results, 1):
            print(f"\n{i}. {file_name}")
            print(f"   Type: {doc_type} | Product: {product} {version}")
            print(f"   Distance: {distance:.4f}")
            print(f"   Content: {content[:200]}...")
            print("-" * 80)
        
        # Get database statistics
        cur.execute("""
            SELECT 
                COUNT(*) as total_docs,
                COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed
            FROM documents;
        """)
        doc_stats = cur.fetchone()
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_chunks,
                COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as embedded,
                AVG(content_length) as avg_length
            FROM document_chunks;
        """)
        chunk_stats = cur.fetchone()
        
        print(f"\n📊 Database Statistics:")
        print(f"Documents: {doc_stats[0]} total, {doc_stats[1]} completed, {doc_stats[2]} failed")
        print(f"Chunks: {chunk_stats[0]} total, {chunk_stats[1]} with embeddings ({chunk_stats[1]/chunk_stats[0]*100:.1f}%)")
        print(f"Average chunk length: {chunk_stats[2]:.0f} characters")
        
        # Check index usage
        cur.execute("""
            EXPLAIN (ANALYZE, BUFFERS) 
            SELECT dc.content, dc.embedding <=> %s::vector as distance
            FROM document_chunks dc
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> %s::vector
            LIMIT 5;
        """, (query_embedding, query_embedding))
        
        explain_results = cur.fetchall()
        print(f"\n🔍 Query Execution Plan:")
        for row in explain_results:
            print(f"   {row[0]}")
        
        cur.close()
        conn.close()
        print(f"\n✅ Vector search test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error in vector search test: {e}")

if __name__ == "__main__":
    test_vector_search()