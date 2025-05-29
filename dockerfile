# Use Node.js 20 with Debian Bullseye slim as base image
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

# Copy all project files
COPY . .

# Make sure node and pnpm are in PATH for all users
ENV PATH=/usr/local/bin:$PATH

# Expose port for Flask app
EXPOSE 5000

# Command to keep the container running for debugging if needed, or just exit
CMD ["python3", "main.py"]