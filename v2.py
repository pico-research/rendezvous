from twisted.web.server import Site, NOT_DONE_YET
from twisted.web.http import Request
from twisted.web.resource import Resource, NoResource
from twisted.internet import reactor, protocol
import uuid
import argparse


class Channel(object):
    def __init__(self, name):
        self.name = name
        self.waiting_read_req = None
        self.waiting_write_req = None
        self.buffer = ''


# Resources


class ChannelsResource(Resource):
    def __init__(self, channels):
        Resource.__init__(self)
        self.channels = channels

    def getChild(self, name, request):
        if name in self.channels:
            return ChannelResource(self.channels[name])
        else:
            return NoResource()


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
            
        self.channels[name] = Channel(name)
        print("Created new channel '{}'".format(name))
        return name + '\n'


class ChannelResource(Resource):
    def __init__(self, channel):
        Resource.__init__(self)
        self._channel = channel

    def render_POST(self, request):
        data = request.args['data'][0]
        print("New data written to channel '{}': {}".format(
                self._channel.name, data))

        # Append data to the channel buffer
        self._channel.buffer += request.args['data'][0]

        read_request = self._channel.waiting_read_req
        if read_request:
            print("Read request already waiting")

            try:
                # Write and clear the channel buffer
                read_request.write(self._channel.buffer)
                self._channel.buffer = '' # RACE!

                # Close the connection with both peers
                read_request.finish()
            except RuntimeError:
                # Read request disconnected
                print("WARNING: Read request disconnected!")
            finally:
                self._channel.waiting_read_req = None
                return ''
        else:
            # Hang the write request until a read request is made
            print("Write request hanging until read request is made")
            self._channel.waiting_write_req = request
            return NOT_DONE_YET

    def render_GET(self, request):
        write_request = self._channel.waiting_write_req
        if write_request:
            print("Write request alread waiting")

            try:
                # Write and clear the channel buffer
                response = self._channel.buffer
                self._channel.buffer = '' # RACE!
                return response
            finally:
                write_request.finish()
                self._channel.waiting_write_req = None
        else:
            # Hang the read request until a write request is made
            print("Read request hanging until write request is made")
            self._channel.waiting_read_req = request
            return NOT_DONE_YET
                


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=8080, help='port to run rendezvous server on')
    parser.add_argument('-f', '--fixed', help='fixed channel name (debug only)')
    args = parser.parse_args()

    channels = dict()

    root = Resource()
    root.putChild("channel", ChannelsResource(channels))
    root.putChild("new", NewChannelResource(channels, args.fixed))

    factory = Site(root)

    print('Starting rendezvous server on port {}...'.format(args.port))
    reactor.listenTCP(8080, factory)
    reactor.run()
