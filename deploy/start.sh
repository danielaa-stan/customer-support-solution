#!/usr/bin/env bash
# Container entry point: build the RAG index in the background (first start only), then serve the UI.
# The index build logs to stdout, so it is visible in the hosting provider's logs.
set -euo pipefail
cd /app

build_index_with_retries() {
  for attempt in 1 2 3; do
    echo "[start] Building RAG index (attempt ${attempt}/3, provider: ${RAG_EMBEDDING_PROVIDER:-from settings.toml})..."
    if python -m agent.scripts.build_index; then
      echo "[start] RAG index ready. New chats use search_policy and find_similar_cases."
      return 0
    fi
    echo "[start] RAG index build failed, retrying in 60s."
    sleep 60
  done
  echo "[start] RAG index could not be built; the agent runs without RAG."
}

if [ ! -f runtime/rag/manifest.json ]; then
  build_index_with_retries &
fi

exec streamlit run agent/ui/app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-8501}" \
  --server.headless=true \
  --browser.gatherUsageStats=false
