"""
Local Proxy Relay — resolve o problema de Playwright não suportar SOCKS5 com autenticação.

Funciona assim:
1. Para cada proxy upstream (socks5://user:pass@ip:port), abre uma porta LOCAL sem autenticação.
2. Playwright se conecta ao localhost:PORT_LOCAL (sem auth).
3. O relay repassa TUDO para o proxy upstream (com auth).

Isso usa asyncio puro, sem dependências externas.
"""

import asyncio
import struct
import logging

logger = logging.getLogger("ProxyRelay")


class Socks5Relay:
    """
    Relay local que aceita conexões HTTP CONNECT (de Playwright)
    e as encaminha via SOCKS5 autenticada para o upstream.
    """

    def __init__(self, upstream_host: str, upstream_port: int,
                 username: str, password: str, local_port: int = 0):
        self.upstream_host = upstream_host
        self.upstream_port = upstream_port
        self.username = username
        self.password = password
        self.local_port = local_port  # 0 = auto-assign
        self.server = None
        self.actual_port = None

    async def start(self):
        self.server = await asyncio.start_server(
            self._handle_client, "127.0.0.1", self.local_port
        )
        self.actual_port = self.server.sockets[0].getsockname()[1]
        logger.info(f"Relay listening on 127.0.0.1:{self.actual_port} → "
                     f"socks5://{self.upstream_host}:{self.upstream_port}")
        return self.actual_port

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _handle_client(self, client_reader: asyncio.StreamReader,
                             client_writer: asyncio.StreamWriter):
        """Handle incoming HTTP CONNECT from Playwright."""
        try:
            # Read the HTTP CONNECT request from Playwright
            request_line = await asyncio.wait_for(client_reader.readline(), timeout=10)
            request_str = request_line.decode("utf-8", errors="ignore").strip()

            # Parse CONNECT host:port
            if not request_str.upper().startswith("CONNECT"):
                client_writer.close()
                return

            # CONNECT host:port HTTP/1.1
            parts = request_str.split()
            if len(parts) < 2:
                client_writer.close()
                return

            target = parts[1]  # host:port
            if ":" in target:
                target_host, target_port = target.rsplit(":", 1)
                target_port = int(target_port)
            else:
                target_host = target
                target_port = 443

            # Read remaining headers (and discard)
            while True:
                header_line = await asyncio.wait_for(client_reader.readline(), timeout=5)
                if header_line in (b"\r\n", b"\n", b""):
                    break

            # Connect to upstream SOCKS5 proxy
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(self.upstream_host, self.upstream_port),
                timeout=10
            )

            # SOCKS5 handshake
            success = await self._socks5_handshake(
                upstream_reader, upstream_writer, target_host, target_port
            )

            if not success:
                client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await client_writer.drain()
                client_writer.close()
                upstream_writer.close()
                return

            # Tell Playwright the tunnel is established
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_writer.drain()

            # Now relay data bidirectionally
            await asyncio.gather(
                self._pipe(client_reader, upstream_writer),
                self._pipe(upstream_reader, client_writer),
            )

        except Exception:
            pass
        finally:
            try:
                client_writer.close()
            except:
                pass

    async def _socks5_handshake(self, reader, writer, target_host, target_port) -> bool:
        """Perform SOCKS5 handshake with username/password auth."""
        try:
            # Step 1: Greeting — we support username/password (method 0x02)
            writer.write(b"\x05\x01\x02")
            await writer.drain()

            resp = await asyncio.wait_for(reader.readexactly(2), timeout=10)
            if resp[0] != 0x05 or resp[1] != 0x02:
                return False

            # Step 2: Username/Password authentication
            user_bytes = self.username.encode("utf-8")
            pass_bytes = self.password.encode("utf-8")
            auth_msg = (
                b"\x01"
                + bytes([len(user_bytes)]) + user_bytes
                + bytes([len(pass_bytes)]) + pass_bytes
            )
            writer.write(auth_msg)
            await writer.drain()

            auth_resp = await asyncio.wait_for(reader.readexactly(2), timeout=10)
            if auth_resp[1] != 0x00:
                return False

            # Step 3: Connection request
            # ATYP 0x03 = domain name
            host_bytes = target_host.encode("utf-8")
            connect_msg = (
                b"\x05\x01\x00\x03"
                + bytes([len(host_bytes)]) + host_bytes
                + struct.pack("!H", target_port)
            )
            writer.write(connect_msg)
            await writer.drain()

            # Read response (at least 4 bytes header)
            conn_resp = await asyncio.wait_for(reader.readexactly(4), timeout=10)
            if conn_resp[1] != 0x00:
                return False

            # Read remaining address bytes based on address type
            atyp = conn_resp[3]
            if atyp == 0x01:  # IPv4
                await reader.readexactly(4 + 2)
            elif atyp == 0x03:  # Domain
                domain_len = (await reader.readexactly(1))[0]
                await reader.readexactly(domain_len + 2)
            elif atyp == 0x04:  # IPv6
                await reader.readexactly(16 + 2)

            return True

        except Exception as e:
            logger.debug(f"SOCKS5 handshake failed: {e}")
            return False

    async def _pipe(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Pipe data from reader to writer until EOF."""
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except:
            pass
        finally:
            try:
                writer.close()
            except:
                pass


class ProxyRelayManager:
    """Manages multiple Socks5Relay instances, one per upstream proxy."""

    def __init__(self):
        self.relays: list[Socks5Relay] = []
        self._next_port = 10000

    async def add_relay(self, upstream_host: str, upstream_port: int,
                        username: str, password: str) -> int:
        """
        Start a local relay for the given upstream.
        Returns the local port number.
        """
        relay = Socks5Relay(
            upstream_host=upstream_host,
            upstream_port=upstream_port,
            username=username,
            password=password,
            local_port=0  # OS picks a free port
        )
        local_port = await relay.start()
        self.relays.append(relay)
        return local_port

    async def stop_all(self):
        for relay in self.relays:
            await relay.stop()
        self.relays.clear()
