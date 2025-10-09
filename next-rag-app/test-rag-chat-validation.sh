#!/bin/bash
# Automated RAG Chat validation for PDF documents in /uploads/archive
# For each PDF, ask a unique question and log the parsed answer

API_URL="http://localhost:3010/api/chat"
ARCHIVE_DIR="/home/kmccullor/Projects/Technical-Service-Assistant/uploads/archive"
LOG_FILE="rag_chat_validation_results.log"

# Sample questions for a subset of documents (expand as needed)
declare -A questions
questions["RNI 4.14 Hardware Security Module Installation Guide.pdf"]="What is the purpose of the Hardware Security Module in RNI 4.14?"
questions["RNI 4.14 Microsoft Active Directory Integration Guide.pdf"]="How do you configure Microsoft Active Directory integration in RNI 4.14?"
questions["RNI 4.14.1 Release Notes.pdf"]="What are the new features in RNI 4.14.1?"
questions["RNI 4.15 Device Manager Electric User Guide.pdf"]="How do you add a new electric device in RNI 4.15 Device Manager?"
questions["RNI 4.16 System Security User Guide.pdf"]="What are the main security features described in the RNI 4.16 System Security User Guide?"
questions["RNI 4.16.1 Release Notes.pdf"]="List the major changes in RNI 4.16.1 Release Notes."

# Clear previous log
echo "RAG Chat Validation Results - $(date)" > "$LOG_FILE"

for pdf in "${!questions[@]}"; do
  question="${questions[$pdf]}"
  echo -e "\n---\nDocument: $pdf" | tee -a "$LOG_FILE"
  echo "Question: $question" | tee -a "$LOG_FILE"
  # Query the RAG Chat endpoint and parse the streaming response for tokens
  response=$(curl -s -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":[{\"role\":\"user\",\"content\":\"$question\"}]}" )
  # Extract all 'token' fields from the SSE response
  answer=$(echo "$response" | grep '"type":"token"' | sed -E 's/.*"token":"([^"]*)".*/\1/' | tr -d '\n')
  # Extract sources and confidence
  sources=$(echo "$response" | grep '"type":"sources"' | sed -E 's/.*"sources":(\[.*\]),"confidence":([0-9.]+).*/\1/')
  confidence=$(echo "$response" | grep '"type":"sources"' | sed -E 's/.*"confidence":([0-9.]+).*/\1/')
  echo "Answer: $answer" | tee -a "$LOG_FILE"
  echo "Sources: $sources" | tee -a "$LOG_FILE"
  echo "Confidence: $confidence" | tee -a "$LOG_FILE"
done

echo -e "\nValidation complete. See $LOG_FILE for results."
