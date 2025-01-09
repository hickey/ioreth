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
#
# ========
#
# This fork of Ioreth was modified by Angelo N2RAC/DU2XXR to support additional
# functionalities, such as a means to store callsigns from a "net" checkin
# as well as a means to forward messages to all stations checked in for the day
# It is also supported by local cron jobs on my own machine and web server
# to publish the net log on a regular basis.
#
# Pardon my code. My knowledge is very rudimentary, and I only modify or create
# functions as I need them. If anyone can help improve on the code and the
# logic of this script, I would very much appreciate it.
# You may reach me at qsl@n2rac.com or simply APRS message me at DU2XXR-7.
#
# A lot of the items here are still poorly documented if at all. Many also
# rely on some weird or nuanced scripts or directory structures that I have
# maintained on my own machine or server, so bear with me.
# The non-indented comments are mine. The indented ones are by Alexandre.
# A lot of this is trial-and-error for me, so again, please bear with me.
#
# 2024-02-09 0020H

import sys
import time
import logging
import configparser
import os
import re
import random

logging.basicConfig()
logger = logging.getLogger('iorethd.bot')

from cronex import CronExpression
from .aprs_client import AprsClient
from .tcp_kiss_client import TcpKissClient
from . import remotecmd
from . import utils
from .log import BotLog
from os import path
from urllib.request import urlopen, Request
from glob import glob
from importlib import import_module


# These lines below I have added in order to provide a means for ioreth to store
# and retrieve a list of "net" checkins on a daily basis. I did not bother to use
# more intuitive names for the files, but I can perhaps do so in a later code cleanup.


dusubs = "/home/pi/ioreth/ioreth/ioreth/dusubs"
dusubslist = "/home/pi/ioreth/ioreth/ioreth/dusubslist"


class BotAprsHandler:
    def __init__(self, callsign, client):
        #aprs_handler.Handler.__init__(self, callsign=callsign,
        #                      path=client._cfg['aprs']['path'])
        self._client = client

    def on_aprs_message(self, source, addressee, text, origframe, msgid=None, via=None):
        # X*>X*:}WT0F-4>APDR16,TCPIP*,qAC,T2ROMANIA::APRSFL   :Test{13
        # WT0F-4->APRSFL (via X*): (13) Test :: X*>X*:}WT0F-4>APDR16,TCPIP*,qAC,T2ROMANIA::APRSFL   :Test{13
        logger.info(f"{source}->{addressee} (via {via}): ({msgid}) {text} :: {origframe}")
        """Handle an APRS message.

        This may be a directed message, a bulletin, announce ... with or
        without confirmation request, or maybe just trash. We will need to
        look inside to know.
        """

        if addressee.strip().upper() != self.callsign.upper():
            # This message was not sent for us.
            return

        # Remove the end of path char if given a 3rd party packet
        if via:
            via = via.replace('*', '')

        if re.match(r"^(ack|rej)\d+", text):
            # We don't ask for acks, but may receive them anyway. Spec says
            # acks and rejs must be exactly "ackXXXX" and "rejXXXX", case
            # sensitive, no spaces. Be a little conservative here and do
            # not try to interpret anything else as control messages.
            logger.info("Ignoring control message %s from %s", text, source)
            return

#        self.handle_aprs_msg_bot_query(source, text, origframe)
        if msgid:
            # APRS Protocol Reference 1.0.1 chapter 14 (page 72) says we can
            # reject a message by sending a rejXXXXX instead of an ackXXXXX
            # "If a station is unable to accept a message". Not sure if it is
            # semantically correct to use this for an invalid query for a bot,
            # so always acks.
            logger.info("Sending ack to message %s from %s.", msgid, source)
            self.send_aprs_msg(source.replace('*',''), "ack" + msgid, via)

        self.handle_aprs_msg_bot_query(source, text, via, origframe)




