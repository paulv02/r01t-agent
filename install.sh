#!/bin/bash
set -e

#curl -s https://raw.githubusercontent.com/paulv02/r01t-agent/main/install.sh -o install.sh
#bash install.sh


apt-get update -qq
apt-get install -y python3-pip python3-venv git

git clone https://github.com/paulv02/r01t-agent /opt/r01t-agent

cd /opt/r01t-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 config_json.py

cat > /etc/systemd/system/r01t-agent.service << EOF
[Unit]
Description=r01t Agent
After=network.target

[Service]
User=root
WorkingDirectory=/opt/r01t-agent
ExecStart=/opt/r01t-agent/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8888
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable r01t-agent
systemctl start r01t-agent

echo "R01T Agent installed and running on port 8888"