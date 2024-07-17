#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import struct
from threading import Lock

import trio


class BufferedWriter:
    """Like a trio SendStream, but send() just buffers data and returns immediately.

    This is more like the asyncio behaviour, where write() is a regular function that returns
    immediately, while drain() is an async method that waits for bytes to be sent to the OS.

    This class exists for two reasons:

    1. So that a slow writing connection does not slow down message reads (e.g. writing a task over
       a broken connection to an ASM does not slow down reads from the DMM, which would slow down
       writing tasks to other ASMs).
    2. So that an error writing to a connection is reported as an exception to the correct task,
       because typically writes are done from the "wrong" coroutine (e.g. writing to ASMs is done
       from the DMM coroutine, and a broken ASM connection should not close the DMM connection).

    The creator of this class should call nursery.start_soon(writer.perform_writes) after
    constructing this class.
    """

    def __init__(self, send_stream: trio.abc.SendStream, max_data: int):
        self.send_stream = send_stream
        self.buffered_bytes = bytearray()
        self.parking_lot = trio.lowlevel.ParkingLot()
        self.exception = None
        self.max_data = max_data

    async def perform_writes(self):
        """Waits for messages to be buffered then writes them; analogous to drain() in asyncio."""
        while True:
            while self.exception is None and len(self.buffered_bytes) == 0:
                await self.parking_lot.park()
            if self.exception is not None:
                raise self.exception
            message_data = self.buffered_bytes
            self.buffered_bytes = bytearray()
            await self.send_stream.send_all(message_data)

    def write_nowait(self, message):
        """Adds message data to the queue to write soon."""
        if self.exception is not None:
            # Already exceeded buffer limit
            return
        self.buffered_bytes.extend(message)
        if len(self.buffered_bytes) > self.max_data:
            self.exception = RuntimeError(
                f"Send buffer full ({len(self.buffered_bytes)} > {self.max_data} bytes)"
            )
            self.buffered_bytes = None
        # Wake the writer (if it is waiting)
        self.parking_lot.unpark()


async def receive_until(
    receive_stream: trio.abc.ReceiveStream,
    read_buffer: bytearray,
    delimiter: bytes,
    max_size: int,
    return_delimiter: bool = False,
):
    """Reads precisely one message from the given stream until the given delimiter.

    This is a bit more general than is needed for Apex, since we only ever need the delimiter b'\0'.
    This signature was chosen to match the receive_until definition that is planned to possibly go
    into trio as a standard function, at which point we can remove this implementation.

    The purpose of the read_buffer parameter is mainly to preserve data across calls in case any
    multiple messages, in whole or in part, are returned from a call to receive_some. For example,
    if the delimiter is b"x" and a single call to receive_some returns b"AAAxBBBxCC" then this
    function will return b"AAA" and leave b"BBBxCC" in the buffer; assuming the same buffer is
    passed back in to another call to this function, the next time it will return b"BBB" and leave
    b"CC" in the buffer without calling receive_until() at all. The other purpose of the read_buffer
    parameter is to allow inspection of partially read data in case of an exception (either the two
    that this function raises itself, or a cancellation exception).

    :param receive_stream: Stream to read bytes from, using repeated calls to receive_some() method
    :param read_buffer: Intermediate buffer to store data read from stream
    :param delimiter: Sequence of bytes that delimit messages
    :param max_size: Maximum size allowed for messages (not including delimiter)
    :param return_delimiter: Whether to include delimiter in returned message
    :return: The message read from the stream
    :raises RuntimeError: Message was too long (possibly thrown before delimiter was encountered)
    :raises EOFError: Stream was closed before a whole message was read
    """
    next_find_index = 0
    max_size += len(delimiter)  # Include delimiter to simplify calculations
    while (terminator_index := read_buffer.find(delimiter, next_find_index)) < 0:
        if len(read_buffer) > max_size:
            raise RuntimeError(f"Message too long (pending {len(read_buffer)} > {max_size})")
        # Next time, start searching from where we left off
        next_find_index = max(len(read_buffer) - len(delimiter) + 1, 0)
        # Add some more data
        more_data = await receive_stream.receive_some()
        if not more_data:
            raise EOFError()
        read_buffer.extend(more_data)

    # Extract the message
    message_len = terminator_index + len(delimiter)
    if message_len > max_size:
        raise RuntimeError(f"Message too long ({message_len} > {max_size})")
    message = read_buffer[: message_len if return_delimiter else terminator_index]
    # Remove from buffer (using bytearray's optimized delete-from-beginning feature)
    del read_buffer[:message_len]
    return message


