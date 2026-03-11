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

# Download Nunito Bold font from Google Fonts (ensures a valid binary)
RUN mkdir -p static/fonts && \
    FONT_URL=$(curl -sf -A "Mozilla/5.0" \
        "https://fonts.googleapis.com/css2?family=Nunito:wght@700" | \
        grep -o 'https://fonts\.gstatic\.com[^)]*\.ttf' | head -1) && \
    curl -L --fail -o static/fonts/Nunito-Bold.ttf "$FONT_URL"

# Download the background video from GitHub LFS at build time
RUN mkdir -p static/assets && \
    curl -L --fail -o static/assets/cs.mp4 \
    "https://media.githubusercontent.com/media/kmjson/RedditParkour/main/static/assets/cs.mp4"

EXPOSE 8080

CMD gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 120
