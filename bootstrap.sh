#!/bin/bash
set -e

echo "Starting Server Bootstrap..."

if [ ! -f /swapfile ]; then
    echo "Creating 2GB swap file..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
else
    echo "Swap file already exists. Skipping."
fi

echo "Installing system dependencies..."
sudo apt update
sudo apt install -y python3-venv python3-pip debian-keyring debian-archive-keyring apt-transport-https curl

if ! command -v caddy &> /dev/null; then
    echo "Installing Caddy..."
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
    sudo apt update && sudo apt install caddy
fi

echo "Configuring Caddy for mail.calvinkoch.ch..."
cat << 'INNER_EOF' | sudo tee /etc/caddy/Caddyfile
mail.calvinkoch.ch {
    reverse_proxy localhost:8000
}
INNER_EOF
sudo systemctl restart caddy

echo "Setting up Python virtual environment..."
APP_DIR="$(pwd)"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "Creating systemd service for FastAPI..."
cat << INNER_EOF | sudo tee /etc/systemd/system/email-router.service
[Unit]
Description=Email Routing FastAPI Webhook
After=network.target

[Service]
User=ubuntu
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
INNER_EOF

sudo systemctl daemon-reload
sudo systemctl enable email-router.service
sudo systemctl restart email-router.service

echo "Bootstrap complete. Service is running in the background."
