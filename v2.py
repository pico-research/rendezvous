from channel import Channel
from response import Ok
from twisted.web.server import Site
from twisted.web.resource import Resource, NoResource
from twisted.internet.error import AlreadyCalled, AlreadyCancelled
from twisted.internet import reactor
import uuid
import argparse


_REQUEST_TIMEOUT = 10
_CHANNEL_CLOSE_TIMEOUT = 30
assert(_REQUEST_TIMEOUT < _CHANNEL_CLOSE_TIMEOUT)


def _close_channel(channels, channel_name):
    channels[channel_name].close()
    del channels[channel_name]


class NewChannelResource(Resource):
    def __init__(self, channels, reactor, fixed):
        Resource.__init__(self)
        self._channels = channels
        self._reactor = reactor
        self._fixed = fixed

    def render_GET(self, request):
        # Get channel name, either fixed for debugging or random
        if self._fixed:
            name = self._fixed
        else:
            name = uuid.uuid4().hex
            
        channel = Channel(name, self._reactor, _REQUEST_TIMEOUT)
        channel.close_call = self._reactor.callLater(
            _CHANNEL_CLOSE_TIMEOUT, _close_channel, self._channels, name)
        self._channels[name] = channel
        print('Created new channel: ' + str(channel))
        return name


class ChannelsResource(Resource):
    def __init__(self, channels):
        Resource.__init__(self)
        self.channels = channels

    def getChild(self, name, request):
        if name in self.channels:
            # RACE?
            return ChannelResource(self.channels[name], self.channels)
        else:
            return NoResource()


class ChannelResource(Resource):
    def __init__(self, channel, channels):
        Resource.__init__(self)
        self._channels = channels
        self._channel = channel
        self._channel.close_call.reset(_CHANNEL_CLOSE_TIMEOUT)

    def render_POST(self, request):
        if 'data' in request.args:
            print("Write to channel '{}': {}".format(
                    self._channel.name, request.args['data'][0]))
            print(self._channel)
            r = self._channel.write(request)
            print(self._channel)
            return r
        elif 'close' in request.args:
            print("Closing channel '{}'".format(self._channel.name))
            try:
                # This is wierd
                self._channel.close_call.cancel()
                _close_channel(channels, self._channel.name)
            except (AlreadyCancelled, AlreadyCalled):
                # Fine
                pass
            return Ok().render(request)
        else:
            return NoResource().render(request)
            

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
    root.putChild("new", NewChannelResource(channels, reactor, args.fixed))

    factory = Site(root)

    print('Starting rendezvous server on port {}...'.format(args.port))
    reactor.listenTCP(8080, factory)
    reactor.run()
