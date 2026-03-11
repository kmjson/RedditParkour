FROM python:3.12-slim

# ffmpeg (with libass for subtitle burning) + curl for LFS download
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Download the background video from GitHub LFS at build time
RUN mkdir -p static/assets && \
    curl -L --fail -o static/assets/cs.mp4 \
    "https://media.githubusercontent.com/media/kmjson/RedditParkour/main/static/assets/cs.mp4"

EXPOSE 8080

CMD gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 120