class ReplyBot:
    def __init__(self, config_file):
        logger.debug(f"({config_file})")
        self._config_file = config_file
        self._last_config_load = None
        self._handlers = dict()
        self.config = configparser.ConfigParser()
        self.config.optionxform = str # config values are case sensitive
        self.check_updated_config()

        # c = TcpKissClient(self._cfg.get('tnc', 'addr'), self._cfg.getint('tnc', 'port'))
        # c.setHandler(self)

        #self.aprs = BotAprsHandler(self._cfg.get('aprs', 'callsign'), self)
        self._last_blns = time.monotonic()
        self._last_cron_blns = 0
        self._last_status = time.monotonic()
        self._last_reconnect_attempt = 0
        self.remote_cmd = remotecmd.RemoteCommandHandler()

        # setup logs
        #self.netlog = BotLog(f"{self.config['files']['netlog']}-{time.strftime('%Y%m%d')}")
        #self.netmsg = BotLog(f"{self.config['files']['netmsg']}")

        self.register_commands(self.config.get('bot', 'command_dir'))


    def load_config(self):
        logger.debug(f"()")
        try:
            self.config.clear()
            logger.debug(f'reading configuration from {self._config_file}')
            self.config.read(self._config_file)

            # reset when the config was loaded
            self._last_config_load = self._config_mtime()

        except Exception as exc:
            logger.error(exc)

    def check_updated_config(self):
        logger.debug(f"()")
        try:
            if self._last_config_load != self._config_mtime():
                self.load_config()
                logger.info("Configuration reloaded")
        except Exception as exc:
            logger.error(exc)

    def _config_mtime(self) -> int:
        return os.stat(self._config_file).st_mtime

    def connect(self):
        logger.debug('()')
        for sect in [s for s in self.config.sections() if re.match(r'conn\.', s)]:
            conn_name = sect.replace('conn.', '')
            conn_def = dict(self.config.items(sect))

            if conn_def['type'] == 'kiss':
                conn = TcpKissClient(conn_def['host'], conn_def['port'])
                conn.setCallsign(conn_def['callsign'])
                conn.setDestination(conn_def['destination'])
                conn.setPath(conn_def['path'])
                conn.setHandler(self)
                conn.connect()
                self._handlers[conn_name] = conn
            elif conn_def['type'] == 'aprs-is':
                conn = None

            else:
                logger.error(f"{sect} has an invalid type: ignoring connection")
                next



    def register_commands(self, cmd_dir: str):
        logger.debug(f"({cmd_dir})")
        sys.path.append(cmd_dir)

        for cmd_file in glob(f"{cmd_dir}/*.py"):
            base_file = os.path.basename(os.path.splitext(cmd_file)[0])
            try:
                mod = import_module(base_file)
                mod.register()
            except Exception as e:
                logger.error(e)

    def update_bulletins(self):
        logger.debug('()')
        if not self.config.has_section("bulletins"):
            return

        max_age = self.config.getint("bulletins", "send_freq", fallback=600)

        # There are two different time bases here: simple bulletins are based
        # on intervals, so we can use monotonic timers to prevent any crazy
        # behavior if the clock is adjusted and start them at arbitrary moments
        # so we don't need to worry about transmissions being concentrated at
        # some magic moments. Rule-based blns are based on wall-clock time, so
        # we must ensure they are checked exactly once a minute, behaves
        # correctly when the clock is adjusted, and distribute the transmission
        # times to prevent packet storms at the start of minute.

        now_mono = time.monotonic()
        now_time = time.time()

        # Optimization: return ASAP if nothing to do.
        if (now_mono <= (self._last_blns + max_age)) and (
            now_time <= (self._last_cron_blns + 60)
        ):
            return

        bln_map = dict()

        # Find all standard (non rule-based) bulletins.
        keys = self.config.options("bulletins")
        keys.sort()
        std_blns = [
            k for k in keys if k.startswith("BLN") and len(k) > 3 and "_" not in k
        ]

        # Do not run if time was not set yet (e.g. Raspberry Pis getting their
        # time from NTP but before conecting to the network)
        time_was_set = time.gmtime().tm_year > 2000

        # Map all matching rule-based bulletins.
        if time_was_set and now_time > (self._last_cron_blns + 60):
            # Randomize the delay until next check to prevent packet storms
            # in the first seconds following a minute. It will, of course,
            # still run within the minute.
            timestr = time.strftime("%Y%m%d")
            timestrtxt = time.strftime("%m%d")
            filename1 = "/home/pi/ioreth/ioreth/ioreth/netlog-"+timestr

            self._last_cron_blns = 60 * int(now_time / 60.0) + random.randint(0, 30)

            cur_time = time.localtime()
            utc_offset = cur_time.tm_gmtoff / 3600  # UTC offset in hours
            ref_time = cur_time[:5]  # (Y, M, D, hour, min)

            for k in keys:
                # if key is "BLNx_rule_x", etc.
                lst = k.split("_", 3)
                if (
                    len(lst) == 3
                    and lst[0].startswith("BLN")
                    and lst[1] == "rule"
                    and (lst[0] not in std_blns)
                ):
                    expr = CronExpression(self.config.get("bulletins", k))
                    if expr.check_trigger(ref_time, utc_offset):
                        bln_map[lst[0]] = expr.comment

        # If we need to send standard bulletins now, copy them to the map.
        if now_mono > (self._last_blns + max_age):
            self._last_blns = now_mono
            for k in std_blns:
                bln_map[k] = self.config.get("bulletins", k)

        if len(bln_map) > 0:
            to_send = [(k, v) for k, v in bln_map.items()]
            to_send.sort()
            for (bln, text) in to_send:
                logger.info("Posting bulletin: %s=%s", bln, text)
                self.aprs.send_aprs_msg(bln, text)

