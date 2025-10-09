#!/usr/bin/env tsx

import { db } from '../lib/db'
import { documents, documentChunks } from '../lib/db/schema'
import { generateEmbeddings } from '../lib/rag/embeddings'
import { chunkText } from '../lib/rag/chunking'

const SAMPLE_DOCUMENTS = [
  {
    title: 'Introduction to RAG',
    source: 'sample-doc-1.md',
    content: `# Introduction to Retrieval Augmented Generation (RAG)

RAG is a powerful technique that combines the benefits of large language models with external knowledge sources. By retrieving relevant documents and using them as context for generation, RAG systems can provide more accurate and up-to-date responses.

## Key Components

1. **Document Store**: A collection of documents that serve as the knowledge base
2. **Embedding Model**: Converts text into dense vector representations
3. **Retrieval System**: Finds relevant documents based on query similarity
4. **Language Model**: Generates responses using retrieved context

## Benefits

- More accurate responses grounded in factual information
- Ability to work with up-to-date information
- Reduced hallucination compared to pure generative models
- Transparent source attribution

RAG has become essential for building reliable AI applications that need to work with domain-specific knowledge.`
  },
  {
    title: 'Next.js Development Guide',
    source: 'nextjs-guide.md',
    content: `# Next.js Development Best Practices

Next.js is a React framework that provides a great developer experience with features like server-side rendering, API routes, and automatic code splitting.

## App Router

The new App Router in Next.js 14 introduces:

- **Layouts**: Shared UI between routes
- **Pages**: Route-specific UI
- **Loading UI**: Instant loading states
- **Error UI**: Error handling components
- **Not Found UI**: 404 pages

## Server Components

Server Components run on the server and can:
- Fetch data directly
- Access backend resources
- Keep sensitive information secure
- Reduce client-side JavaScript

## API Routes

Create API endpoints using:
- Route handlers in the app directory
- Edge runtime for better performance
- Type-safe responses with TypeScript

## Performance Optimization

- Use Image component for optimized images
- Implement proper caching strategies
- Utilize static generation where possible
- Monitor Core Web Vitals`
  },
  {
    title: 'Database Design Patterns',
    source: 'database-patterns.md',
    content: `# Database Design Patterns for Modern Applications

Proper database design is crucial for scalable applications. Here are key patterns and considerations.

## Schema Design

### Normalization vs Denormalization
- **Normalization**: Reduces data redundancy, good for OLTP
- **Denormalization**: Improves read performance, good for OLAP

### Indexing Strategies
- Primary indexes for unique identification
- Secondary indexes for common queries
- Composite indexes for multi-column searches
- Partial indexes for filtered data

## Vector Databases

With the rise of AI applications, vector databases have become important:

### pgvector Extension
- Adds vector similarity search to PostgreSQL
- Supports different distance metrics (cosine, euclidean, inner product)
- HNSW and IVFFlat index types for performance

### Use Cases
- Semantic search in documents
- Recommendation systems
- Image and audio similarity
- RAG applications

## Performance Considerations

- Connection pooling for scalability
- Query optimization and EXPLAIN analysis
- Proper data types and constraints
- Regular maintenance and statistics updates`
  }
]

async function seedDatabase() {
  console.log('🌱 Starting database seeding...')
  
  try {
    // Insert sample documents
    for (const doc of SAMPLE_DOCUMENTS) {
      console.log(`📄 Processing document: ${doc.title}`)
      
      // Insert document
      const [insertedDoc] = await db.insert(documents).values({
        fileName: doc.title,
        title: doc.title,
        fileHash: `hash-${doc.title.replace(/\s+/g, '-').toLowerCase()}`,
        fileSize: doc.content.length,
        mimeType: 'application/pdf',
        processedAt: new Date()
      }).returning()

      // Create chunks from content
      const chunks = chunkText(doc.content)
      
      // Generate embeddings for chunks
      const embeddings = await generateEmbeddings(chunks.map(c => c.content))
      
      // Insert chunks for this document
      const chunkInserts = chunks.map((chunk, index) => ({
        documentId: insertedDoc.id,
        chunkIndex: index,
        pageNumber: Math.floor(index / 5) + 1,
        content: chunk.content,
        contentHash: `chunk-${insertedDoc.id}-${index}`,
        contentLength: chunk.content.length,
        embedding: embeddings[index]
      }))

      await db.insert(documentChunks).values(chunkInserts)
      console.log(`✅ Inserted ${chunkInserts.length} chunks for ${doc.title}`)
    }

    console.log('🎉 Database seeding completed successfully!')
  } catch (error) {
    console.error('❌ Seeding failed:', error)
    process.exit(1)
  }
}

seedDatabase()