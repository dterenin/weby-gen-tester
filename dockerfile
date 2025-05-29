# Build stage
FROM node:23-alpine AS builder
WORKDIR /app
RUN npm install -g pnpm@latest

# Runtime stage
FROM python:3.11-alpine

# Copy Node.js from builder
COPY --from=builder /usr/local/bin/node /usr/local/bin/
COPY --from=builder /usr/local/bin/npm /usr/local/bin/
COPY --from=builder /usr/local/bin/pnpm /usr/local/bin/
COPY --from=builder /usr/local/lib/node_modules /usr/local/lib/node_modules

# Install system dependencies
RUN apk add --no-cache \
    ffmpeg \
    chromium \
    nss \
    freetype \
    harfbuzz \
    ca-certificates \
    ttf-freefont

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy project files
COPY . .

# Expose port
EXPOSE 5000

# Run the application
CMD ["python3", "main.py"]