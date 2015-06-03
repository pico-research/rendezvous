import json

from twisted.web.resource import Resource


def _with_json_headers(request, response):
    request.setHeader('Content-Type', 'application/json')
    request.setHeader('Content-Length', len(response))
    return response


class Ok(Resource):
    def render(self, request):
        response = json.dumps(
            {'status': 'ok',
             'code': 0}) + '\n'
        return _with_json_headers(request, response)


class Data(Resource):
    def __init__(self, data):
        self._data = data

    def render(self, request):
        request.setHeader('Content-Type', 'application/octet-stream')
        request.setHeader('Content-Length', len(self._data))
        return self._data


class Closed(Resource):
    def render(self, request):
        response = json.dumps(
            {'status': 'ok',
             'code': -1,
             'message': 'channel closed'}) + '\n'
        return _with_json_headers(request, response)


class Timeout(Resource):
    def render(self, request):
        response = json.dumps(
            {'status': 'error',
             'code': 2,
             'message': 'request timed out'}) + '\n'
        return _with_json_headers(request, response)
