#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${PLAYWRIGHT_BASE_URL:-https://rni-llm-01.lab.sensus.net}"
API_KEY="${PLAYWRIGHT_API_KEY:-}"
BEARER_TOKEN="${PLAYWRIGHT_BEARER_TOKEN:-}"

cat <<'DOCKERFILE' > next-rag-app/playwright.dockerfile
FROM mcr.microsoft.com/playwright:v1.42.1-jammy
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .
CMD ["npx", "playwright", "test", "--config=playwright.config.ts"]
DOCKERFILE

pushd next-rag-app >/dev/null
PLAYWRIGHT_BASE_URL="$BASE_URL" PLAYWRIGHT_API_KEY="$API_KEY" PLAYWRIGHT_BEARER_TOKEN="$BEARER_TOKEN" \
  docker build -f playwright.dockerfile -t tsa-playwright-perf .
PLAYWRIGHT_BASE_URL="$BASE_URL" PLAYWRIGHT_API_KEY="$API_KEY" PLAYWRIGHT_BEARER_TOKEN="$BEARER_TOKEN" \
  docker run --rm \
    -e PLAYWRIGHT_BASE_URL \
    -e PLAYWRIGHT_API_KEY \
    -e PLAYWRIGHT_BEARER_TOKEN \
    -v "$(pwd)/playwright-report:/app/playwright-report" \
    tsa-playwright-perf
popd >/dev/null
