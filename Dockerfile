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
# L'embedded replica di Turso (file locale + file temporanei di sync) vive in
# una dir sempre scrivibile a runtime. La persistenza vera e' su Turso, quindi
# va bene un percorso effimero come /tmp.
ENV MAIOMARKET_DB=/tmp/maiomarket.db

EXPOSE 7860
CMD ["python", "app.py"]
