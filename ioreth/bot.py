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
from .ax25 import Frame
from .tcp_kiss_client import TcpKissClient
from .aprs_is_client import AprsIsClient
from . import remotecmd
from . import utils
from glob import glob
from importlib import import_module


class ReplyBot:
    def __init__(self, config_file):
        logger.debug(f"({config_file})")
        self._config_file = config_file
        self._last_config_load = None
        self._handlers = dict()
        self.config = configparser.ConfigParser()
        self.config.optionxform = str # config values are case sensitive
        self.check_updated_config()

        # enable Sentry error capturing if DSN is specified
        if self.config.get('bot', 'sentry_dsn'):
            import sentry_sdk
            sentry_sdk.init(dsn=self.config.get('bot', 'sentry_dsn'))

        #self.aprs = BotAprsHandler(self._cfg.get('aprs', 'callsign'), self)
        self._last_blns = time.monotonic()
        self._last_cron_blns = 0
        self._last_status = time.monotonic()
        self._last_reconnect_attempt = 0
        self.remote_cmd = remotecmd.RemoteCommandHandler()

        # setup logs
        #self.netlog = BotLog(f"{self.config['files']['netlog']}-{time.strftime('%Y%m%d')}")
        #self.netmsg = BotLog(f"{self.config['files']['netmsg']}")

        # discover additional commands added to command_dir directory
        self._extra_commands = dict()
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
                conn.conn_name = conn_name
                conn.setCallsign(conn_def['callsign'])
                conn.setDestination(conn_def['destination'])
                conn.setPath(conn_def['path'])
                conn.setHandler(self)
                conn.connect()
            elif conn_def['type'] == 'aprs-is':
                conn = AprsIsClient(conn_def['host'], conn_def['port'])
                conn.conn_name = conn_name
                conn.setCallsign(conn_def['callsign'])
                conn.setPasscode(conn_def['passcode'])
                conn.setDestination(conn_def['destination'])
                conn.setPath(conn_def['path'])
                if 'filter' in conn_def:
                    conn.setFilter(conn_def['filter'])
                conn.setHandler(self)
                conn.connect()
            else:
                logger.error(f"{sect} has an invalid type: ignoring connection")
                next

            self._handlers[conn_name] = conn


    def register_commands(self, cmd_dir: str):
        logger.debug(f"({cmd_dir})")
        sys.path.append(cmd_dir)

        logger.info(f"Registering external commands from {cmd_dir}")
        for cmd_file in glob(f"{cmd_dir}/*.py"):
            base_file = os.path.basename(os.path.splitext(cmd_file)[0])
            try:
                logger.debug(f'Registering {base_file}')
                mod = import_module(base_file)
                if hasattr(mod, 'logger'):
                    mod.logger.level = logger.level
                infos = mod.register(self.config)

                for info in infos:
                    logger.info(f"Registered command: {info['command']}")
                    info['module'] = mod
                    self._extra_commands[info['command']] = info
                    if 'alias' in info:
                        for also in info['alias']:
                            self._extra_commands[also] = info

            except Exception as e:
                logger.error(f"Exception when registering {info['command']}")
                logger.exception(e)
                if logger.level == logging.DEBUG:
                    raise e

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
                for (name, conn) in self._handlers.items():
                    logger.info(f"Posting bulletin: {bln}='{text}' to {name}")
                    conn.send_aprs_msg(bln, text)

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
            #self.update_status()

            # Poll results from external commands, if any.
            while True:
                rcmd = self.remote_cmd.poll_ret()
                if not rcmd:
                    break
                self.on_remote_command_result(rcmd)

            for (name, conn) in self._handlers.items():
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

    def on_message(self, frame):
        logger.debug(f'({frame=})')
        reply = self.process_internal_commands(frame)

        if reply is None:
            reply = self.process_external_commands(frame)

        if reply is None:
            # send help message
            reply = "Message not understood, please send 'help' for info."

        new_mesgs = [f for f in reply if type(f) == Frame]
        for msg in new_mesgs:
            # send the msg out the approriate connection
            logger.info(f'sending to {msg.dest}: {msg.info}')
            self._handlers[msg.connection].write_frame(msg)

        # return the replies to just the originating station
        if type(reply) == str:
            return reply
        else:
            return [f for f in reply if type(f) == str]

    def process_internal_commands(self, frame):
        """We got an text message direct to us. Handle it as a bot query.
        TODO: Make this a generic thing.

        source: the sender's callsign+SSID
        text: message text.
        """

        addressee, cmd, args = self._unpack_message(frame)
        timestrtxt = time.strftime("%m%d %H%MZ")

        if '\x00' in args or '<0x' in args :
            logger.info("Message contains null character from APRS looping issue. Stop processing." )
            return

        # # TODO Update for bot name
        # if sourcetrunc == "APRSPH" or sourcetrunc == "ANSRVR" or sourcetrunc == "ID1OT" or sourcetrunc == "WLNK-1" or sourcetrunc == "KP4ASD" or qry[0:3] == "rej" or qry[0:3] == "aa:" or args == "may be unattended" or args =="QTH Digi heard you!" or qry == "aa:message" :
        #     logger.info("Message from ignore list. Stop processing." )
        #     return

        if cmd == 'ping':
            logger.info(f"Handling PING from {frame.source}")
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
            return f"Localtime is {time.strftime("%Y-%m-%d %H:%M:%S %Z")}"
        elif cmd in ('help', '?'):
            help_text = [
                'ABOUT: Send info about this bot',
                'TIME: Send the current local time',
                'PING: Ping the bot and receive back a pong'
            ]

            # gather help lines from commands
            for name in self._extra_commands.keys():
                if 'help' in self._extra_commands[name]:
                    help_text.append(self._extra_commands[name]['help'])
            return help_text

        return None

    def process_external_commands(self, frame):
        addressee, cmd, args = self._unpack_message(frame)

        if cmd in self._extra_commands:
            info = self._extra_commands[cmd]
            return info['module'].invoke(frame, cmd, args)

    def _unpack_message(self, frame):
        info = frame.info.decode('utf-8', errors='backslashreplace').lstrip()

        if info[0] == ':':
            # standard APRS message
            parts = info.split(':')
            addressee = parts[1].strip()
            text = re.split(r'\s+', parts[2].strip(), 1)
            cmd = text[0].lower()
            args = ''
            if len(text) == 2:
                args = text[1]

            return (addressee, cmd, args)

        return (None, '', '')
