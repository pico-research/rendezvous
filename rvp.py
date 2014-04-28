from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.http import Request
from twisted.web.resource import Resource, NoResource
from twisted.internet import reactor, protocol
import uuid


class GetChannel(Resource):
    def __init__(self, channels):
        Resource.__init__(self)
        self.channels = channels

    def render_GET(self, request):
        # generate random string
        channel_name = uuid.uuid4().hex
        print("Created channel '{}'".format(channel_name))
        self.channels[channel_name] = SSEStream(request)
        self.channels[channel_name].send(
                event="channel-created", data=channel_name)
        return NOT_DONE_YET


class SSEStream(object):
    def __init__(self, request):
        self.request = request
        self.request.setHeader("Content-Type", "text/event-stream")

    def send(self, data, event=None):
        if event:
            self.request.write("event: {}\n".format(event))
        self.request.write("data: {}\n\n".format(data))

    def finish(self):
        self.request.finish()


class Publish(Resource):
    def __init__(self, channels):
        self.channels = channels
        Resource.__init__(self)

    def getChild(self, name, request):
        try:
            return PostToChannel(self.channels[name])
        except KeyError:
            return NoResource()
        finally:
            self.channels.pop(name, None)


class PostToChannel(Resource):
    def __init__(self, channel):
        Resource.__init__(self)
        self.channel = channel

    def render_POST(self, request):
        data = request.args['data'][0]
        print("Posted data '{}'".format(data))
        self.channel.send(event="data", data=data)
        self.channel.finish()
        return ""


channels = dict()

root = Resource()
root.putChild("get-rvp", GetChannel(channels))
root.putChild("channel", Publish(channels))


factory = Site(root)
reactor.listenTCP(8080, factory)
reactor.run()
