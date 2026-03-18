import json
import psutil
import subprocess
import os
import sys
import shutil
import httpx
from pydantic import BaseModel

class Config:
    interface = None
    name = None
    services= None
    nginx = None
    dns = None
    dns_key = None
    zoneid = None
    target_ip = None

class ConfConfig(BaseModel):
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

async def get_public_ip(interface):
    interface = interface
    addresses = psutil.net_if_addrs()
    try:
        if interface in addresses:
            for i in addresses[interface]:
                print(i.address)
                return i.address
    except Exception as e:
        return e

async def config_first_time():
    if not os.path.exists('config.json'):
        with open('config.json', 'w') as f:
            json.dump({}, f)
    with open('config.json', 'r') as f:
        config_file = json.load(f)
    interfaces = []
    for i in psutil.net_if_addrs():
        if i != 'lo':
            if i != 'wg0':
                interfaces.append(i)
    not_set = True
    while not_set:
        if len(interfaces) > 1:
            select_interface = input(f'Which interface is for the traffic {interfaces} write name: ')
        else: 
            select_interface = interfaces[0]
        if select_interface in interfaces:
            config_file["interface_traffic"] = select_interface
            not_set = False
    not_set_name = True
    while not_set_name:
        name_input = input('Give the agent a name: ')
        if name_input != '':
            config_file["name"] = name_input
            not_set_name = False
    not_set_services = True
    services = []
    get_services = subprocess.run(
        ["systemctl", "list-units", "--type=service", "--no-pager", "--no-legend"],
        capture_output=True, text=True)
    for i in get_services.stdout.splitlines():
        part = i.split()
        if part:
            services.append(part[0])
    config_file["services"] = ['r01t-agent.service']
    while not_set_services:
        service_input = str(input('Name services that will shown on the api (r for end): ') + '.service')
        if service_input in services:
            services.remove(service_input)
            config_services = config_file["services"]
            config_services.append(service_input)
        elif service_input == 'r.service':
            not_set_services = False
        else:
            print('no service with this name or already in config!')
    if shutil.which('nginx') is not None:
        not_set_nginx = True
        while not_set_nginx:
            nginx_input = str(input('will you use NGINX on your device? y/n '))
            if  nginx_input.lower() == 'y' and'nginx.service' in config_file["services"]:
                config_file['use_nginx'] = True
                not_set_nginx = False
                print('NGINX already in the List of used Services')
            elif nginx_input.lower() == 'y':
                config_services = config_file["services"]
                config_services.append('nginx.service')
                config_file['use_nginx'] = True
                not_set_nginx = False
            elif nginx_input == 'n':
                config_file['use_nginx'] = False
                not_set_nginx = False
        not_set_dns = True
        if config_file['use_nginx']:
            while not_set_dns:
                dns_input = str(input('will you use that DNS in Work with NGINX? y/n '))
                if  dns_input.lower() == 'y':
                    config_file['use_dns'] = True
                    not_set_dns = False
                    config_file['dns_key'] = input('Paste in your key: ')
                    async with httpx.AsyncClient() as client:
                        res = await client.get("https://api.hosting.ionos.com/dns/v1/zones",
                                headers={"X-API-Key": config_file['dns_key'],
                                        "Content-Type": "application/json"})
                        print(res.json())
                    config_file['dns_zone'] = input('Paste in your ZoneID: ')
                    pub_ip = await get_public_ip(config_file["interface_traffic"])
                    ip_dns = input(f'Paste in your target IP or "r" for default: "{pub_ip}": ')
                    if ip_dns == 'r':
                        config_file['dns_traget_ip'] = pub_ip
                    else:
                        config_file['dns_traget_ip'] = ip_dns
                elif dns_input == 'n':
                    config_file['use_dns'] = False
                    not_set_dns = False
    with open('config.json', 'w') as fw:
        json.dump(config_file, fw, indent=4)

def conf_json(data: ConfConfig):
    if not os.path.exists('confs.json'):
        with open('confs.json', 'w') as f:
            json.dump({}, f)
    with open('confs.json', 'r') as f:
        config_file = json.load(f)
    config_file[data.domain] = {'domain': data.domain,
                                'target': data.target_ip if data.redirect_url  == '' else data.redirect_url,
                                'mode': data.mode,
                                'port': data.port if data.redirect_url  == '' else None,
                                'ssl': data.ssl,
                                'websocket': data.websocket,
                                'location': data.location,
                                'max_body_size': data.max_body_size,
                                'timeout': data.timeout,
                                'redirect_http': data.redirect_http}
    with open('confs.json', 'w') as fw:
        json.dump(config_file, fw, indent=4)

def load_config():
    with open('config.json', 'r') as f:
        config = json.load(f)
        Config.interface = config["interface_traffic"]
        Config.name = config["name"]
        Config.services = config["services"]
        Config.nginx = config["user_nginx"]
        if config["user_nginx"]:
            Config.dns = config["use_dns"]
            if Config.dns:
                Config.dns_key = config["dns_key"]
                Config.zoneid = config["dns_zone"]
                Config.target_ip = config['dns_traget_ip']

def load_nginx_conf(all: bool = False, name: str = ''):
    with open('confs.json', 'r') as f:
            data = json.load(f)
    if all:
        return  {'ok': True, 'data': data}
    if name == '':
        return {'ok': False, 'error': 'no_name_provided'}
    if name in data:
        return {'ok': True, 'data': data[name]}
    return {'ok': False, 'error': 'error_while_load'}