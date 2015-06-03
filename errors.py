from twisted.web.resource import Resource
from helpers import error


class Timeout(Resource):
    def render(self, request):
        response = error(2, 'request timed out')
        request.setHeader('Content-Type', 'text/json')
        request.setHeader('Content-Length', len(response))
        return response
