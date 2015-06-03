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
    def __init__(self, streams):
        Resource.__init__(self)
        self.streams = streams

    def getChild(self, name, request):
        try:
            stream = self.streams[name]
            if stream.finished:
                self.streams.pop(name, None)
                return NoResource()
            else:
                return Channel(name, stream)
        except KeyError:
            return NoResource()
        '''No longer appropriate with listen method
        finally:
        self.streams.pop(name, None)
        '''


class NewChannel(Resource):
    def __init__(self, streams, fixed):
        Resource.__init__(self)
        self.streams = streams
        self.fixed = fixed

    def render_GET(self, request):
        print("NewChannel.render_GET start")
        try:
            # Get channel name, either fixed for debugging or random
            channel_name = self.fixed or uuid.uuid4().hex

            # Get or create stream
            if channel_name in self.streams:
                stream = self.streams.get(channel_name, False)
                stream.listen(request)
            else:
                stream = SSEStream(request)
                self.streams[channel_name] = stream

            stream.send(event="channel-created", data=channel_name)
            print("Created new channel '{}'".format(channel_name))
            return NOT_DONE_YET
        finally:
            print("NewChannel.render_GET finish")


class Channel(Resource):
    def __init__(self, name, stream):
        Resource.__init__(self)
        self.name = name
        self.stream = stream

    def render_POST(self, request):
        print("Channel.render_POST start")
        try:
            data = request.args['data'][0]
            print("Data posted to channel '{}': {}".format(self.name, data))
            self.stream.send(data)
            self.stream.finish()
            return ""
        finally:
            print("Channel.render_POST finish")

    def render_GET(self, request):
        print("Channel.render_POST start")
        try:
            self.stream.listen(request)
            print("New listener on channel '{}'".format(self.name))
            return NOT_DONE_YET
        finally:
            print("Channel.render_POST finish")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=8080, help='port to run rendezvous server on')
    parser.add_argument('-f', '--fixed', help='fixed channel name (debug only)')
    args = parser.parse_args()

    streams = dict()

    root = Resource()
    root.putChild("channel", Channels(streams))
    root.putChild("new", NewChannel(streams, args.fixed))

    factory = Site(root)

    print('Starting rendezvous server on port {}...'.format(args.port))
    reactor.listenTCP(args.port, factory)
    reactor.run()
