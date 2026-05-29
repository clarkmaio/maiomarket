---
title: MaioMarket
emoji: 📈
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# MaioMarket

Prediction market goliardico in stile Polymarket, scritto in
[FastHTML](https://fastht.ml).

## Eseguire in locale

```bash
pip install -r requirements.txt
python app.py          # http://localhost:5001
```

## Deploy su Hugging Face Spaces + Turso

Vedi [DEPLOY.md](DEPLOY.md) per la procedura passo-passo. In sintesi:

- Lo Space è di tipo **Docker** (porta `7860`).
- Il database persiste su **Turso/libSQL**: imposta i secret
  `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` e `SESSION_SECRET` nelle
  *Settings → Variables and secrets* dello Space.
- Senza quelle env l'app usa SQLite locale (comodo per lo sviluppo).
