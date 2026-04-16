#!/bin/bash
# Script to start the IG Transcriber on the Raspberry Pi
echo "Starting IG Transcriber..."

# Check if docker-compose is installed
if command -v docker-compose &> /dev/null; then
    docker-compose up -d --build
elif docker compose version &> /dev/null; then
    docker compose up -d --build
else
    echo "Error: docker-compose not found. Please install Docker."
    exit 1
fi

echo "Server started on port 8000!"
