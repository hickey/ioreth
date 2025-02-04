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

import logging
import serial

from .aprs_client import AprsClient
from .ax25 import Frame

logging.basicConfig()
logger = logging.getLogger('iorethd.serial_client')

class SerialClient(AprsClient):
    FEND = b"\xc0"
    FESC = b"\xdb"
    TFEND = b"\xdc"
    TFESC = b"\xdd"
    DATA = b"\x00"
    FESC_TFESC = FESC + TFESC
    FESC_TFEND = FESC + TFEND

    def __init__(self, device, speed):
        logger.debug(f'({device=}, {speed=})')

        AprsClient.__init__(self)
        self.device = device
        self.speed = int(speed)
        self.filter = ''
        self._connection = None

    def connect(self):
        self._connection = serial.Serial(self.device, self.speed, timeout=0)
        self._connection.set_filter(self.filter)
        self.on_connect()

    def disconnect(self):
        if self._connection:
            self._connection.close()
            self.on_disconnect()

    def is_connected(self):
        return bool(self._connection)

    def setCallsign(self, callsign: str):
        self.callsign = callsign

    def setPasscode(self, passcode: str):
        self.passcode = passcode

    def setFilter(self, filter: str):
        self.filter = filter

    def on_recv(self, aprslib_frame):
        logger.debug(f'({aprslib_frame=})')

        frame = Frame.from_kiss_bytes(frame_bytes)
        self.on_recv_frame(frame)

    def on_loop_hook(self):
        logger.debug('()')

        buf = self._connection.read(256)
        if buf:
            self.on_recv(buf)

        # if will_disconnect:
        #     self.disconnect()

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
            SerialClient.FESC, SerialClient.FESC_TFESC
        ).replace(SerialClient.FEND, SerialClient.FESC_TFEND)
        self._outbuf += (
            SerialClient.FEND + SerialClient.DATA + esc_frame + SerialClient.FEND
        )

    def on_connect(self):
        logger.info("APRS-IS connection connected")

    def on_disconnect(self):
        logger.warning("APRS-IS connection disconnected! Will try again soon...")

