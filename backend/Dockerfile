FROM python:3.13-slim

# Installer FFmpeg et gcc (pour certaines dépendances Python)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail
WORKDIR /app

# Copier et installer les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le code
COPY . .

# Créer les dossiers nécessaires
RUN mkdir -p staticfiles media logs

# Collecter les fichiers statiques
RUN python manage.py collectstatic --noinput

# Port Render
ENV PORT=8000
EXPOSE 8000

# Démarrer avec Gunicorn
CMD gunicorn wsgi:application --bind 0.0.0.0:$PORT --workers 4 --timeout 60