# These lines are for maintaining the net logs
        if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/netlog'):
            file = open('/home/pi/ioreth/ioreth/ioreth/netlog', 'r')
            data20 = file.read()
            file.close()
            fout = open(filename1, 'a')
            fout.write(data20)
            fout.write(",")
            fout = open(filename3, 'a')
            fout.write(data20)
            fout.write("\n")
            logger.info("Copying latest checkin into day's net logs")
            os.remove('/home/pi/ioreth/ioreth/ioreth/netlog')
            logger.info("Deleting net log scratch file")
            timestrtxt = time.strftime("%m%d")
            file = open(filename1, 'r')
            data5 = file.read()
            file.close()
            if len(data5) > 310 :
                listbody1 = data5[0:58]
                listbody2 = data5[58:121]
                listbody3 = data5[121:184]
                listbody4 = data5[184:247]
                listbody5 = data5[247:310]
                listbody6 = data5[310:]
                self.aprs.send_aprs_msg("BLN3NET", timestrtxt + " 1/6:" + listbody1)
                self.aprs.send_aprs_msg("BLN4NET", "2/6:" + listbody2 )
                self.aprs.send_aprs_msg("BLN5NET", "3/6:" + listbody3 )
                self.aprs.send_aprs_msg("BLN6NET", "4/6:" + listbody4 )
                self.aprs.send_aprs_msg("BLN7NET", "5/6:" + listbody5 )
                self.aprs.send_aprs_msg("BLN8NET", "6/6:" + listbody6 )
            if len(data5) > 247 and len(data5) <= 310 :
                listbody1 = data5[0:58]
                listbody2 = data5[58:121]
                listbody3 = data5[121:184]
                listbody4 = data5[184:247]
                listbody5 = data5[247:310]
                self.aprs.send_aprs_msg("BLN4NET", timestrtxt + " 1/5:" + listbody1)
                self.aprs.send_aprs_msg("BLN5NET", "2/5:" + listbody2 )
                self.aprs.send_aprs_msg("BLN6NET", "3/5:" + listbody3 )
                self.aprs.send_aprs_msg("BLN7NET", "4/5:" + listbody4 )
                self.aprs.send_aprs_msg("BLN8NET", "5/5:" + listbody5 )
            if len(data5) > 184 and len(data5) <= 247 :
                listbody1 = data5[0:58]
                listbody2 = data5[58:121]
                listbody3 = data5[121:184]
                listbody4 = data5[184:]
                self.aprs.send_aprs_msg("BLN5NET", timestrtxt + " 1/4:" + listbody1)
                self.aprs.send_aprs_msg("BLN6NET", "2/4:" + listbody2 )
                self.aprs.send_aprs_msg("BLN7NET", "3/4:" + listbody3 )
                self.aprs.send_aprs_msg("BLN8NET", "4/4:" + listbody4 )
            if len(data5) > 121 and len(data5) <= 184:
                listbody1 = data5[0:58]
                listbody2 = data5[58:121]
                listbody3 = data5[121:]
                self.aprs.send_aprs_msg("BLN6NET", timestrtxt + " 1/3:" + listbody1)
                self.aprs.send_aprs_msg("BLN7NET", "2/3:" + listbody2 )
                self.aprs.send_aprs_msg("BLN8NET", "3/3:" + listbody3 )
            if len(data5) > 58 and len(data5) <= 121:
                listbody1 = data5[0:58]
                listbody2 = data5[58:]
                self.aprs.send_aprs_msg("BLN6NET", timestrtxt + " 1/2:" + listbody1)
                self.aprs.send_aprs_msg("BLN7NET", "2/2:" + listbody2 )
            if len(data5) <= 58:
                self.aprs.send_aprs_msg("BLN6NET", timestrtxt + ":" + data5)
            self.aprs.send_aprs_msg("BLN9NET", "Full logs and more info at https://aprsph.net")
            logger.info("Sending new log text to BLN7NET to BLN8NET after copying over to daily log")

        if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/nettext'):
