# Use Node.js 23 slim as base image
FROM node:23-slim

# Update package lists
RUN apt-get update

# Install basic system dependencies
RUN apt-get install -y \
    curl \
    wget \
    gnupg \
    ca-certificates \
    lsb-release

# Install Python and Java
RUN apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    openjdk-17-jre-headless

# Install Playwright system dependencies
RUN apt-get install -y \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0

# Install additional X11 and graphics libraries
RUN apt-get install -y \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    libu2f-udev \
    libvulkan1

# Clean up apt cache
RUN rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME environment variable
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="$JAVA_HOME/bin:$PATH"

# Install pnpm
RUN npm install -g pnpm@latest

# Create a symlink for python
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Create virtual environment and install Python dependencies
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy project files
COPY . .

# Expose port for Streamlit (default 8501)
EXPOSE 8501
EXPOSE 8502

# Install Allure via npm
RUN npm install -g allure-commandline

# Create directories for reports
RUN mkdir -p /app/allure-results /app/allure-reports

# Run Streamlit app
CMD ["streamlit", "run", "main.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
