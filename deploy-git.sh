#!/usr/bin/env bash
#
# Deploy di MaioMarket su uno Space di Hugging Face via git puro
# (alternativa a deploy.sh, NON richiede huggingface_hub).
#
# Uso:
#   export HF_TOKEN=hf_xxx                 # token con permesso "write"
#   ./deploy-git.sh <utente>/<nome-space>  # es. ./deploy-git.sh clarkmaio/maiomarket
#
# Variabili opzionali:
#   HF_USER   utente da usare nell'autenticazione (default: la parte prima di "/")
#
# NOTA: lo Space deve gia' esistere (git push non lo crea). Crealo una volta da
#       https://huggingface.co/new-space  scegliendo SDK = Docker, oppure usa
#       ./deploy.sh che lo crea da solo. I secret (TURSO_*, SESSION_SECRET) vanno
#       impostati in Settings -> Variables and secrets dello Space.
#
set -euo pipefail

SPACE_ID="${1:-${HF_SPACE_ID:-}}"
if [ -z "$SPACE_ID" ]; then
  echo "Uso: ./deploy-git.sh <utente>/<nome-space>   (es. ./deploy-git.sh clarkmaio/maiomarket)"
  exit 1
fi
if [ -z "${HF_TOKEN:-}" ]; then
  echo "Manca HF_TOKEN. Esegui:  export HF_TOKEN=hf_xxx"
  exit 1
fi

HF_USER="${HF_USER:-${SPACE_ID%%/*}}"

STAGE="$(mktemp -d)"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

# Copia i file del progetto escludendo roba locale.
tar \
  --exclude='./.venv' \
  --exclude='./.git' \
  --exclude='*.db' --exclude='*.db-shm' --exclude='*.db-wal' \
  --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='./deploy-git.sh' \
  -cf - . | tar -xf - -C "$STAGE"

cd "$STAGE"
git init -q
git checkout -q -b main 2>/dev/null || git checkout -q main
git add .
git -c user.email=deploy@local -c user.name=deploy commit -qm "Deploy MaioMarket"
git push -f "https://${HF_USER}:${HF_TOKEN}@huggingface.co/spaces/${SPACE_ID}.git" main

printf '\n✅ Deploy fatto: https://huggingface.co/spaces/%s\n' "$SPACE_ID"
