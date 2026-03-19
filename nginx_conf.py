from pydantic import BaseModel
import os
import httpx
from services import manage_service
from config import conf_json, ConfConfig, Config
from main import send_log

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
    auth: bool

CONF_PATH = '/etc/nginx/sites-available'
CONF_ENABLED = '/etc/nginx/sites-enabled'

async def create_conf(data: NginxPayload):
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
        auth_lines = ''
        if data.auth:
            auth_lines = f"""
                auth_request /r01t_auth;
                location = /r01t_auth {{
                    internal;
                    proxy_pass http://10.100.0.10:6666/auth_session;
                    proxy_pass_request_body off;
                    proxy_set_header Content-Length "";
                    proxy_set_header X-Original-URI $request_uri;
                    proxy_set_header Cookie $http_cookie;
                    proxy_set_header Authorization $http_authorization;
                    }}
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
                    {auth_lines}
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


    return {'ok': True, 'data': await check_domain(name=data.domain, content=Config.target_ip)}

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
    if Config.dns:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f'https://api.hosting.ionos.com/dns/v1/zones/{Config.zoneid}/records',
                headers = {"X-API-Key": Config.dns_key, "Content-Type": "application/json"},
                json=[{"name": name, "type": type, "content": content, "ttl": 3600, "disabled": False}]
            )
            send_log('info', f'subdomain {name} created: {res.json}')
            return res.json()