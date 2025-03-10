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

import aprslib
import time
import logging
import socket       # necessary for short term fix

from .aprs_client import AprsClient
from .ax25 import Frame

logging.basicConfig()
logger = logging.getLogger('iorethd.aprs_is_client')

class AprsIsClient(AprsClient):

    def __init__(self, addr="rotate.aprs.net", port=14580):
        logger.debug(f'({addr=}, {port=})')

        AprsClient.__init__(self)
        self.addr = addr
        self.port = int(port)
        self.filter = ''
        self._connection = None

    def connect(self):
        self._connection = aprslib.IS(self.callsign, passwd=self.passcode,
                                      host=self.addr, port=self.port)
        self._connection.set_filter(self.filter)
        self._connection.connect()
        #self._connection.consumer(self.on_recv, raw=True)
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

        frame = Frame.from_aprs(aprslib_frame['raw'].encode('ASCII'))
        self.on_recv_frame(frame)

    def on_loop_hook(self):
        logger.debug('()')

        # short term fix untit aprslib gets patched
        # ref: https://github.com/rossengeorgiev/aprs-python/pull/92
        try:
            self._connection.consumer(self.on_recv, blocking=False)
        except socket.error as e:
            if 'timed out' in str(e):
                pass
        except aprslib.exceptions.ConnectionDrop:
            self.disconnect()
            self.connect()

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

        self._connection.sendall(frame.to_string())

    def on_connect(self):
        logger.info("APRS-IS connection connected")

    def on_disconnect(self):
        logger.warning("APRS-IS connection disconnected! Will try again soon...")

