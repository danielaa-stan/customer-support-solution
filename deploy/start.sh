#!/usr/bin/env bash
# Container entry point: build the RAG index in the background (first start only), then serve the UI.
set -euo pipefail
cd /app

if [ ! -f runtime/rag/manifest.json ]; then
  echo "RAG index not found: building it in the background (about 3 minutes on the Gemini free tier)."
  python -m agent.scripts.build_index > runtime-build-index.log 2>&1 &
fi

exec streamlit run agent/ui/app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-8501}" \
  --server.headless=true \
  --browser.gatherUsageStats=false
