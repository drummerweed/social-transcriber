#!/bin/bash
set -e

echo "Installing ffmpeg..."
brew install ffmpeg

echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Setup complete! Run 'source venv/bin/activate' then 'python main.py' to start."
