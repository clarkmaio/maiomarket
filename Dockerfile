FROM python:3.12-slim

# HF Spaces gira come utente non-root (uid 1000): scriviamo i file dell'app
# in una home scrivibile.
RUN useradd -m -u 1000 user
WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

USER user

# Porta attesa da Hugging Face Spaces (vedi app_port nel README.md).
ENV PORT=7860
# L'embedded replica di Turso vive qui (filesystem effimero: viene
# ri-sincronizzato da Turso a ogni cold start).
ENV MAIOMARKET_DB=/app/maiomarket.db

EXPOSE 7860
CMD ["python", "app.py"]
