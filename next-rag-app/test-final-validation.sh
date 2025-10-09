#!/bin/bash
# Quick RAG Chat validation for key PDF documents
API_URL="http://localhost:3010/api/chat"
LOG_FILE="rag_final_validation.log"

echo "RAG Chat Final Validation - $(date)" > "$LOG_FILE"

# Test 3 key questions
questions=(
  "What is the Hardware Security Module in RNI?"
  "How do you configure Active Directory integration?"
  "What are the system requirements for RNI installation?"
)

for question in "${questions[@]}"; do
  echo -e "\n---\nQuestion: $question" | tee -a "$LOG_FILE"
  
  # Get streaming response and parse for answer tokens
  response=$(timeout 30 curl -s -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":[{\"role\":\"user\",\"content\":\"$question\"}]}")
  
  # Extract answer, sources, and confidence
  answer=$(echo "$response" | grep '"type":"token"' | sed -E 's/.*"token":"([^"]*)".*/\1/' | tr -d '\n' | head -c 200)
  confidence=$(echo "$response" | grep '"type":"sources"' | sed -E 's/.*"confidence":([0-9.]+).*/\1/' | head -1)
  
  echo "Answer: $answer..." | tee -a "$LOG_FILE"
  echo "Confidence: $confidence" | tee -a "$LOG_FILE"
  echo "Status: $(if [ -n "$answer" ] && [ -n "$confidence" ]; then echo 'SUCCESS ✅'; else echo 'PARTIAL'; fi)" | tee -a "$LOG_FILE"
done

echo -e "\nValidation complete. See $LOG_FILE for results." | tee -a "$LOG_FILE"