#           file = open('/home/pi/ioreth/ioreth/ioreth/nettext', 'r')
#           data4 = file.read()
#           file.close()
# Deprecated the lines below. We are now writing the login text directly, since the previous method resulted in
# Simultaneous checkins not being logged properly. The purpose now is to use the nettext file as a flag whether to
# upload the net logs to the web.
#           fout = open('/home/pi/ioreth/ioreth/ioreth/netlog-msg', 'a')
#           fout.write(data4)
#           fout.write("\n")
#           fout.close()
#           logger.info("Copying latest checkin message into cumulative net log")
            os.remove('/home/pi/ioreth/ioreth/ioreth/nettext')
            logger.info("Deleting net text scratch file")
            cmd = 'scp -P 2202 /home/pi/ioreth/ioreth/ioreth/netlog-msg root@irisusers.com:/var/www/html/index.html'
#           cmd = 'scp /home/pi/ioreth/ioreth/ioreth/netlog-msg root@radio1.dx1arm.net:/var/www/aprsph.net/public_html/index.html'
#           cmd = 'scp /home/pi/ioreth/ioreth/ioreth/netlog-msg root@radio1.dx1arm.net:/var/www/html/aprsnet'
            try:
                os.system(cmd)
                logger.info("Uploading logfile to the web")
            except:
                logger.info("ERRIR in uploading logfile to the web")

        if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/aprsthursdaytext'):
            os.remove('/home/pi/ioreth/ioreth/ioreth/aprsthursdaytext')
            logger.info("Deleting aprsthursday net text scratch file")
            cmd = 'scp -P 2202 /home/pi/ioreth/ioreth/ioreth/aprsthursday/index.html root@irisusers.com:/var/www/html/aprsthursday/index.html'
