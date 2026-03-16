import psutil
import time
import subprocess
import config
from config import Config

config.load_config()

def collect_metrics():
    ram = psutil.virtual_memory().percent
    cpu = psutil.cpu_percent(0.2)
    uptime = int(time.time() - psutil.boot_time())
    temps = psutil.sensors_temperatures()
    if temps:
        temperatur_dict = []
        for i in temps:
            for e in temps[i]:
                temperatur_dict.append(int(e.current))
        temperatur = max(temperatur_dict)
    else:
        temperatur = None
    traffic = []
    for i in ["tx_bytes", "rx_bytes"]:
        with open(f"/sys/class/net/{Config.interface}/statistics/{i}")as f:
            traffic.append({i: int(f.read())})
    return {'ram': ram, 'cpu': cpu, 'uptime': uptime, 'temperatur':temperatur, 'traffic': traffic}

def collect_services():
    services = {}
    for i in Config.services:
        data = {}
        service = subprocess.run(['systemctl', 'show', i, '--no-pager'],
                    capture_output=True, text=True)
        for l in service.stdout.splitlines():
            if "=" in l:
                key, val = l.split("=", 1)
                data[key] = val
        services[i] = {'status': data.get('ActiveState'),
                        'sub': data.get('Substate'),
                        'since': data.get('ActiveEnterTimestamp'),
                        "description": data.get("Description"),
                    }

    return services

def collect_data():
    return {'metrics': collect_metrics(), 'services': collect_services()}