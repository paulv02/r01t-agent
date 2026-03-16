import subprocess

def manage_service(name: str, action: str):
    available_actions = ['restart', 'stop', 'start', 'enable', 'disable', 'reload']
    if action not in available_actions:
        return {'ok': False, 'error': 'invalid_action'}
    result = subprocess.run(['systemctl', action, name ], capture_output=True, text=True)
    if result.returncode == 0:
        return {'ok': True}
    else:
        return {'ok': False, 'error': result.stderr.strip()}

