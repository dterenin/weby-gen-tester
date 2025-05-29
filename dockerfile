# Use Ubuntu base image and install Node.js manually
FROM ubuntu:22.04

# Install Node.js, npm, and other dependencies
RUN apt-get update && apt-get install -y \
    curl \
    python3 \
    python3-pip \
    ffmpeg \
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

# Install Node.js 23.x (latest)
RUN curl -fsSL https://deb.nodesource.com/setup_23.x | bash - \
    && apt-get install -y nodejs

# Install pnpm globally
RUN npm install -g pnpm@latest

# Verify installations
RUN node --version && npm --version && pnpm --version && python3 --version

# Set working directory inside the container
WORKDIR /app

# Copy Python requirements and install them
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium firefox webkit

# Copy all project files
COPY . .

# Make sure all binaries are accessible
ENV PATH=/usr/local/bin:/usr/bin:/bin:$PATH

# Expose port for Flask app
EXPOSE 5000

# Command to run the application
CMD ["python3", "main.py"]