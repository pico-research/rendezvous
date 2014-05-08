from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import NoResource
from twisted.internet.error import AlreadyCalled, AlreadyCancelled
from helpers import error


_PEER_DISCONNECTED = error(1, 'peer disconnected whilst writing data')
_TIMEOUT = error(2, 'request timed out')
_CHANNEL_CLOSED = error(3, 'channel closed unexpectedly')


class Channel(object):
    def __init__(self, name):
        self.name = name
        self.state = Standby(self)
        self._timeout_call = None
        self._close_call = None

    def write(self, request):
        return self.state.write(request)

    def read(self, request):
        return self.state.read(request)

    def timeout(self):
        try:
            self._timeout_call.cancel()
        except TypeError, AlreadyCancelled, AlreadyCalled:
            # self._timeout_call not yet set or already called/cancelled
            # That's fine, no action needed
            pass
        self._state.timeout()

    def timeout_in(self, delay):
        if delay > 0:
            try:
                self._timeout_call.reset(delay)
            except TypeError, AlreadyCancelled, AlreadyCalled:
                # self._timeout_call not yet set or already called/cancelled
                self._timeout_call = reactor.callLater(delay, self.timeout)
        else:
            # Call timeout immediately
            self.timeout()

    def close(self):
        pass

    def close_in(self, delay):
        if delay > 0:
            pass
        else:
            pass

    def __str__(self):
        return "Channel '{}' with state: {}".format(self.name, self.state)


class ChannelState(object):
    def __init__(self, channel):
        self._channel = channel


class Standby(ChannelState):
    def write(self, request):
        self._channel.state = WriteWaiting(self._channel, request)
        return NOT_DONE_YET

    def read(self, request):
        self._channel.state = ReadWaiting(self._channel, request)
        return NOT_DONE_YET

    def timeout(self):
        pass

    def __str__(self):
        return 'Standby'


class WriteWaiting(ChannelState):
    def __init__(self, channel, waiting_write_request):
        super(WriteWaiting, self).__init__(channel)
        waiting_write_request.notifyFinish().addErrback(self._waiting_closed)
        self._waiting_write_request = waiting_write_request

    def write(self, request):
        # No state change
        return NoResource().render(request)

    def read(self, request):
        try:
            data = self._waiting_write_request.args['data'][0]
            self._waiting_write_request.finish()
        except RuntimeError:
            # The waiting write request was closed
            return _PEER_DISCONNECTED
        else:
            self._channel.state = Standby(self._channel)
            return data

    def timeout(self):
        print('Waiting write request timed out')
        self._waiting_write_request.write(_TIMEOUT)
        self._waiting_write_request.finish()
        self._channel.state = Standby(self._channel)

    def _waiting_closed(self, err):
        print('Waiting write request closed')
        self._channel.state = Standby(self._channel)

    def __str__(self):
        data = self._waiting_write_request.args['data'][0]
        return "WriteWaiting '{}'".format(data)


class ReadWaiting(ChannelState):
    def __init__(self, channel, waiting_read_request):
        super(ReadWaiting, self).__init__(channel)
        waiting_read_request.notifyFinish().addErrback(self._waiting_closed)
        self._waiting_read_request = waiting_read_request

    def write(self, request):
        try:
            data = request.args['data'][0]
            self._waiting_read_request.write(data)
            self._waiting_read_request.finish()
        except RuntimeError:
            # The waiting read request was closed
            return _PEER_DISCONNECTED
        else:
            self._channel.state = Standby(self._channel)
            return '' # Just return 200 OK

    def read(self, request):
        # No state change
        return NoResource().render(request)

    def timeout(self):
        print('Waiting read request timed out')
        self._waiting_read_request.write(_TIMEOUT)
        self._waiting_read_request.finish()
        self._channel.state = Standby(self._channel)

    def _waiting_closed(self, err):
        print('Waiting read request closed')
        self._channel.state = Standby(self._channel)

    def __str__(self):
        return 'ReadWaiting'
    
    

    
