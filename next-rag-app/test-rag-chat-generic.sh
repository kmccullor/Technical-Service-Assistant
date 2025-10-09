#!/bin/bash
# Quick generic RAG Chat validation
API_URL="http://localhost:8080/api/chat"
LOG_FILE="rag_chat_generic_test.log"

echo "RAG Chat Generic Test - $(date)" > "$LOG_FILE"

questions=(
  "What is RNI system?"
  "How do I install RNI?"
  "What is the Hardware Security Module?"
  "What is Active Directory integration?"
  "What are the new features in the latest release?"
)

for question in "${questions[@]}"; do
  echo -e "\n---\nQuestion: $question" | tee -a "$LOG_FILE"
  response=$(curl -s -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":[{\"role\":\"user\",\"content\":\"$question\"}]}" )
  answer=$(echo "$response" | grep '"type":"token"' | sed -E 's/.*"token":"([^"]*)".*/\1/' | tr -d '\n')
  sources=$(echo "$response" | grep '"type":"sources"' | sed -E 's/.*"sources":(\[.*\]),"confidence":([0-9.]+).*/\1/')
  confidence=$(echo "$response" | grep '"type":"sources"' | sed -E 's/.*"confidence":([0-9.]+).*/\1/')
  echo "Answer: $answer" | tee -a "$LOG_FILE"
  echo "Sources: $sources" | tee -a "$LOG_FILE"
  echo "Confidence: $confidence" | tee -a "$LOG_FILE"
done

echo -e "\nGeneric test complete. See $LOG_FILE for results."
