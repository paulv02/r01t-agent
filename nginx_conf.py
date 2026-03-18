from pydantic import BaseModel
import os
import httpx
from services import manage_service
from config import conf_json, ConfConfig

class NginxPayload(BaseModel):
    domain: str
    target_ip: str
    redirect_url: str
    mode: str
    port: str
    ssl: bool
    websocket: bool
    location: str
    max_body_size: str
    timeout: int
    redirect_http: bool

CONF_PATH = '/etc/nginx/sites-available'
CONF_ENABLED = '/etc/nginx/sites-enabled'

def create_conf(data: NginxPayload):
    if os.path.exists(f'{CONF_ENABLED}/{data.domain}'):
        return {'ok': False, 'error': 'conf_exists'}
    conf = ''
    if data.mode == 'proxy' and data.ssl:
        websocket_lines = ""
        if data.websocket:
            websocket_lines ="""
                proxy_http_version 1.1;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "upgrade";
                """
        conf += f"""
            server{{
                listen 80;
                server_name {data.domain};
                return 301 https://$host$request_uri;
            }}
            server {{
                listen 443 ssl;
                server_name {data.domain};
                ssl_certificate /etc/letsencrypt/live/cloud.r01t.de/fullchain.pem;
                ssl_certificate_key /etc/letsencrypt/live/cloud.r01t.de/privkey.pem;
                ssl_protocols TLSv1.2 TLSv1.3;
                client_max_body_size {data.max_body_size};
                location /{data.location} {{
                    {websocket_lines}
                    proxy_pass http://{data.target_ip}:{data.port};
                    proxy_set_header Host $host;
                    proxy_set_header X-Real-IP $remote_addr;
                    proxy_read_timeout {data.timeout};
                }}
            }}
            """
    elif data.mode == 'proxy' and not data.ssl:
        websocket_lines = ""
        if data.websocket:
            websocket_lines ="""
                proxy_http_version 1.1;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "upgrade";
                """
        conf += f"""
            server{{
                    listen 80;
                    server_name {data.domain};
                    client_max_body_size {data.max_body_size};        

            location /{data.location}  {{
                    {websocket_lines}
                    proxy_pass http://{data.target_ip}:{data.port};
                    proxy_set_header Host $host;
                    proxy_set_header X-Real-IP $remote_addr;
                    proxy_read_timeout {data.timeout};
                }}
            }}
            """
    elif data.mode == 'redirect':
        conf += f"""
            server{{
                listen 80;
                server_name {data.domain};
                return 301 {data.redirect_url};
            }}
            """
    with open(f'{CONF_PATH}/{data.domain}', 'w') as f:
        f.write(conf)

    conf_json(data)

    return {'ok': True}

def enable_conf(name):
    if not os.path.exists(f'{CONF_ENABLED}/{name}'):
        os.symlink(f'{CONF_PATH}/{name}', f'{CONF_ENABLED}/{name}')
        return manage_service('nginx.service', 'reload')
    else:
        return {'ok': False, 'error': 'conf_already_exists'}

def disable_conf(name):
    if os.path.exists(f'{CONF_ENABLED}/{name}'):
        os.remove(f'{CONF_ENABLED}/{name}')
        return manage_service('nginx.service', 'reload')
    else:
        return {'ok': False, 'error': 'conf_not_exists'}
    
def delete_conf(name):
    disable_conf(name)
    if os.path.exists(f'{CONF_PATH}/{name}'):
        os.remove(f'{CONF_PATH}/{name}')
        return {'ok': True}
    else:
        return {'ok': False, 'error': 'conf_not_exists'}
    
async def check_domain(name: str, type: str = 'A', content: str = ''):
    