async def receive_size_prefixed(
    receive_stream: trio.abc.ReceiveStream,
    read_buffer: bytearray,
    max_size: int,
    **kwargs,  # Added to match params of receive_until
):
    """Reads precisely one size-prefixed message from the given stream.

    This is analogous to receive_until(), but that routine assumes that each message is followed by
    a terminator, whereas this routine assumes that each message is prefixed with the message size.
    A particular benefit of this is that the message can contain any sequence of bytes, whereas
    messages separated by some sort of terminator must not contain the terminator.

    The size prefix must be 4 bytes and little endian (matching protobuf's convention of using
    little endian serialisation).

    :param receive_stream: Stream to read bytes from, using repeated calls to receive_some() method
    :param read_buffer: Intermediate buffer to store data read from stream
    :param max_size: Maximum size, not including size prefix, allowed for messages
    :return: The message read from the stream
    :raises RuntimeError: Message was too long
    :raises EOFError: Stream was closed before a whole message was read
    """
    # Read length prefix
    while len(read_buffer) < 4:
        more_data = await receive_stream.receive_some()
        if not more_data:
            raise EOFError()
        read_buffer.extend(more_data)

    # Decode length prefix
    (message_len,) = struct.unpack("<I", read_buffer[:4])
    if message_len > max_size:
        raise RuntimeError(f"Message too long ({message_len} > {max_size})")
    del read_buffer[:4]

    # Read the message
    while len(read_buffer) < message_len:
        more_data = await receive_stream.receive_some()
        if not more_data:
            raise EOFError()
        read_buffer.extend(more_data)

    # Extract message
    result = read_buffer[:message_len]
    del read_buffer[:message_len]
    return result


class ThreadSafeCancelScope:
    """Like a trio.CancelScope, but can be cancelled from a different thread.

    A typical usage of this class is to create an instance in a parent thread, then use in a child
    thread to wrap all Trio code; that way, when the parent thread cancels the scope, it has the
    effect of stopping the child thread.

    The main reason for this class existing, rather than just using a trio.CancelScope directly, is
    that the cancel() method of trio.CancelScope cannot be directly called from a different thread
    than the one it is being used in. Instead, in the Trio thread you need to record the "trio
    token" and then, in the main thread, use that to call cancel in the Trio thread. This only adds
    a couple of lines of boilerplate but it is enough to be annoying.

    In addition, this class handles the possibilities that cancel() is called before the scope has
    been entered or after it has exited; see the code below for details.
    """

    def __init__(self):
        self.lock = Lock()  # To prevent race condition; see comment in cancel()
        self.scope = trio.CancelScope()
        self.token = None

    def __enter__(self):
        with self.lock:
            assert self.token is None, "Re-entering a ThreadSafeCancelScope is not allowed"
            self.token = trio.lowlevel.current_trio_token()
        return self.scope.__enter__()

    def __exit__(self, exc_t, exc_v, exc_tb):
        return self.scope.__exit__(exc_t, exc_v, exc_tb)

    def cancel(self):
        with self.lock:
            # We lock a mutex here and in __enter__() to prevent the (admittedly very slim) race
            # condition that the cancellation scope is entered between the if condition and cancel()
            # call below (which would be an error because once the scope is entered in one thread
            # it cannot be cancelled from a different thread).
            if self.token is None:
                # Not entered block yet, so can just call cancel() directly in this thread. When
                # the block is entered later, the scope will already be cancelled and so will stop
                # when it reaches the first checkpoint (i.e. await of something) within the block.
                self.scope.cancel()
                return
        try:
            # Block has been entered so need to request cancel scope gets run in Trio thread.
            self.token.run_sync_soon(self.scope.cancel)
        except trio.RunFinishedError:
            # Not only did the block protected by the CancelScope finish, but so did the top-level
            # async function it was contained in (the one passed to trio.run). That is fine, so we
            # just swallow this exception.
            pass


async def _open_tcp_until_successful(host, port, retry_interval_seconds):
    """Repeatedly attempts to connect until successful.

    Attempts an outbound TCP connection, like trio.open_tcp_stream, but retries until success.

    If a connection attempt does not return within the retry interval, it is cancelled and a new
    attempt is immediately started. This is not strictly necessary, as the OS would eventually time
    out the attempt anyway. But, internally, the OS (probably) uses an exponential backoff algorithm
    that does not make much sense when retrying the connection attempt forever as this routine does.
    """
    while True:
        with trio.move_on_after(retry_interval_seconds):
            try:
                return await trio.open_tcp_stream(host, port)
            except OSError:
                await trio.sleep_forever()  # Wait for timeout to expire


async def connect_tcp_repeatedly(handler, host, port, retry_interval_seconds=2):
    """Establishes outbound TCP connections, retrying repeatedly on failure or closure.

    The idea is that this function allows initiating outbound connections with a very similar API
    to accepting incoming connections with trio.serve_tcp: The handler is called whenever a
    connection is available, while this function takes care of establishing the connection(s).

    When the handler returns, this routine gets back to trying and retrying a connection. It does
    not check or enforce that the connection passed to the handler was closed; that is left up to
    the handler.
    """
    while True:
        stream = await _open_tcp_until_successful(host, port, retry_interval_seconds)
        await handler(stream)