#           cmd = 'scp /home/pi/ioreth/ioreth/ioreth/aprsthursday/index.html root@radio1.dx1arm.net:/var/www/aprsph.net/public_html/aprsthursday/index.html'
#           cmd = 'scp /home/pi/ioreth/ioreth/ioreth/netlog-msg root@radio1.dx1arm.net:/var/www/html/aprsnet'
            try:
                os.system(cmd)
                logger.info("Uploading aprsthursday logfile to the web")
            except:
                logger.info("ERRIR in uploading logfile to the web")

    def update_status(self):
        logger.debug('()')
        if not self.config.has_section("status"):
            return

        max_age = self.config.getint("status", "send_freq", fallback=600)
        now_mono = time.monotonic()
        if now_mono < (self._last_status + max_age):
            return

        self._last_status = now_mono
        #self.remote_cmd.post_cmd(SystemStatusCommand(self._cfg))

    def check_reconnection(self):
        logger.debug('()')
        if self.is_connected():
            return
        try:
            # Server is in localhost, no need for a fancy exponential backoff.
            if time.monotonic() > self._last_reconnect_attempt + 5:
                logger.info("Trying to reconnect")
                self._last_reconnect_attempt = time.monotonic()
                self.connect()
        except ConnectionRefusedError as e:
            logger.warning(e)

    def start(self):
        logger.debug('()')
        while True:
            logger.debug('Starting event loop')
            #AprsClient.on_loop_hook(self)
            self.check_updated_config()
            #self.check_reconnection()
            self.update_bulletins()
            self.update_status()

            # Poll results from external commands, if any.
            while True:
                rcmd = self.remote_cmd.poll_ret()
                if not rcmd:
                    break
                self.on_remote_command_result(rcmd)

            for name, conn in self._handlers.items():
                try:
                    logger.debug(f'Calling connection {name} event loop')
                    conn.on_loop_hook()
                    logger.debug('Event loop returned')
                except Exception as e:
                    logger.error(f"Connection error on {name}: {e}")
                    raise e

            time.sleep(1);

    def on_remote_command_result(self, cmd):
        logger.debug(f"({cmd})")
        logger.debug("ret = %s", cmd)

        if isinstance(cmd, SystemStatusCommand):
            logger.info(f"{cmd.status_str=}")
            self.aprs.send_aprs_status(cmd.status_str)

    def on_message(self, source, dest, text):
        reply = self.process_internal_commands(source, dest, text)

        if not reply:
            reply = self.process_commands(source, dest, text)

        if not reply:
            # send help message
            reply = "Message not understood, please send 'help' for info."

        return reply

    def process_internal_commands(self, source: str, dest: str, text: str):
        """We got an text message direct to us. Handle it as a bot query.
        TODO: Make this a generic thing.

        source: the sender's callsign+SSID
        text: message text.
        """

        sourcetrunc = source.replace('*','')
        parsed_text = text.lstrip().split(" ", 1)
        cmd = parsed_text[0].rstrip().lower()
        args = ''
        if len(parsed_text) == 2:
            args = parsed_text[1]

        timestrtxt = time.strftime("%m%d %H%MZ")

        if '\x00' in args or '<0x' in args :
            logger.info("Message contains null character from APRS looping issue. Stop processing." )
            return

        # # TODO Update for bot name
        # if sourcetrunc == "APRSPH" or sourcetrunc == "ANSRVR" or sourcetrunc == "ID1OT" or sourcetrunc == "WLNK-1" or sourcetrunc == "KP4ASD" or qry[0:3] == "rej" or qry[0:3] == "aa:" or args == "may be unattended" or args =="QTH Digi heard you!" or qry == "aa:message" :
        #     logger.info("Message from ignore list. Stop processing." )
        #     return

        if cmd == 'ping':
            logger.info(f"Handling PING from {source}")
            return timestrtxt + ":Pong! " + args
        elif cmd == 'test':
#                  1234567890123456789012345678901234567890123456789012345678901234567
            return timestrtxt + ":It works! HELP for more commands."
        # elif qry == "?aprst" or qry == "?ping?" or qry == "aprst?" or qry == "aprst" :
        #     tmp_lst = (
        #         origframe.to_aprs_string()
        #         .decode("utf-8", errors="replace")
        #         .split("::", 2)
        #     )
        #     self.send_aprs_msg(sourcetrunc, tmp_lst[0] + ":")
        # elif qry == "version":
        #     self.send_aprs_msg(sourcetrunc, "Python " + sys.version.replace("\n", " "))
        elif cmd == 'about':
            return "APRS bot by WT0F based on ioreth by N2RAC/DU2XXR."
        elif cmd == 'time':
            return "Localtime is " + time.strftime("%Y-%m-%d %H:%M:%S %Z")
        elif cmd in ('help', '?'):
#                                            123456789012345678901234567890123456789012345678901234567890123       4567
            self.send_aprs_msg(sourcetrunc, "CQ [space] msg to join net & send msg to all checked in today /" +timestrtxt)
            self.send_aprs_msg(sourcetrunc, "NET [space] msg to checkin & join without notifying everyone /" +timestrtxt)
            self.send_aprs_msg(sourcetrunc, "LAST/LAST10/LAST15 to retrieve 5/10/15 msgs. ?APRST for path /"+timestrtxt)
            self.send_aprs_msg(sourcetrunc, "?APRSM for the last 10 direct msgs to you. U to leave the net /" +timestrtxt)
            self.send_aprs_msg(sourcetrunc, "MINE for ur last net msgs. SEARCH [spc] phrase to find msgs /" +timestrtxt)
            self.send_aprs_msg(sourcetrunc, "LIST to see today's checkins. https://aprsph.net for more info/"+timestrtxt)

        return None
