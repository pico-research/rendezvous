from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.http import Request
from twisted.web.resource import Resource, NoResource
from twisted.internet import reactor, protocol
import uuid
import argparse


class SSEStream(object):
    def __init__(self, request=None):
        self.listening_requests = set()
        self.finished = False

        if request:
            self.listen(request)

    def _get_listeners(self):
        return len(self.listening_requests)

    listeners = property(_get_listeners, None, None, None)

    def listen(self, request):
        request.setHeader("Content-Type", "text/event-stream")
        request.setHeader("Cache-Control", "no-cache")
        request.setHeader("Connection", "keep-alive")
        self.listening_requests.add(request)
        self.send(event="join", data=self.listeners)

    def send(self, data, event=None):
        # Form the string to be written to the stream
        if not event:
            event = "data"
        s = "event: {}\ndata: {}\n\n".format(event, data)

        # Write it to each listening request
        for r in self.listening_requests:
            r.write(s)

    def finish(self):
        for r in self.listening_requests:
            r.finish()
        self.finished = True


class Channels(Resource):
    def __init__(self, channels):
        Resource.__init__(self)
        self.channels = channels

    def getChild(self, name, request):
        if name in self.channels:
            return Channel(name, self.channels[name])
        else:
            return NoResource()


class NewChannel(Resource):
    def __init__(self, channels, fixed):
        Resource.__init__(self)
        self.channels = channels
        self.fixed = fixed

    def render_GET(self, request):
        print("NewChannel.render_GET start")
        try:
            # Get channel name, either fixed for debugging or random
            if self.fixed:
                channel_name = self.fixed
            else:
                channel_name = uuid.uuid4().hex
            
            # Initialize list of channel listeners
            if channel_name not in self.channels:
                self.channels[channel_name] = set() # RACE CONDITION

            print("Created new channel '{}'".format(channel_name))
            return channel_name
        finally:
            print("NewChannel.render_GET finish")


class Channel(Resource):
    def __init__(self, name, listeners):
        Resource.__init__(self)
        self.name = name
        self.listeners = listeners

    def render_POST(self, request):
        print("Channel.render_POST start")
        try:
            data = request.args['data'][0]
            for l in self.listeners:
                l.write(data)
                l.finish()

            print("Data posted to channel '{}': {}".format(self.name, data))
            return ""
        finally:
            print("Channel.render_POST finish")

    def render_GET(self, request):
        print("Channel.render_POST start")
        try:
            # Add current request to set of listeners
            self.listeners.add(request)

            print("New listener on channel '{}'".format(self.name))
            return NOT_DONE_YET
        finally:
            print("Channel.render_POST finish")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=8080, help='port to run rendezvous server on')
    parser.add_argument('-f', '--fixed', help='fixed channel name (debug only)')
    args = parser.parse_args()

    channels = dict()

    root = Resource()
    root.putChild("channel", Channels(channels))
    root.putChild("new", NewChannel(channels, args.fixed))

    factory = Site(root)

    print('Starting rendezvous server on port {}...'.format(args.port))
    reactor.listenTCP(8080, factory)
    reactor.run()
