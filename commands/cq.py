
import logging

logging.basicConfig()
logger = logging.getLogger('commands.cq')

from ioreth.ax25 import Frame, APRS_CONTROL_FLD, APRS_PROTOCOL_ID

netlog = None
config = None

class NetLog:

    def __init__(self, logfile: str):
        self.logfile = logfile
        self.fp = open(logfile, 'a+')
        self.checkins = self.read()


    def __del__(self):
        self.fp.close()

    def write(self, sender: str, text: str):
        now = time.strftime("%Y-%m-%d %H:%M:%S %Z")
        self.fp.write(f"{now}|{sender}|{text}\n")
        self.fp.sync()
        self.checkins.append({'time': now, 'station': sender,
                              'message': text})

    def read(self) -> str:
        self.checkins.clear()

        self.fp.seek(0)

        entries = self.fp.readlines()
        for entry in entries:
            ci_time, ci_station, ci_mesg = entry.split('|', 2)
            self.checkins.append({'time': ci_time,
                                  'station': ci_station,
                                  'message': ci_mesg })
        return self.checkins

    def check_for_dup(self, sender, mesg):
        for checkin in self.checkins:
            if checkin['station'].startswith(sender) and
                mesg == checkin['message']:
                return True
        return False


def register(bot_config):
    if not config.has_option('files', 'netlog'):
        logger.error("Can not find netlog setting in files section of config file")
        return

    config = bot_config
    netlog = NetLog(config['files']['netlog'])

    return list(
        {
            'command': 'cq',
            'status': False,
            'help': 'CQ: msg to join net & send msg to all checked in today',
            'cron': '',
        },
    )

def invoke(frame, cmd: str, args: str):
    if cmd == 'cq':
        return do_cq(frame, args)




def do_cq(frame, args):
    # need to do some dup checking on the checkin
    if netlog.check_for_dup(frame.source, args):
        return

    # write another check in to netlog file
    netlog.write(f"{frame.source}/{frame.connection}", args)

    # iterate through the check ins and send a message
    notifications = list(f"You are checked in as {frame.source}")
    for checkin in netlog.checkins:
        dest, conn = checkin['station'].split('/')
        bot_name = config[f'conn.{conn}']['callsign']
        path = config[f'conn.{conn}']['path']
        mesg = f'{frame.source}: {args}'

        notif_frame = Frame(bot_name, dest, path, APRS_CONTROL_FLD,
                            APRS_PROTOCOL_ID, mesg)
        notif_frame.connection = conn
        notifications.append(notif_frame)

    return notifications
