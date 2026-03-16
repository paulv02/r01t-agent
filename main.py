from fastapi import FastAPI, Request
import time
import psutil
import json
import asyncio
import httpx
import config
import urllib.error
from urllib import request
from metrics import collect_data, collect_services, collect_metrics
from services import manage_service
from contextlib import asynccontextmanager
from config import Config, load_nginx_conf
from nginx_conf import *

config.load_config()

@asynccontextmanager
async def start_task(app: FastAPI):
    asyncio.create_task(reg_agent())
    send_start_info()
    yield

app = FastAPI(lifespan=start_task)

IP = ''
IP_PUBLIC = ''
CONTOLLER_ADDR = 'http://10.100.0.10:7777'
hb_intervall = 30

def get_ip():
    interface = 'wg0'
    addresses = psutil.net_if_addrs()
    global IP
    if IP  == '':
        try:
            if interface in addresses:
                for i in addresses[interface]:
                    IP = i.address
                    return IP
        except Exception as e:
            send_log('error', e)
    else:
        return IP

def get_public_ip():
    interface = Config.interface
    addresses = psutil.net_if_addrs()
    global IP_PUBLIC
    if IP_PUBLIC  == '':
        try:
            if interface in addresses:
                for i in addresses[interface]:
                    IP_PUBLIC = i.address
                    return IP_PUBLIC
        except Exception as e:
            send_log('error', e)
    else:
        return IP_PUBLIC

async def reg_agent():
    last_hb = 0
    async with httpx.AsyncClient() as client:
        while True:
            if time.time() >= last_hb + hb_intervall:
                payload = { 'IP': get_ip(),'PUBLIC_IP': get_public_ip(), 'NAME': Config.name, 'PORT': 8888, 'SERVICES': Config.services, 'LS': int(time.time()) }
                body = json.dumps(payload)
                try:
                    res = await client.post(f'{CONTOLLER_ADDR}/reg_agent', content=body, headers={"Content-Type": "application/json"}, timeout=5)
                    if res.status_code == 200:
                        last_hb = time.time()
                except httpx.RequestError:
                    pass
            await asyncio.sleep(1)

def send_log(level, msg):
    try:
        payload = {
            'IP': get_ip(),
            'LEVEL': level,
            'MSG': msg
        }
        body = json.dumps(payload).encode('utf-8')
        res = request.Request( f'{CONTOLLER_ADDR}/send_error',
                data= body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
        response = request.urlopen(res, timeout=2)
        return response.status
    except urllib.error.URLError as e:
        return None

def send_start_info():
    not_get = True
    for i in range(5):
        if send_log('info', 'Started') == 200:
            break
        time.sleep(1)

send_start_info()

@app.get('/current')
def current():
    return collect_data()

@app.get('/services')
def services():
    return collect_services()

@app.get('/metrics')
def metrics():
    return collect_metrics()

@app.post('/service/{name}/{action}')
def service_actions(name: str, action: str):
    return manage_service(name, action)

@app.post('/nginx/add')
def add_nginx(config: NginxPayload):
    if Config.nginx:
        return create_conf(config)
    return {'ok': False, 'error': 'agent_not_provided'}

@app.post('/nginx/enable/{name}')
def enable_nginx(name: str):
    if Config.nginx:
        return enable_conf(name)
    return {'ok': False, 'error': 'agent_not_provided'}

@app.post('/nginx/disable/{name}')
def disable_nginx(name: str):
    if Config.nginx:
        return disable_conf(name)
    return {'ok': False, 'error': 'agent_not_provided'}

@app.post('/nginx/delete/{name}')
def delete_nginx(name: str):
    if Config.nginx:
        return delete_conf(name)
    return {'ok': False, 'error': 'agent_not_provided'}

@app.get('/nginx/{name}')
def load_nginx(name: str):
    if not Config.nginx:
        return {'ok': False, 'error': 'agent_not_provided'}
    return load_nginx_conf(name=name)

@app.get('/nginx/all')
def load_nginx_all():
    if not Config.nginx:
        return {'ok': False, 'error': 'agent_not_provided'}
    return load_nginx_conf(all=True)