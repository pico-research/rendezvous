import threading
from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import NoResource
from twisted.internet.error import AlreadyCalled, AlreadyCancelled
from helpers import error, success, closed
from response import Data, Ok, Timeout, Closed


_PEER_DISCONNECTED = error(1, 'peer disconnected whilst writing data')
_TIMEOUT = error(2, 'request timed out')
_CHANNEL_CLOSED = error(3, 'channel closed unexpectedly')


class Channel(object):
    def __init__(self, name, reactor, timeout_delay):
        self.name = name
        self.state = Standby(self)
        self.lock = threading.Lock()

        self._timeout_delay = timeout_delay
        self._reactor = reactor
        self._timeout_call = None

    def write(self, request, data):
        with self.lock:
            return self.state.write(request, data)

    def read(self, request):
        with self.lock:
            return self.state.read(request)

    def disconnect(self, err):
        with self.lock:
            return self.state.disconnect(err)

    def timeout(self):
        self.cancel_delayed_timeout()
        with self.lock:
            self.state.timeout()

    def delayed_timeout(self):
        if self._timeout_delay > 0:
            try:
                self._timeout_call.reset(self._timeout_delay)
            except (AttributeError, AlreadyCancelled, AlreadyCalled):
                # self._timeout_call not yet set or already called/cancelled
                self._timeout_call = self._reactor.callLater(
                    self._timeout_delay, self.timeout)
        else:
            # Call timeout immediately
            self.timeout()

    def cancel_delayed_timeout(self):
        try:
            self._timeout_call.cancel()
        except (AttributeError, AlreadyCancelled, AlreadyCalled):
            # self._timeout_call not yet set or already called/cancelled
            # That's fine, no action needed
            pass

    def close(self):
        self.cancel_delayed_timeout()
        with self.lock:
            self.state.close()

    def __str__(self):
        return "Channel '{}' with state: {}".format(self.name, self.state)


class ChannelState(object):
    def __init__(self, channel):
        self._channel = channel


class Standby(ChannelState):
    def __init__(self, channel):
        super(Standby, self).__init__(channel)
        self._channel.cancel_delayed_timeout()

    def write(self, request, data):
        self._channel.state = WriteWaiting(self._channel, request, data)
        return NOT_DONE_YET

    def read(self, request):
        self._channel.state = ReadWaiting(self._channel, request)
        return NOT_DONE_YET

    def disconnect(self, err):
        pass

    def timeout(self):
        pass

    def close(self):
        pass

    def __str__(self):
        return 'Standby'


class WriteWaiting(ChannelState):
    def __init__(self, channel, write_request, data):
        super(WriteWaiting, self).__init__(channel)

        # Keep a reference to the writing request
        self._write_request = write_request
        write_request.notifyFinish().addErrback(self._channel.disconnect)
        
        # Store the written data
        self._data = data

        # Start the timeout
        self._channel.delayed_timeout()

    def __str__(self):
        return "WriteWaiting '{}'".format(self._data)

    def write(self, request):
        # No state change
        return NoResource().render(request)

    def read(self, read_request):
        data = self._data

        # Write to reader
        read_request.write(Data(data).render(read_request))
        try:
            self._write_request.write(Ok().render(self._write_request))
            self._write_request.finish()
        except RuntimeError:
            # Waiting write request disconnected
            # Nothing to be done
            print("Runtime error!")

        self._channel.state = Standby(self._channel)
        return ''

    def disconnect(self, err):
        print('Waiting write request closed')
        self._channel.state = Standby(self._channel)

    def timeout(self):
        print('Timing out waiting write request')
        try:
            self._write_request.write(Timeout().render(self._write_request))
            self._write_request.finish()
        except RuntimeError:
            # The waiting read request was closed remotely
            pass
        finally:
            self._channel.state = Standby(self._channel)

    def close(self):
        try:
            self._write_request.write(Closed().render(self._write_request))
            self._write_request.finish()
        except RuntimeError:
            # The waiting write request was closed remotely
            pass


class ReadWaiting(ChannelState):
    def __init__(self, channel, read_request):
        super(ReadWaiting, self).__init__(channel)
        self._read_request = read_request
        read_request.notifyFinish().addErrback(self._channel.disconnect)
        self._channel.delayed_timeout()

    def __str__(self):
        return 'ReadWaiting'

    def write(self, write_request, data):
        try:
            self._read_request.write(Data(data).render(self._read_request))
            self._read_request.finish()
        except RuntimeError:
            # The waiting read request was closed remotely
            return _PEER_DISCONNECTED
        else:
            return Ok().render(write_request)
        finally:
            self._channel.state = Standby(self._channel)

    def read(self, request):
        # No state change
        return NoResource().render(request)

    def disconnect(self, err):
        print('Waiting read request closed remotely')
        self._channel.state = Standby(self._channel)

    def timeout(self):
        print('Timing out waiting read request')
        try:
            self._read_request.write(Timeout().render(self._read_request))
            self._read_request.finish()
        except RuntimeError:
            # The waiting read request was closed remotely
            pass
        finally:
            self._channel.state = Standby(self._channel)

    def close(self):
        try:
            self._read_request.write(Closed().render(self._read_request))
            self._read_request.finish()
        except RuntimeError:
            # The waiting read request was closed remotely
            pass
