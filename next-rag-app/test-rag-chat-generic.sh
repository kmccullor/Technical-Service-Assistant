#!/bin/bash
# Quick generic RAG Chat validation
API_URL="${API_URL:-http://localhost:3000/api/chat}"
LOG_FILE="rag_chat_generic_test.log"
AUTH_TOKEN="${AUTH_TOKEN:-}"

echo "RAG Chat Generic Test - $(date)" > "$LOG_FILE"

questions=(
  "What is RNI system?"
  "How do I install RNI?"
  "What is the Hardware Security Module?"
  "What is Active Directory integration?"
  "What are the new features in the latest release?"
)

headers=(-H "Content-Type: application/json")
if [ -n "$AUTH_TOKEN" ]; then
  headers+=(-H "Authorization: Bearer $AUTH_TOKEN")
fi

for question in "${questions[@]}"; do
  echo -e "\n---\nQuestion: $question" | tee -a "$LOG_FILE"
  payload=$(printf '{"message":"%s"}' "$question")

  response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
    "${headers[@]}" \
    -d "$payload")

  http_status="${response##*$'\n'}"
  body="${response%$'\n'*}"

  if [ "$http_status" != "200" ]; then
    echo "HTTP $http_status from $API_URL" | tee -a "$LOG_FILE"
    echo "Raw body: $body" | tee -a "$LOG_FILE"
    continue
  fi

  answer=$(echo "$body" | grep '"type":"token"' | sed -E 's/.*"token":"([^"]*)".*/\1/' | tr -d '\n')
  sources=$(echo "$body" | grep '"type":"sources"' | sed -E 's/.*"sources":(\[.*\]),"confidence":([0-9.]+).*/\1/')
  confidence=$(echo "$body" | grep '"type":"sources"' | sed -E 's/.*"confidence":([0-9.]+).*/\1/')
  echo "HTTP $http_status" | tee -a "$LOG_FILE"
  echo "Answer: $answer" | tee -a "$LOG_FILE"
  echo "Sources: $sources" | tee -a "$LOG_FILE"
  echo "Confidence: $confidence" | tee -a "$LOG_FILE"
done

echo -e "\nGeneric test complete. See $LOG_FILE for results."
