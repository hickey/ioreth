
import logging
import time
import re

logging.basicConfig()
logger = logging.getLogger('commands.cq')

from ioreth.ax25 import Address, Frame, APRS_CONTROL_FLD, APRS_PROTOCOL_ID

netlog = None
config = None

class NetLog:
    """
    NetLog class keeps track of an active net and can provide statistics
    about the net.

    The net is recorded to a file named 'netlog-' with the net name
    appended to it. This allows muliple nets to be operating at the same
    time.

    The format for the netlog file is as follows:

        2025-02-06 10:48:57 EST|KB9LEB/tnc|73 FROM JACK IN NSB FL

    There are three primary fields seperated by the pipe '|' symbol:
    date time, station and message. The station is further divided into
    callsign and connection name (here conn.tnc from the config file)
    with a slash '/' separating the two values. If a station checks in
    multiple times with different messages, then there will be mulitple
    entries in the netlog file.

    Internally the full netlog file is kept in memory as the `checkin`
    attribute of the netlog instance. The `checkin` attribute is an
    array of hash maps with the value of each field available. The keys
    to the hash map are `time`, `station`, `via` and `message`.

    When a station checks out of the net using the `unsubscribe` command,
    a netlog entry is created with the message '*UNSUBSCRIBE*'.

    """
    def __new__(cls, logfile=None):
        if not hasattr(cls, 'instance'):
            cls.instance = super(NetLog, cls).__new__(cls)
            cls.logfile = logfile
            cls.fp = open(logfile, 'a+')

            # first we need to initialize checkins and then read the values
            cls.checkins = []
            cls.checkins = cls.instance.read()
        return cls.instance

    def __del__(self):
        self.fp.close()

    def write(self, sender: str, text: str):
        now = time.strftime("%Y-%m-%d %H:%M:%S %Z")
        self.fp.write(f"{now}|{sender}|{text}\n")
        self.fp.flush()
        self.checkins.append({'time': now, 'station': sender,
                              'message': text})

    def read(self) -> str:
        self.checkins.clear()

        self.fp.seek(0)

        entries = self.fp.readlines()
        for entry in entries:
            ci_time, ci_source, ci_mesg = entry.split('|', 2)
            ci_station, ci_via = ci_source.split('/', 2)
            ci_mesg = ci_mesg.replace('\n', '')
            self.checkins.append({'time': ci_time,
                                  'station': ci_station,
                                  'via': ci_via,
                                  'message': ci_mesg })
        return self.checkins

    def check_for_dup(self, sender, mesg):
        for checkin in self.checkins:
            if checkin['station'].startswith(sender) and mesg == str(checkin['message']):
                return True
        return False

    def current_checkins(self):
        callsigns = {}
        for entry in self.checkins:
            if entry['station'] in callsigns and entry['message'] == '*UNSUBSCRIBE*':
                del callsigns[entry['station']]
                continue
            callsigns[entry['station']] = entry['via']

        return callsigns

    def checkin_count(self):
        return len(self.current_checkins())


def register(bot_config):
    global config, netlog

    if not bot_config.has_option('files', 'netlog'):
        logger.error("Can not find netlog setting in files section of config file")
        return

    config = bot_config
    netlog = NetLog(config['files']['netlog'])

    return [{ 'command': 'cq',
              'status': False,
              'help': 'CQ: msg to join net & send msg to all checked in today',
              'cron': '',
            },
            { 'command': 'net',
              'status': False,
              'help': 'NET: quietly join the net',
              'cron': '',
            },
            { 'command': 'list',
              'status': False,
              'help': 'LIST: respond with a list of net checkins',
              'cron': '',
            },
            { 'command': 'unsubscribe',
              'status': False,
              'help': 'UNSUBSCRIBE|UNSUB|U: check out of the net & stop checking notifications',
              'cron': '',
              'alias': ['u', 'unsub'],
            }]

def invoke(frame, cmd: str, args: str):
    logger.debug(f"({frame=}, {cmd=}, {args=})")
    if cmd == 'cq':
        return do_cq(frame, args)
    elif cmd == 'net':
        return do_net(frame, args)
    elif cmd == 'list':
        return do_list(frame, args)
    elif cmd in ['unsubscribe', 'unsub', 'u']:
        return do_unsubscribe(frame, args)


def do_cq(frame, args):
    logger.debug(f"({frame=}, {args=})")
    global config, netlog

    # need to do some dup checking on the checkin
    station = str(frame.source).replace('*', '')  # Checkin sent with no path
    if netlog.check_for_dup(station, args):
        return ''

    # write another check in to netlog file
    notifications = do_net(frame, args)

    # iterate through the check ins and send a message
    checkins = netlog.current_checkins()
    for receiver, via in checkins.items():
        # we don't need to send notification to the source
        if not receiver == station:
            bot_name = Address.from_string(config[f'conn.{via}']['callsign'])
            dest = Address.from_string(config[f'conn.{via}']['destination'])
            mesg = f':{receiver:9}:{station}: {args}'.encode('ASCII')
            path = []
            for p in config[f'conn.{via}']['path'].split(','):
                path.append(Address.from_string(p))

            notif_frame = Frame(bot_name, dest, path, APRS_CONTROL_FLD,
                                APRS_PROTOCOL_ID, mesg)
            notif_frame.connection = via
            notifications.append(notif_frame)
    return notifications

def do_net(frame, args):
    logger.debug(f"({frame=}, {args=})")
    global config, netlog

    # need to do some dup checking on the checkin
    station = str(frame.source).replace('*', '')  # Checkin sent with no path
    if netlog.check_for_dup(station, args):
        return ''

    # write another check in to netlog file
    netlog.write(f"{station}/{frame.connection}", args)

    # iterate through the check ins and send a message
    notifications = [f"You are checked in as {station}"]

    return notifications

def do_list(frame, args):
    logger.debug(f"({frame=}, {args=})")
    global netlog

    # gather a list of checkins and response with list of callsigns
    responses = []
    message = ''
    for checkin in netlog.current_checkins():
        # add comma between callsigns
        if message:
            message += ','
        # Remove the connection information
        message += checkin
        if len(message) >= 60:
            responses.append(message)
            message = ''
    responses.append(message)

    return responses


def do_unsubscribe(frame, args):
    logger.debug(f"({frame=}, {args=})")
    global netlog

    station = str(frame.source).replace('*', '')
    netlog.write(f"{station}/{frame.connection}", '*UNSUBSCRIBE*')

    return 'You have checked out of the net'

