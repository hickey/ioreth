#
# Ioreth - An APRS library and bot
# Copyright (C) 2020  Alexandre Erwin Ittner, PP5ITT <alexandre@ittner.com.br>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import os
import socket
import select
import time
import logging

from .aprs_client import AprsClient
from .ax25 import Frame

logging.basicConfig()
logger = logging.getLogger('iorethd.tcp_kiss_client')

class TcpKissClient(AprsClient):
    FEND = b"\xc0"
    FESC = b"\xdb"
    TFEND = b"\xdc"
    TFESC = b"\xdd"
    DATA = b"\x00"
    FESC_TFESC = FESC + TFESC
    FESC_TFEND = FESC + TFEND

    def __init__(self, addr="localhost", port=8001):
        logger.debug(f'({addr=}, {port=})')

        AprsClient.__init__(self)
        self.addr = addr
        self.port = int(port)
        self._sock = None
        self._inbuf = bytearray()
        self._outbuf = bytearray()
        self._run = False

    def connect(self, timeout=10):
        if self._sock:
            self.disconnect()
        self._inbuf.clear()
        self._outbuf.clear()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(timeout)
        self._sock.connect((self.addr, self.port))
        self._sock.settimeout(None)
        self.on_connect()

    def disconnect(self):
        if self._sock:
            self._sock.close()
            self._sock = None
            self._inbuf.clear()
            self._outbuf.clear()
            self.on_disconnect()

    def is_connected(self):
        return bool(self._sock)

    def setCallsign(self, callsign: str):
        self.callsign = callsign

    def on_recv(self, frame_bytes):
        logger.debug(f'({frame_bytes})')

        frame = Frame.from_kiss_bytes(frame_bytes)
        self.on_recv_frame(frame)

    def on_loop_hook(self):
        logger.debug('()')
        poller = select.poll()
        self._run = True

        will_disconnect = False
        fd = -1
        if self.is_connected():
            fd = self._sock.fileno()
            flags = select.POLLIN | select.POLLHUP | select.POLLERR
            if len(self._outbuf) > 0:
                flags |= select.POLLOUT
            poller.register(fd, flags)

        # Look for incoming packets
        logger.debug('Start polling')
        events = poller.poll(1000)
        logger.debug('Finish polling')

        # Process each event
        for _, evt in events:
            # error in socket connection
            if evt & (select.POLLHUP | select.POLLERR):
                logger.debug('Received disconnect event')
                will_disconnect = True
            # TODO handle POLLRDHUP

            # incoming packet
            if evt & select.POLLIN:
                logger.debug('Received incoming packets')
                rdata = self._sock.recv(2048)
                if len(rdata) == 0:
                    will_disconnect = True
                else:
                    self._inbuf += rdata

            # socket can accept writes
            if evt & select.POLLOUT:
                logger.debug('Received output event')
                nsent = self._sock.send(self._outbuf)
                self._outbuf = self._outbuf[nsent:]

        if fd >= 0:
            logger.debug('Unregister poller')
            poller.unregister(fd)

        # process any packets received
        while len(self._inbuf) > 3:
            logger.debug('Processing received packets')
            # FEND, FDATA, escaped_data, FEND, ...
            if self._inbuf[0] != ord(TcpKissClient.FEND):
                logger.error('Bad frame start')
                raise ValueError("Bad frame start")
            lst = self._inbuf[2:].split(TcpKissClient.FEND, 1)
            if len(lst) > 1:
                self._inbuf = lst[1]
                frame = (
                    lst[0]
                    .replace(TcpKissClient.FESC_TFEND, TcpKissClient.FEND)
                    .replace(TcpKissClient.FESC_TFESC, TcpKissClient.FESC)
                )
                logger.debug('Sending frame to APRS client')
                self.on_recv(frame)

        if will_disconnect:
            self.disconnect()

    def exit_loop(self):
        self._run = False

    def write_frame(self, frame):
        """Send a complete frame."""
        logger.debug(f"({frame=})")

        if type(frame) != Frame:
            logger.error(f"{frame=} is not a ax25.Frame object. Ignoring frame.")
            return

        if not self.is_connected():
            return
        frame_bytes = frame.to_kiss_bytes()
        esc_frame = frame_bytes.replace(
            TcpKissClient.FESC, TcpKissClient.FESC_TFESC
        ).replace(TcpKissClient.FEND, TcpKissClient.FESC_TFEND)
        self._outbuf += (
            TcpKissClient.FEND + TcpKissClient.DATA + esc_frame + TcpKissClient.FEND
        )

    def on_connect(self):
        logger.info("KISS connection connected")

    def on_disconnect(self):
        logger.warning("KISS connection disconnected! Will try again soon...")
        recon = 'sudo systemctl restart ioreth'
        os.system(recon)
