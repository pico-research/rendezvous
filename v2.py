from channel import Channel
from response import Ok
from twisted.web.server import Site
from twisted.web.resource import Resource, NoResource
from twisted.internet.error import AlreadyCalled, AlreadyCancelled
from twisted.internet import reactor
import uuid
import argparse


_REQUEST_TIMEOUT = 60
_CHANNEL_CLOSE_TIMEOUT = 120
assert(_REQUEST_TIMEOUT < _CHANNEL_CLOSE_TIMEOUT)


def _close_channel(channel, channels):
    print("Closing channel '{}'".format(channel.name))
    #channel.close_call.cancel()
    channel.close()
    del channels[channel.name]


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

        existing = self._channels.get(name, None)
        if existing:
            _close_channel(existing, self._channels)
            
        channel = Channel(name, self._reactor, _REQUEST_TIMEOUT)
        #channel.close_call = self._reactor.callLater(
        #    _CHANNEL_CLOSE_TIMEOUT, _close_channel, self._channels, name)
        channel.close_call = None
        self._channels[name] = channel
        print('Created new channel: ' + str(channel))
        return name


class ChannelsResource(Resource):
    def __init__(self, channels):
        Resource.__init__(self)
        self.channels = channels

    def getChild(self, name, request):
        channel = self.channels.get(name, None)
        if channel is None:
            return NoResource()
        else:
            #channel.close_call.reset(_CHANNEL_CLOSE_TIMEOUT)
            return ChannelResource(channel, self.channels)


class ChannelResource(Resource):
    def __init__(self, channel, channels):
        Resource.__init__(self)
        self._channels = channels
        self._channel = channel

    # Write
    def render_POST(self, request):
        data = request.content.read()
        print("Write to channel '{}': {}".format(self._channel.name, data))
        print(self._channel)
        r = self._channel.write(request, data)
        print(self._channel)
        return r
        
    # Read
    def render_GET(self, request):
        print("Read from channel '{}'".format(self._channel.name))
        print(self._channel)
        r = self._channel.read(request)
        print(self._channel)
        return r

    # Close channel
    def render_DELETE(self, request):
        print("Closing channel '{}'".format(self._channel.name))
        try:
            # This is wierd
            if self._channel.close_call:
                self._channel.close_call.cancel()
            _close_channel(self._channel, channels)
        except (AlreadyCancelled, AlreadyCalled):
            # Fine
            pass
        return Ok().render(request)
                

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
    reactor.listenTCP(args.port, factory)
    reactor.run()
