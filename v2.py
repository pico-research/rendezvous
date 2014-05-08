from channel import Channel
from twisted.web.server import Site
from twisted.web.resource import Resource, NoResource
from twisted.internet import reactor
import uuid
import argparse


class NewChannelResource(Resource):
    def __init__(self, channels, fixed):
        Resource.__init__(self)
        self.channels = channels
        self.fixed = fixed

    def render_GET(self, request):
        # Get channel name, either fixed for debugging or random
        if self.fixed:
            name = self.fixed
        else:
            name = uuid.uuid4().hex
            
        channel = Channel(name)
        self.channels[name] = channel
        print('Created new channel: ' + str(channel))
        return name


class ChannelsResource(Resource):
    def __init__(self, channels):
        Resource.__init__(self)
        self.channels = channels

    def getChild(self, name, request):
        if name in self.channels:
            # RACE?
            return ChannelResource(self.channels[name])
        else:
            return NoResource()


class ChannelResource(Resource):
    def __init__(self, channel):
        Resource.__init__(self)
        self._channel = channel

    def render_POST(self, request):
        print("Write to channel '{}': {}".format(
                self._channel.name, request.args['data'][0]))
        print(self._channel)
        r = self._channel.write(request)
        print(self._channel)
        return r

    def render_GET(self, request):
        print("Read from channel '{}'".format(self._channel.name))
        print(self._channel)
        r = self._channel.read(request)
        print(self._channel)
        return r
                

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-p', '--port', type=int, default=8080, 
        help='port to run rendezvous server on')
    parser.add_argument(
        '-f', '--fixed',
        help='fixed channel name (debug only)')
    args = parser.parse_args()

    channels = dict()

    root = Resource()
    root.putChild("channel", ChannelsResource(channels))
    root.putChild("new", NewChannelResource(channels, args.fixed))

    factory = Site(root)

    print('Starting rendezvous server on port {}...'.format(args.port))
    reactor.listenTCP(8080, factory)
    reactor.run()
