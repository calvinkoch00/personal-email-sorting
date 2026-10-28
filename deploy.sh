#!/bin/bash
set -e

# The token is securely passed from GitHub Actions
BWS_TOKEN=$1

echo "Starting Deployment..."
cd ~/personal-email-sorting

echo "Pulling latest code from GitHub..."
git fetch origin main
git reset --hard origin/main

echo "Updating Python environment..."
# Check if the virtual environment exists, create it if it doesn't
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt

echo "Checking for Bitwarden Secrets CLI (bws)..."
if ! command -v bws &> /dev/null; then
    echo "Installing bws..."
    curl -fsSL https://bws.bitwarden.com/install | bash
    sudo mv bws /usr/local/bin/
fi

echo "Saving BWS token to .env for systemd..."
echo "ORACLE_MICRO_1_BWS_TOKEN=$BWS_TOKEN" > .env

echo "Restarting FastAPI background service..."
sudo systemctl restart email-router.service

echo "Deployment Successful!"
