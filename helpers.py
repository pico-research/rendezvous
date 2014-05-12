import json


def error(code, message):
    return json.dumps(
        {'status': 'error', 'code': code, 'message': message}) + '\n'

def success(data=None):
    d = {'status': 'success', 'code': 0}
    if data:
        d['data'] = data
    return json.dumps(d) + '\n'

def closed():
    return json.dumps({'status': 'success', 'code': -1}) + '\n'
