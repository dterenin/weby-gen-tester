#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define Docker image name
IMAGE_NAME="nextjs-tester-image"
CONTAINER_NAME="nextjs-tester-container"

# Build the Docker image (only if it doesn't exist or needs rebuilding)
echo "Building Docker image $IMAGE_NAME..."
docker build -t "$IMAGE_NAME" .

# Ensure the allure-results directory exists on the host
mkdir -p allure-results

# Define your pytest arguments (e.g., --csv-output-field="...")
# Pass all arguments from the script to pytest
PYTEST_ARGS="$@"
# Example: PYTEST_ARGS="-s --alluredir=allure-results --csv-output-field='output_tesslate_response'"

echo "Running pytest tests inside Docker container..."
# Simplified run command:
docker run --rm \
  -v "$(pwd)":/app \
  -w /app \
  --user "$(id -u)":"$(id -g)" \
  "$IMAGE_NAME" \
  python3 -m pytest $PYTEST_ARGS

echo "Tests finished. Generating Allure report..."
allure serve allure-results

echo "Cleanup: Removing dangling Docker images/containers (optional)."
# You might want to run this cleanup manually or less frequently
# docker system prune -f --volumes