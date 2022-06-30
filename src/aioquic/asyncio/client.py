import asyncio
import ipaddress
import socket
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, Optional, cast

from ..quic.configuration import QuicConfiguration
from ..quic.connection import QuicConnection
from ..tls import SessionTicketHandler
from .protocol import QuicConnectionProtocol, QuicStreamHandler

__all__ = ["connect"]

# keep compatibility for Python 3.7 on Windows
if not hasattr(socket, "IPPROTO_IPV6"):
    socket.IPPROTO_IPV6 = 41


@asynccontextmanager
async def connect(
    host: str,
    port: int,
    *,
    configuration: Optional[QuicConfiguration] = None,
    create_protocol: Optional[Callable] = QuicConnectionProtocol,
    session_ticket_handler: Optional[SessionTicketHandler] = None,
    stream_handler: Optional[QuicStreamHandler] = None,
    wait_connected: bool = True,
    local_port: int = 0,
) -> AsyncGenerator[QuicConnectionProtocol, None]:
    """
    Connect to a QUIC server at the given `host` and `port`.

    :meth:`connect()` returns an awaitable. Awaiting it yields a
    :class:`~aioquic.asyncio.QuicConnectionProtocol` which can be used to
    create streams.

    :func:`connect` also accepts the following optional arguments:

    * ``configuration`` is a :class:`~aioquic.quic.configuration.QuicConfiguration`
      configuration object.
    * ``create_protocol`` allows customizing the :class:`~asyncio.Protocol` that
      manages the connection. It should be a callable or class accepting the same
      arguments as :class:`~aioquic.asyncio.QuicConnectionProtocol` and returning
      an instance of :class:`~aioquic.asyncio.QuicConnectionProtocol` or a subclass.
    * ``session_ticket_handler`` is a callback which is invoked by the TLS
      engine when a new session ticket is received.
    * ``stream_handler`` is a callback which is invoked whenever a stream is
      created. It must accept two arguments: a :class:`asyncio.StreamReader`
      and a :class:`asyncio.StreamWriter`.
    * ``local_port`` is the UDP port number that this client wants to bind.
    """
    loop = asyncio.get_event_loop()
    local_host = "::"

    # if host is not an IP address, pass it to enable SNI
    try:
        ipaddress.ip_address(host)
        server_name = None
    except ValueError:
        server_name = host

    # lookup remote address
#--------ipv4 begin
    #dhlu
    #infos = await loop.getaddrinfo(host, port, type=socket.SOCK_DGRAM)    
    infos = await loop.getaddrinfo(host, port, type=socket.AF_INET)    
    #infos = await loop.getaddrinfo("localhost", port, type=socket.SOCK_DGRAM)
    addr = infos[0][4]
    local_host = addr[0]
    #if len(addr) == 2:
    #    addr = ("::ffff:" + addr[0], addr[1], 0, 0)

    # prepare QUIC connection
    if configuration is None:
        configuration = QuicConfiguration(is_client=True)
    if configuration.server_name is None:
        configuration.server_name = server_name
    connection = QuicConnection(
        configuration=configuration, session_ticket_handler=session_ticket_handler
    )

    # explicitly enable IPv4/IPv6 dual stack
    #dhlu
    #sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    completed = False
    try:
        #sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        #sock.bind((local_host, 8280, 0, 0))#v6 ip=::1         
        sock.bind(("127.0.0.1",8280))
#--------ipv4 end
        completed = True
    finally:
        if not completed:
            sock.close()
    # connect
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: create_protocol(connection, stream_handler=stream_handler),
        sock=sock,
    )
    protocol = cast(QuicConnectionProtocol, protocol)
    try:
        protocol.connect(addr)
        if wait_connected:
            await protocol.wait_connected()
        yield protocol
    finally:
        protocol.close()
        await protocol.wait_closed()
        transport.close()
