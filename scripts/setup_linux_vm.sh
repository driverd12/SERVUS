#!/bin/bash
# SERVUS Production Setup Script for Amazon Linux 2023
# Run as root (sudo)

set -e

echo "🚀 Starting SERVUS Production Setup..."

# 1. System Updates & Dependencies
echo "📦 Installing Dependencies..."
dnf update -y
dnf install -y git python3-pip python3-devel gcc openssl-devel

# 2. GAM Installation (Linux Binary)
echo "🔧 Installing GAM..."
# We use the standard installer but target the servus user or a shared location
# For this script, we assume running as the 'ec2-user' or similar
GAM_DIR="/home/ec2-user/bin/gam"
mkdir -p $GAM_DIR
curl -s -S -L https://git.io/install-gam | bash -s -- -l -d $GAM_DIR

# Note: You must manually upload oauth2.txt and client_secrets.json to $GAM_DIR
echo "⚠️  ACTION REQUIRED: Upload 'oauth2.txt' and 'client_secrets.json' to $GAM_DIR"

# 3. Python Virtual Environment
echo "🐍 Setting up Python venv..."
APP_DIR="/opt/servus"
mkdir -p $APP_DIR
chown -R ec2-user:ec2-user $APP_DIR

# Assuming repo is cloned to $APP_DIR
cd $APP_DIR
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Systemd Service
echo "⚙️  Creating Systemd Service..."
cat <<EOF > /etc/systemd/system/servus.service
[Unit]
Description=SERVUS Identity Orchestrator
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/scripts/scheduler.py
Restart=always
RestartSec=10
EnvironmentFile=$APP_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

# 5. Systemd Timer (Optional - if we want to run it periodically instead of as a daemon)
# Since scheduler.py has an internal loop, we use a Service. 
# If we wanted to use a Timer, we'd remove the loop from scheduler.py.
# For "Zero-Touch 24/7", the Daemon (Service) approach is preferred for the listener.

echo "✅ Setup Complete!"
echo "👉 Next Steps:"
echo "   1. Clone repo to $APP_DIR"
echo "   2. Create .env file"
echo "   3. Upload GAM secrets"
echo "   4. sudo systemctl enable --now servus"
