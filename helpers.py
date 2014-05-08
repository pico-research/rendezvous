import json


def error(code, message):
    return json.dumps({'status': 'error', 'code': code, 'message': message})
