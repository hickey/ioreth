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

import time
import logging

from .ax25 import Frame, Address, APRS_CONTROL_FLD, APRS_PROTOCOL_ID

logging.basicConfig()
logger = logging.getLogger('iorethd.aprs_client')


class AprsClient:
    """Handle parsing and generation of APRS packets.
    """

    DEFAULT_PATH = "WIDE1-1,WIDE2-2"
    DEFAULT_DESTINATION = "APZIOR"

    def __init__(self):
        self.path = None
        self.destination = None
        self.handler = None
        self.conn_name = None

    def setDestination(self, dest: str):
        self.destination = dest

    def setPath(self, path: str):
        self.path = path

    def setHandler(self, handler):
        self.handler = handler

    def send_frame_bytes(self, frame_bytes):
        try:
            logger.info("SEND: %s", frame_bytes.hex())
            self.write_frame(frame_bytes)
        except Exception as exc:
            logger.warning(exc)

    def on_recv_frame(self, frame):
        """ Handle an AX.25 frame and look for APRS data packets.
        """
        logger.debug(f'({frame=})')

        # set the connection name on the frame so it can be determined
        # later on how to route replies
        frame.connection = self.conn_name

        if frame.info == b"":
            # No data.
            return

        via = None
        if frame.info[0] == ord(b"}"):
            # Got a third-party APRS packet, check the payload.
            # PP5ITT-10>APDW15,PP5JRS-15*,WIDE2-1:}PP5ITT-7>APDR15,TCPIP,PP5ITT-10*::PP5ITT-10:ping 00:01{17

            # This is tricky: according to the APRS Protocol Reference 1.0.1,
            # chapter 17, the path may be both in TNC-2 encoding or in AEA
            # encoding. So these both are valid:
            #
            # S0URCE>DE5T,PA0TH,PA1TH:payload
            # S0URCE>PA0TH>PA1TH>DE5T:payload
            #
            # We are only using the source and payload for now so no worries,
            # but another parser will be needed if we want the path.
            #
            # Of course, I never saw one of these EAE paths in the wild.

            frame.via = frame.source.to_string()
            eae_path = frame.info[1:].split(b">", 1)
            if len(eae_path) != 2:
                logger.warning(
                    "Discarding third party packet with no destination. %s",
                    frame.to_aprs().decode("utf-8", errors="replace"),
                )
                return

            # Source address should be a valid callsign+SSID.
            frame.source = eae_path[0].decode("utf-8", errors="replace")
            destpath_payload = eae_path[1].split(b":", 1)

            if len(destpath_payload) != 2:
                logger.warning(
                    "Discarding third party packet with no payload. %s",
                    frame.to_aprs().decode("utf-8", errors="replace"),
                )
                return

            frame.info = destpath_payload[1]

        self.on_aprs_packet(frame)

    # def enqueue_frame(self, frame):
    #     logger.info("AX.25 frame %d: %s", self._frame_cnt, frame.to_aprs())
    #     #self.enqueue_frame_bytes(frame.to_kiss_bytes())
    #     self.enqueue_frame_bytes(frame.to_aprs())

    # def enqueue_frame_bytes(self, data_bytes):
    #     logger.info("AX.25 frame %d enqueued for sending", self._frame_cnt)
    #     self._snd_queue.append((self._frame_cnt, data_bytes))
    #     self._frame_cnt += 1

    # def dequeue_frame_bytes(self):
    #     now = time.monotonic()
    #     if now < (self._snd_queue_last + self._snd_queue_interval):
    #         return
    #     self._snd_queue_last = now
    #     if len(self._snd_queue) > 0:
    #         num, frame_bytes = self._snd_queue.pop(0)
    #         logger.info("Sending queued AX.25 frame %d", num)
    #         logger.info(frame_bytes)
    #         self.send_frame_bytes(frame_bytes)

    # def on_loop_hook(self):
    #     self.dequeue_frame_bytes()

    def make_frame(self, data, via=None):
        """Shortcut for making a AX.25 frame with a APRS packet with the
        known (mostly constant) information and 'data' as the contents.
        """
        return Frame(
            Address.from_string(self.callsign),
            Address.from_string(self.destination),
            [Address.from_string(s) for s in self.path.split(",")],
            APRS_CONTROL_FLD,
            APRS_PROTOCOL_ID,
            data,
            via,
        )

    def make_aprs_msg(self, to_call, text, via=None):
        """Make an APRS message packet sending 'text' to 'to_call'.
        """
        addr_msg = ":" + to_call.ljust(9, " ") + ":" + text
        return self.make_frame(addr_msg.encode("utf-8"), via)

    def make_aprs_status(self, status, via=None):
        """Make an APRS status packet.
        """
        return self.make_frame((">" + status).encode("utf-8"), via)

    def send_aprs_msg(self, to_call, text, via=None):
        logger.debug(f"({to_call}, {text}, {via})")
        self.write_frame(self.make_aprs_msg(to_call, text, via=via))

    def send_aprs_status(self, status, via=None):
        logger.debug(f"({status}, {via})")
        self.write_frame(self.make_aprs_status(status, via=via))

    def on_aprs_packet(self, frame):
        """A APRS packet was received, possibly through a third-party forward.

        This code runs *after* the search for third-party packets. The
        default implementation will call a more specialized callback for
        known data types. Users can override this for specialized parsing
        if required.

        origframe: the original ax25.Frame
        source: the sender's callsign as a string.
        payload: the APRS data as bytes.
        via: None is not a third party packet; otherwise is the callsign of
             the forwarder (as a string).
        """
        logger.debug(f'({frame=})')

        if frame.info == b"":
            self.on_aprs_empty(frame)
            return
        data_type = frame.info[0]
        if data_type == ord(b":"):
            self.on_aprs_message(frame)
        elif data_type == ord(b">"):
            self.on_aprs_status(frame)
        elif data_type == ord(b";"):
            self.on_aprs_object(frame)
        elif data_type == ord(b")"):
            self.on_aprs_item(frame)
        elif data_type == ord(b"?"):
            self.on_aprs_query(frame)
        elif data_type == ord(b"<"):
            self.on_aprs_capabilities(frame)
        elif data_type == ord(b"!"):
            self.on_aprs_position_wtr(frame)
        elif data_type == ord(b"@"):
            self.on_aprs_position_ts_msg(frame)
        elif data_type == ord(b"="):
            self.on_aprs_position_msg(frame)
        elif data_type == ord(b"/"):
            self.on_aprs_position_ts(frame)
        elif data_type == ord(b"T"):
            self.on_aprs_telemetry(frame)
        elif data_type == ord(b"`"):
            self.on_aprs_mic_e(frame)
        elif data_type == ord(b"'"):
            self.on_aprs_old_mic_e(frame)
        else:
            self.on_aprs_others(frame)

    def on_aprs_empty(self, frame):
        """APRS empty packet (no payload). What can we do with this?! Just
        log the sending station as alive?
        """
        logger.debug(f"({frame=})")
        pass

    def on_aprs_message(self, frame=None):
        """Parse APRS message packet (data type: :)

        This may be a directed message, a bulletin, announce ... with or
        without confirmation request, or maybe just trash. We will need to
        look inside to know.
        """
        logger.debug(f"({frame=})")

        data_str = frame.info.decode("utf-8", errors="replace")

        addressee_text = data_str[1:].split(":", 1)
        if len(addressee_text) != 2:
            logger.warning("Bad addressee:text pair: %s", addressee_text)
            return
        addressee = addressee_text[0].strip()
        text_msgid = addressee_text[1].rsplit("{", 1)
        text = text_msgid[0]
        msgid = None
        if len(text_msgid) == 2:
            # This message is asking for an ack.
            msgid = text_msgid[1]

            logger.info(f"Sending ack to message {msgid} from {frame.source}.")
            self.send_aprs_msg(frame.source.to_string().replace('*',''), "ack" + msgid, frame.via)
            frame.info = f":{addressee:9}:{text}".encode()

        logger.info(f"Message from {frame.source}:{text}")
        response = self.handler.on_message(frame)
        logger.debug(f"{response=}")

        # response is allowed to come back as multiple messages
        if type(response) == list:
            for r in response:
                logger.debug(f'sending {response=}')
                self.send_aprs_msg(str(frame.source), r, frame.via)
        else:
            self.send_aprs_msg(str(frame.source), response, frame.via)

    def on_aprs_status(self, frame=None):
        """APRS status packet (data type: >)
        """
        logger.debug(f"({frame=})")
        pass

    def on_aprs_object(self, frame=None):
        """Object packet (data type: ;)
        """
        logger.debug(f"({frame=})")
        pass

    def on_aprs_item(self, frame=None):
        """Object packet (data type: ))
        """
        logger.debug(f"({frame=})")
        pass

    def on_aprs_query(self, frame=None):
        """APRS query packet (data type: ?)
        """
        logger.debug(f"({frame=})")
        pass

    def on_aprs_capabilities(self, frame=None):
        """Station capabilities packet (data type: <)
        """
        logger.debug(f"({frame=})")
        pass

    def on_aprs_position_wtr(self, frame=None):
        """Position without timestamp no APRS messaging, or Ultimeter
        2000 WX Station (data type: !)

        This mix-up with weather data is pure madness.

        eg.
        PP5JRS-15>APBK20,WIDE1-1,WIDE2-1:!2630.96S/04903.24W#digipeater de Jaragua do Sul - SC
        PP5JR-15>APNU3B,WIDE1-1,WIDE3-3:!2741.46S/04908.89W#PHG7460/REDE SUL APRS BOA VISTA RANCHO QUEIMADO SC
        PY5CTV-13>APTT4,PP5BAU-15*,PP5JRS-15*:! Weather Station ISS Davis Morro do Caratuva - PR
        """
        logger.debug(f"({frame=})")
        pass

    def on_aprs_position_ts_msg(self, frame=None):
        """Position with timestamp (with APRS messaging) (data type: @)

        eg.
        PP5JR-13>APRS,PP5JR-15*,PP5JRS-15*:@092248z2741.47S/04908.88W_098/011g014t057r000p000P000h60b07816.DsVP
        """
        logger.debug(f"({frame=})")
        pass

    def on_aprs_position_msg(self, frame=None):
        """Position without timestamp with APRS messaging (data type: =)

        eg.
        PY5TJ-12>APBK,PY5CTV-13*,WIDE1*,PP5JRS-15*:=2532.12S/04914.18WkTelemetria: 14.6v 25*C 56% U. Rel
        """
        logger.debug(f"({frame=})")
        pass

    def on_aprs_position_ts(self, frame=None):
        """Position with timestamp, no APRS messaging (data type: /)
        """
        logger.debug(f"({frame=})")
        pass

    def on_aprs_telemetry(self, frame=None):
        """Telemetry packet (data type: T)
        """
        logger.debug(f"({frame=})")
        pass

    def on_aprs_mic_e(self, frame=None):
        """APRS Mic-E packet, current (data type: `)
        """
        logger.debug(f"({frame=})")
        pass

    def on_aprs_old_mic_e(self, frame=None):
        """APRS Mic-E packet, old (data type: ')
        """
        logger.debug(f"({frame=})")
        pass

    def on_aprs_others(self, frame=None):
        """All other APRS data types (possibly unknown)
        """
        logger.debug(f"({frame=})")
        pass
