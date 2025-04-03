# Utiliser une image Python légère
FROM python:3.12-alpine

# Installer les dépendances système nécessaires (curl, Chromium, etc.)
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    curl \
    bash \
    gcc \
    musl-dev \
    py3-pip \
    ffmpeg

# Ajouter les options pour que Chromium fonctionne sans interface graphique
ENV CHROMIUM_FLAGS="--headless --no-sandbox --disable-dev-shm-usage"

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Copier les fichiers de votre script dans le conteneur
COPY . /app

# Installer les dépendances Python spécifiées dans requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Exposer le port si nécessaire (facultatif)
EXPOSE 8080

# Commande par défaut pour exécuter le script
CMD ["python3", "automate.py"]
