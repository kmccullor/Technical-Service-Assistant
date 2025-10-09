#!/usr/bin/env npx tsx

import { db } from '../lib/db'
import { documentChunks, documents } from '../lib/db/schema'
import { sql } from 'drizzle-orm'

async function testRAG() {
  console.log('🔍 Testing RAG system with existing data...\n')

  try {
    // Test 1: Check document count
    const docCount = await db.select({ count: sql<number>`count(*)::int` }).from(documents)
    console.log(`📄 Documents in database: ${docCount[0].count}`)

    // Test 2: Check chunk count  
    const chunkCount = await db.select({ count: sql<number>`count(*)::int` }).from(documentChunks)
    console.log(`📝 Chunks in database: ${chunkCount[0].count}`)

    // Test 3: Sample document titles
    const sampleDocs = await db
      .select({ id: documents.id, fileName: documents.fileName, title: documents.title })
      .from(documents)
      .limit(5)
    
    console.log('\n📋 Sample documents:')
    sampleDocs.forEach(doc => {
      console.log(`  ${doc.id}: ${doc.fileName || doc.title || 'Untitled'}`)
    })

    // Test 4: Sample chunks with embeddings
    const chunksWithEmbeddings = await db
      .select({ 
        count: sql<number>`count(*)::int`
      })
      .from(documentChunks)
      .where(sql`embedding IS NOT NULL`)
    
    console.log(`\n🔢 Chunks with embeddings: ${chunksWithEmbeddings[0].count}`)

    // Test 5: Sample chunk content
    const sampleChunks = await db
      .select({ 
        id: documentChunks.id,
        content: sql<string>`LEFT(content, 100)`,
        pageNumber: documentChunks.pageNumber,
        chunkType: documentChunks.chunkType
      })
      .from(documentChunks)
      .limit(3)

    console.log('\n📖 Sample chunk content:')
    sampleChunks.forEach(chunk => {
      console.log(`  Chunk ${chunk.id} (Page ${chunk.pageNumber}, Type: ${chunk.chunkType}):`)
      console.log(`    ${chunk.content}...`)
    })

    console.log('\n✅ RAG system database connection successful!')
    console.log('\n🎯 Next steps:')
    console.log('  1. Update OPENAI_API_KEY in .env.local with your actual API key')
    console.log('  2. Open http://localhost:3000 to test the chat interface')
    console.log('  3. Try searching for technical terms from your documents')
    console.log('  4. The hybrid search will use both vector similarity and lexical matching')

  } catch (error) {
    console.error('❌ Error testing RAG system:', error)
  }
}

if (require.main === module) {
  testRAG()
}