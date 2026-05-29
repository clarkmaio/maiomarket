#!/usr/bin/env bash
#
# Deploy di MaioMarket su uno Space (Docker) di Hugging Face con un comando.
#
# Uso:
#   ./deploy.sh <utente>/<nome-space>
#   es.  ./deploy.sh andrea/maiomarket
#
# Prerequisiti:
#   pip install huggingface_hub
#   e autenticazione, in uno dei due modi:
#     - export HF_TOKEN=hf_xxx            (token con permesso "write")
#     - oppure: huggingface-cli login     (una volta sola)
#
# Opzionale (se esportati, vengono impostati come SECRET dello Space):
#   TURSO_DATABASE_URL, TURSO_AUTH_TOKEN, SESSION_SECRET
#
set -euo pipefail

SPACE_ID="${1:-${HF_SPACE_ID:-}}"
if [ -z "$SPACE_ID" ]; then
  echo "Uso: ./deploy.sh <utente>/<nome-space>   (es. ./deploy.sh andrea/maiomarket)"
  exit 1
fi

PY="${PYTHON:-python}"

if ! "$PY" -c "import huggingface_hub" 2>/dev/null; then
  echo "Manca huggingface_hub. Installa con:  pip install huggingface_hub"
  exit 1
fi

"$PY" - "$SPACE_ID" <<'PY'
import os, sys
from huggingface_hub import HfApi
from huggingface_hub.utils import HfHubHTTPError

space_id = sys.argv[1]
token = os.environ.get("HF_TOKEN")  # se assente usa il login salvato

api = HfApi(token=token)

# 1) crea lo Space (Docker) se non esiste -- idempotente
api.create_repo(space_id, repo_type="space", space_sdk="docker", exist_ok=True)

# 2) carica i file del progetto (escludendo roba locale)
api.upload_folder(
    repo_id=space_id,
    repo_type="space",
    folder_path=".",
    commit_message="Deploy MaioMarket",
    ignore_patterns=[
        ".venv/*", "*.db", "*.db-shm", "*.db-wal",
        "__pycache__/*", "*.pyc", ".git/*", "deploy.sh",
    ],
)

# 3) se i secret sono nell'ambiente, impostali sullo Space
secrets = ["TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN", "SESSION_SECRET"]
set_any = False
for key in secrets:
    val = os.environ.get(key)
    if val:
        api.add_space_secret(space_id, key, val)
        print(f"  secret impostato: {key}")
        set_any = True
if not set_any:
    print("  (nessun secret passato via env: impostali a mano in Settings -> "
          "Variables and secrets, oppure esportali prima di rilanciare lo script)")

print(f"\n✅ Deploy fatto: https://huggingface.co/spaces/{space_id}")
PY
