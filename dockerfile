# Use a base image that includes Node.js and Python
FROM node:20-bullseye-slim

# Install Python and its dependencies (needed for playwright, pytest, requests)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    # Install FFmpeg for video conversion to GIF
    ffmpeg \
    # Dependencies for Playwright browsers (e.g., Chrome/Chromium)
    libnss3 \
    libfontconfig1 \
    libgbm-dev \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libasound2 \
    libcups2 \
    libnspr4 \
    libxkbcommon0 \
    libxrandr2 \
    libxi6 \
    libglib2.0-0 \
    libdbus-1-3 \
    && rm -rf /var/lib/apt/lists/*

# Install pnpm globally
RUN npm install -g pnpm@latest

# Set working directory inside the container
WORKDIR /app

# Copy Python requirements and install them
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Install Playwright browsers (important: do this AFTER python deps)
# This will install Chromium, Firefox, and WebKit within the container
RUN playwright install --with-deps chromium firefox webkit

# Ensure npm cache is clean and global packages are not installed globally
ENV NPM_CONFIG_PREFIX=/usr/local/.npm-global
ENV PATH=$PATH:$NPM_CONFIG_PREFIX/bin

# Set up a non-root user for security best practices
ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID appuser && useradd -u $UID -g $GID -m appuser
USER appuser

# Copy all project files
COPY --chown=appuser:appuser . .

# Command to keep the container running for debugging if needed, or just exit
CMD ["python3", "main.py"]