# Deploy: Hugging Face Space (Docker) + Turso

Obiettivo: app online gratis e **database che non si perde** quando lo Space va
in sleep / si riavvia. Lo storage dello Space è effimero, quindi i dati vivono
su **Turso** (SQLite gestito); l'app ne tiene una *embedded replica* locale che
sincronizza a ogni avvio e dopo ogni scrittura.

## 1. Crea il database su Turso

1. Registrati su <https://turso.tech> (free tier, senza carta).
2. Installa la CLI e crea il DB:
   ```bash
   curl -sSfL https://get.tur.so/install.sh | bash
   turso auth signup
   turso db create maiomarket
   ```
3. Prendi i due valori che ti serviranno come secret:
   ```bash
   turso db show maiomarket --url        # -> TURSO_DATABASE_URL (libsql://...)
   turso db tokens create maiomarket     # -> TURSO_AUTH_TOKEN
   ```

> Lo schema delle tabelle viene creato in automatico dall'app al primo avvio
> (`db.init_db`), non devi fare migrazioni a mano.

## 2. Deploy con un comando (consigliato)

Dopo aver creato il DB Turso (passo 1) e aver fatto login a HF:

```bash
pip install huggingface_hub
export HF_TOKEN=hf_xxx                 # token con permesso "write"
# opzionale: passa anche i secret, verranno impostati sullo Space
export TURSO_DATABASE_URL="libsql://..."
export TURSO_AUTH_TOKEN="..."
export SESSION_SECRET="una-stringa-lunga-e-casuale"

./deploy.sh clarkmaio/maiomarket
```

Lo script crea lo Space (Docker) se non esiste, carica i file ed eventualmente
imposta i secret. Per gli aggiornamenti successivi basta rilanciare lo stesso
comando.

I passi 3–5 qui sotto descrivono la procedura **manuale** equivalente, se
preferisci usare la web UI.

## 3. Crea lo Space su Hugging Face (manuale)

1. Su <https://huggingface.co/new-space>: **SDK = Docker**, visibilità a scelta.
   - ⚠️ Il repo dello Space conterrà `config.yaml` con utenti/password in chiaro:
     se è un problema, rendi lo Space **privato**.
2. Carica i file del progetto nel repo dello Space (via web UI o git):
   `app.py`, `db.py`, `market.py`, `config.yaml`, `requirements.txt`,
   `Dockerfile`, `README.md`.

## 4. Imposta i secret dello Space (manuale)

In *Settings → Variables and secrets* aggiungi (come **Secrets**):

| Nome                  | Valore                                  |
|-----------------------|-----------------------------------------|
| `TURSO_DATABASE_URL`  | l'URL `libsql://...` del passo 1         |
| `TURSO_AUTH_TOKEN`    | il token del passo 1                     |
| `SESSION_SECRET`      | una stringa lunga e casuale             |

Senza `TURSO_DATABASE_URL` l'app ripiega su SQLite locale (utile in dev, ma sullo
Space i dati andrebbero persi).

## 5. Build & run

Lo Space builda il `Dockerfile` ed espone la porta `7860` (vedi `app_port` nel
`README.md`). Al primo avvio l'app crea le tabelle su Turso e semina i mercati di
`config.yaml`. A ogni riavvio i dati vengono ripristinati da Turso.

## Come funziona la persistenza (in breve)

- `db.py` usa `libsql.connect(DB_PATH, sync_url=..., auth_token=...)`.
- **Cold start**: `sync()` fa il *pull* dello stato da Turso nel file locale.
- **Dopo ogni commit**: `sync()` fa il *push* delle scritture su Turso.
- Quindi anche se il container viene distrutto, lo stato resta su Turso.

## Note / limiti

- Pensato per **un solo container** (free tier HF). Con più repliche
  concorrenti le scritture non si vedrebbero tra loro senza un pull esplicito.
- ⚠️ **Da validare con le tue credenziali**: il percorso Turso non è stato
  testato in questo ambiente (manca un'istanza Turso reale). Il percorso SQLite
  locale è invece testato. Se l'API del pacchetto `libsql` fosse cambiata,
  l'unico punto da adattare è la funzione `_raw_connect()` in `db.py`.
- I piani gratuiti (HF, Turso) cambiano spesso: verifica i limiti correnti.
