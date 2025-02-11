
import logging
import time

logging.basicConfig()
logger = logging.getLogger('commands.cq')

from ioreth.ax25 import Address, Frame, APRS_CONTROL_FLD, APRS_PROTOCOL_ID

netlog = None
config = None

class NetLog:

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
            ci_time, ci_station, ci_mesg = entry.split('|', 2)
            ci_mesg = ci_mesg.replace('\n', '')
            self.checkins.append({'time': ci_time,
                                  'station': ci_station,
                                  'message': ci_mesg })
        return self.checkins

    def check_for_dup(self, sender, mesg):
        for checkin in self.checkins:
            if checkin['station'].startswith(sender) and mesg == str(checkin['message']):
                return True
        return False


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
            }]

def invoke(frame, cmd: str, args: str):
    logger.debug(f"({frame=}, {cmd=}, {args=})")
    if cmd == 'cq':
        return do_cq(frame, args)
    elif cmd == 'net':
        return do_net(frame, args)
    elif cmd == 'list':
        return do_list(frame, args)





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
    recipients = []
    for checkin in netlog.checkins:
        receiver, conn = checkin['station'].split('/')
        if not((receiver == station) or (receiver in recipients)):
            # we don't need to send notification to the source
            # or a station we have already sent to
            bot_name = Address.from_string(config[f'conn.{conn}']['callsign'])
            dest = Address.from_string(config[f'conn.{conn}']['destination'])
            mesg = f':{receiver:9}:{station}: {args}'.encode('ASCII')
            path = []
            for p in config[f'conn.{conn}']['path'].split(','):
                path.append(Address.from_string(p))

            notif_frame = Frame(bot_name, dest, path, APRS_CONTROL_FLD,
                                APRS_PROTOCOL_ID, mesg)
            notif_frame.connection = conn
            notifications.append(notif_frame)

            # add to list so we don't send duplicate messages
            recipients.append(receiver)
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
    global config, netlog

    # gather a list of checkins and response with list of callsigns
    responses = []
    message = ''
    for checkin in netlog.read():
        if message:
            message += ','
        message += checkin['station']
        if len(message) >= 60:
            responses.push(message)
            message = ''
    responses.push(message)

    return responses







#         elif qry == "netremind" :
#            lines = []
#            sourcetrunc = source.replace('*','')
#            with open(filename3) as sendlist:
#                 lines = sendlist.readlines()
#            count = 0
#            for line in lines:
#                 linetrunc = line.replace('\n','')
#                 count += 1
#                 strcount = str(count)
#                 timestrtxt = time.strftime("%m%d")
# #                                   1234567890123456789012345678901234567890123456789012345678901234567
# #                msgbody = timestrtxt + " This is a test message from the aprsph net manager."
#                 msgbody = timestrtxt + " net is restarting soon. Checkin again after 0000Z to rejoin."
#                 self.send_aprs_msg(linetrunc, msgbody )
#                 logger.info("Reminding %s that net will restart soon.", linetrunc)



#         elif qry in ["cq", "hi", "hello", "happy","ga", "gm", "ge", "gn", "good", "gud", "gd", "ok", "j", "thanks", "tu", "tnx", "73", "greetings" ]:
#            timestrtxt = time.strftime("%m%d %H%MZ")
#            sourcetrunc = source.replace('*','')
#            argsstr1 = args.replace('<','&lt;')
#            argsstr = argsstr1.replace('>','&gt;')
#            cqnet = 0
#            nocheckins = 0
#            dt = datetime.now()
# # Checking if duplicate message
#            dupecheck = qry + " " + args
#            args2 = args.upper()
# #           args2 = args2a.split(' ',1)[0]
#            args3 = args[0:120]
#            if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc) and dupecheck == open('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc).read():
#                   logger.info("Message is exact duplicate, stop logging." )
#                   return
#            if args2 in ["LIST", "LIST ", "LAST", "LAST ", "LAST10", "LAST10 ", "LAST15", "LAST15 ", "HELP", "HELP ", "APRSM?", "APRSM? " ] :
#                         timestrtxt = time.strftime("%m%d:")
#                         logger.info("CQ message is a command. Advising user to use the command without CQ" )
# #                                                                1234567890123456789012345678901234567890123456789012345678901234567
#                         self.send_aprs_msg(sourcetrunc, timestrtxt + "Are u trying to send a command? Try sending without CQ" )
#                         self.send_aprs_msg(sourcetrunc, timestrtxt + "For example:" + args2 + " (without CQ before it)" )
#                         self.send_aprs_msg(sourcetrunc, timestrtxt + "HELP for list of commands. More info at https://aprsph.net." )
# # Changed the few lines below. Even if the user is sending a command as a message, log it anyway, but simply warn them.
# #                        return
# #           else:
#            if args2.split(' ',1)[0] == "HOTG" and dt.isoweekday() == 4 :
# # in ["LIST", "LIST ", "LAST", "LAST ", "LAST10", "LAST10 ", "LAST15", "LAST15 ", "HELP", "HELP ", "APRSM?", "APRSM? " ] :
#                         timestrtxt = time.strftime("%m%d:")
#                         logger.info("Possible APRSThursday checkin. Advise users to send without CQ" )
# #                                                                1234567890123456789012345678901234567890123456789012345678901234567
#                         self.send_aprs_msg(sourcetrunc, timestrtxt + "Trying to checkin APRSThursday? Send HOTG without CQ" )
#                         self.send_aprs_msg(sourcetrunc, timestrtxt + "For example: HOTG [space] Your message here." )
#                         self.send_aprs_msg(sourcetrunc, timestrtxt + "HELP for list of commands. More info at https://aprsph.net." )
#            logger.info("Message is not exact duplicate, now logging" )
# # This logs the message into net text draft for adding into the message log.
#            with open('/home/pi/ioreth/ioreth/ioreth/nettext', 'w') as cqm:
#                        if qry == "cq" :
#                           data9 = "{} {}:{}".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, argsstr)
#                        else :
#                           data9 = "{} {}:{} {}".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, qrynormalcase, argsstr)
#                        cqm.write(data9)
#                        cqm.close()
#                        logger.info("Writing %s CQ message to nettext", sourcetrunc)
#                        self._client.netmsg.write(f"{data9}\n")
#                        logger.info("Writing latest checkin message into cumulative net log")

# # If no checkins, we will check you in and also post your CQ message into the CQ log, and also include in net log
#            if not os.path.isfile(filename3) :
#                nocheckins = 1
#                timestrtxt = time.strftime("%m%d")
#                self.send_aprs_msg(sourcetrunc, "You are first in the day's log for " + timestrtxt + "." )
#                self._client.netlog.write(sourcetrunc)
#                logger.info("Writing %S message to netlog", sourcetrunc)
# # Checking if duplicate message
#                dupecheck = qry + " " + args
#                if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc) and dupecheck == open('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc).read():
#                    logger.info("Message is exact duplicate, stop logging" )
#                    return
#                else:
#                    logger.info("Message is not exact duplicate, now logging" )
#                    timestrtxt = time.strftime("%m%d:")
#                    with open('/home/pi/ioreth/ioreth/ioreth/nettext', 'w') as ntg:
# # If not duplicate, this logs the message into net text draft for adding into the message log.

#                         if qry == "cq" :
#                            data3 = "{} {}:{}".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, argsstr)
#                         else :
#                            data3 = "{} {}:{} {}".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, qrynormalcase, argsstr)
#                         ntg.write(data3)
#                         logger.info("Writing %s net message to netlog-msg", sourcetrunc)
#                         self._client.netmsg.write(f"{data3}\n")
#                         logger.info("Writing latest checkin message into cumulative net log")

#                logger.info("Advising %s to checkin", sourcetrunc)
#                return
# # If not yet in log, add them in and add their message to net log.
#            file = open(filename3, 'r')
#            search_word = sourcetrunc
#            if not (search_word in file.read()):
#                 self._client.netlog.write(sourcetrunc)
#                 logger.info("CQ source not yet in net. Writing %s checkin to netlog", source)

# # Deprecated this part of the net, since CQs now default to the "Net" portion of the checkin (we have unified
# # the checkin between CQ and Net). Perhaps we shall use another keyword for that purpose, since most people are
# # Doing a Net and then a CQ afterward.
# #                with open('/home/pi/ioreth/ioreth/ioreth/nettext', 'w') as ntg:
# #                      if qry == "cq" :
# #                         data3 = "{} {}:{}".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, args)
# #                      else :
# #                         data3 = "{} {}:{} {}".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, qry, args)
# #                      ntg.write(data3)
#                 cqnet = 1
# #                      logger.info("Writing %s net message to netlog-msg", sourcetrunc)
# # Record the message somewhere to check if next message is dupe
#            with open('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc, 'w') as g:
#                 dupecheck = qry + " " + args
#                 g.write(dupecheck)
#                 logger.info("Writing %s message somewhere to check for future dupes", sourcetrunc)

# # Send the message to all on the QRX list for today
#            lines = []
#            timestrtxt = time.strftime("%m%d")
#            sourcetrunc = source.replace('*','')
#            sendfile = "/home/pi/ioreth/ioreth/ioreth/outbox/" + sourcetrunc
#            sendfile2 = "/home/pi/ioreth/ioreth/ioreth/outbox/" + sourcetrunc + "-reply"
#            relay = "cat " + sendfile + " | kissutil"
#            relay2 = "cat " + sendfile2 + " | kissutil"

#            if os.path.isfile(sendfile):
#                 rmsendfile = ("sudo rm "+ sendfile)
#                 os.system(rmsendfile)
#            if os.path.isfile(sendfile2):
#                 rmsendfile2 = ("sudo rm "+ sendfile2)
#                 os.system(rmsendfile2)

#            with open(filename3) as sendlist:
#                 lines = sendlist.readlines()
#            count = 0
#            outboxfile = open(sendfile, 'a')
#            replyfile = open(sendfile2, 'a')
# # 123456789012345678901
#            for line in lines:
#                 linetrunc = line.replace('\n','')
#                 linejust = linetrunc.ljust(9)
#                 count += 1
#                 strcount = str(count)
#                 msgbodycq = sourcetrunc + ":" + args
#                 msgbody = sourcetrunc + ":" + qrynormalcase + " " + args
#                 # TODO Get botname from config
#                 msgbodynewcq = "APRSPH:" + args
#                 msgbodynewcq2 = "APRSPH:" + qrynormalcase + " " + args


# # 123456789012345678901
#                 if not sourcetrunc == linetrunc:
# # Let's try a different logic for sending messages to the QRX list
#                 # TODO Get botname from config
#                       groupreply = "[0] APRSPH>APZIOR,WIDE2-1::" + linejust + ":CQ[spc]msg to group reply.LIST recipients.LAST/LAST10 history " + timestrtxt
# #                      replyfile.write(groupreply)
# #                      replyfile.write("\n")
# # 123456789012345678901
#                       if qry == "cq" :
#                          if len(msgbodycq) > 67 :
#                             msgbody1 = msgbodycq[0:61]
#                             msgbody2 = msgbodycq[61:118]
# #                            self.send_aprs_msg(linetrunc, msgbody1 + "+" )
# #                            self.send_aprs_msg(linetrunc, sourcetrunc + ":+" + msgbody2 )

#                             draft1 = "[0] " + sourcetrunc + ">APZIOR,WIDE2-1::" + linejust + ":" + msgbodynewcq[0:62] + "+"
#                             draft2 = "[0] " + sourcetrunc + ">APZIOR,WIDE2-1::" + linejust + ":" + msgbodynewcq[62:118]




# #                            os.cmd("echo '" + draft1 + "' | kissutil" )
# #                            os.cmd("echo '" + draft2 + "' | kissutil" )


#                             outboxfile.write(draft1)
#                             outboxfile.write("\n")
#                             outboxfile.write(draft2)
#                             outboxfile.write("\n")
#                             outboxfile.write(groupreply)
#                             outboxfile.write("\n")


#                          else:
# #                            self.send_aprs_msg(linetrunc, msgbodycq )

#                             draft1 = "[0] " + sourcetrunc + ">APZIOR,WIDE2-1::" + linejust + ":" + msgbodynewcq
# #                            os.cmd("echo '" + draft1 + "' | kissutil" )
#                             outboxfile.write(draft1)
#                             outboxfile.write("\n")
#                             outboxfile.write(groupreply)
#                             outboxfile.write("\n")




# #                         self.send_aprs_msg(linetrunc, sourcetrunc + ":" + args)
#                       else :
#                          if len(msgbody) > 67 :
#                             msgbody1 = msgbody[0:61]
#                             msgbody2 = msgbody[61:118]
# #                            self.send_aprs_msg(linetrunc, msgbody1 + "+" )
# #                            self.send_aprs_msg(linetrunc, sourcetrunc + ":+" + msgbody2 )

#                             draft1 = "[0] " + sourcetrunc + ">APZIOR,WIDE2-1::" + linejust + ":" + msgbodynewcq2[0:62] + "+"
#                             draft2 = "[0] " + sourcetrunc + ">APZIOR,WIDE2-1::" + linejust + ":" + msgbodynewcq2[62:118]
# #                            os.cmd("echo '" + draft1 + "' | kissutil" )
# #                            os.cmd("echo '" + draft2 + "' | kissutil" )

#                             outboxfile.write(draft1)
#                             outboxfile.write("\n")
#                             outboxfile.write(draft2)
#                             outboxfile.write("\n")
#                             outboxfile.write(groupreply)
#                             outboxfile.write("\n")



#                          else:
# #                            self.send_aprs_msg(linetrunc, msgbody )
#                             draft1 = "[0] " + sourcetrunc + ">APZIOR,WIDE2-1::" + linejust + ":" + msgbodynewcq2
# #                            os.cmd("echo '" + draft1 + "' | kissutil" )

#                             outboxfile.write(draft1)
#                             outboxfile.write("\n")
#                             outboxfile.write(groupreply)
#                             outboxfile.write("\n")


# #                         self.send_aprs_msg(linetrunc, sourcetrunc + ":" + qry + " " + args)
# #                                                    1234567890123456789012345678901234567890123456789012345678901234567
# # Rewrite message with original sender as FROM address
# # 123456789012345678901

#                       logger.info("Sending CQ message to %s except %s", linetrunc, sourcetrunc)
#            outboxfile.close()
#            os.system(relay)

# #           replyfile.close()
# #           os.system(relay2)
#            logger.info("Sending message from %s via Kissutil", sourcetrunc)
# #         except:
# #               logger.info("Error sending message from %s via Kissutil", sourcetrunc)



# #                      self.send_aprs_msg(linetrunc, "CQ[spc]msg to group reply.LIST recipients.LAST/LAST10 history " + timestrtxt  )
# # This reads the day's log from a line-separated list for processing one message at a time.
# # Advise sender their message is being processed/sent
#            dayta2 = self._client.netlog.read()
#            dayta31 = dayta2.replace(sourcetrunc + ',','')
#            dayta3 = dayta31.replace('\n','')
# #           dayta3count = dayta3.count(",")
#            if nocheckins == 1:
#                  self.send_aprs_msg(sourcetrunc, "No CQ recipients yet. You are first in today's log." )
#            else:
#                timestrtxt = time.strftime("%m%d %H%MZ:")
#                if len(dayta3) > 51 :
#                      count = 0
#                      for i in dayta3:
#                          if i == ',':
#                             count = count + 1
# #                                                    12345678901   2345    67            89012345678901234567890123456789012345678901234567
#                      self.send_aprs_msg(sourcetrunc, timestrtxt + "QSP " + str(count) + " stations. LIST for recipients. LAST for history." )
#                elif len(dayta3) < 1:
#                      timestrtxt = time.strftime("%m%d")
#                      self.send_aprs_msg(sourcetrunc, "No other checkins yet. You are first in the log for " + timestrtxt )
#                else:
# #                                                    12345678901   23456789012345678901234567890123456789012345678901234567
#                      self.send_aprs_msg(sourcetrunc, timestrtxt + "QSP "+ dayta3 )
#            logger.info("Advising %s of messages sent to %s", sourcetrunc, dayta3)
#            if cqnet == 1:
#                  timestrtxt = time.strftime("%m%d %H%MZ")
# #                                                 123456789012345678901234        5678901234567890123456789012345678901234567
#                  self.send_aprs_msg(sourcetrunc, "Ur checked in " + timestrtxt + ". QRX pls til 2359Z. U to exit. aprsph.net" )
#                  logger.info("Adivising %s they are also now checked in.", sourcetrunc)



#         elif qry in ["u", "u ", "unsubscribe", "unsubscribe ", "checkout", "checkout ", "leave", "leave ", "exit", "exit "] :
# # == "u" or qry == "unsubscribe" or qry == "checkout" or qry == "leave"  :


# # Checking if already in log
#            with open(filename3, 'r') as file:
#                  timestrtxt = time.strftime("%m%d %H%MZ")
#                  search_word = sourcetrunc
#                  search_replace = search_word + ","
#                  if(search_word in file.read()):
# #                                                      1234567890123456789012345678901234567890123456789012345678901234567
#                       self.send_aprs_msg(sourcetrunc, "Unsubscribing from net " + timestrtxt +". NET or CQ to join again.")
#                       logger.info("Found %s in today's net. Unsubscribing", sourcetrunc)
# # Remove them from the day's list
#                       with open(filename1, 'r') as file1:
#                            filedata = file1.read()
#                            filedata = filedata.replace(search_replace, '')
#                       with open(filename1, 'w') as file1:
#                            file1.write(filedata)

# # Now remove them from the send list
#                       with open(filename3, 'r') as file2:
#                            filedata = file2.read()
#                            sourcen = sourcetrunc + "\n"
#                            filedata = filedata.replace(sourcen, '')
#                       with open(filename3, 'w') as file2:
#                            file2.write(filedata)

#                       file2.close()

#                       with open('/home/pi/ioreth/ioreth/ioreth/nettext', 'w') as g:
#                            data3 = "{} {}:{} [Checked out from the net]".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, args)
#                            g.write(data3)
#                            logger.info("Writing %s unsubscribe and message into netlog text", sourcetrunc)
#                            fout = open('/home/pi/ioreth/ioreth/ioreth/netlog-msg', 'a')
#                            fout.write(data3)
#                            fout.write("\n")
#                            fout.close()
#                            logger.info("Writing unsubscribe message into cumulative log.")



# # If not in log, then add them
#                  else:
#                       timestrtxt = time.strftime("%m%d")
#                       self.send_aprs_msg(sourcetrunc, "Ur not checked in today " + timestrtxt + ". NET or CQ to join the net.")
#                       logger.info("Replying to %s that they are not yet subscribed", sourcetrunc)


#         elif qry in ["net", "check", "checkin", "checking", "checking ",  "joining", "join", "qrx", "k", "check-in", "net "] :
# #  == "net" or qry == "checking" or qry == "check" or qry == "checkin" or qry == "joining" or qry == "join" or qry == "qrx" or qry == "j"  :
#            sourcetrunc = source.replace('*','')
# # Checking if duplicate message
# # If not, write msg to temp file
#            dupecheck = qry + " " + args
#            argsstr1 = args.replace('<','&lt;')
#            argsstr = argsstr1.replace('>','&gt;')
#            if os.path.isfile('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc) and dupecheck == open('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc).read():
#                   logger.info("Message is exact duplicate. Stop logging." )
#                   return
#            else:
# #           if not dupecheck == open('/home/pi/ioreth/ioreth/ioreth/lastmsg').read():
#                   logger.info("Message is not exact duplicate, now logging" )

#                   with open('/home/pi/ioreth/ioreth/ioreth/nettext', 'w') as g:
#                        if qry == "net":
#                           data3 = "{} {}:{} *".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, argsstr)
#                        else:
#                           data3 = "{} {}:{} {} *".format(time.strftime("%Y-%m-%d %H:%M:%S %Z"), sourcetrunc, qrynormalcase, argsstr)
#                        g.write(data3)
#                        logger.info("Writing %s net message to netlog text", sourcetrunc)
#                        fout = open('/home/pi/ioreth/ioreth/ioreth/netlog-msg', 'a')
#                        fout.write(data3)
#                        fout.write("\n")
#                        fout.close()
#                        logger.info("Writing latest checkin message into cumulative net log")




# # Checking if already in log
#            with open(filename3, 'r') as file:
#                  timestrtxt = time.strftime("%m%d %H%MZ")
#                  search_word = sourcetrunc
#                  if(search_word in file.read()):
# #                                                      1234567890123456789012       345678901234567890123456789012345678901234567
#                       self.send_aprs_msg(sourcetrunc, "QSL new msg " + timestrtxt +".CQ[spc]msg,LIST,LAST.Info:HELP or aprsph.net")
#                       logger.info("Checked if %s already logged to prevent duplicate. Skipping checkin", sourcetrunc)
#                       file.close()
# # If not in log, then add them
#                  else:
#                       timestrtxt = time.strftime("%m%d")
#                       with open('/home/pi/ioreth/ioreth/ioreth/netlog', 'w') as f:
#                          f.write(sourcetrunc)
#                          f.close()
#                          logger.info("Writing %s checkin to netlog", source)
#                       if args == "":
# #                                                         1234567890123456789012345678901234567890123456789012345678901234567
#                          self.send_aprs_msg(sourcetrunc, "U may also add msg.CQ[spc]msg.LAST for history.LIST for recipients")
# #                      else:
# #                                                      1234567890123          4    5678          9012345678901234567890123456789012345678901234567
#                       self.send_aprs_msg(sourcetrunc, "QSL " + sourcetrunc + " " + timestrtxt + ". LAST view history. LIST recipients. U to leave")
# #                                                      123456789012345678901           2345678901234567890123456789012345678901234567
#                       self.send_aprs_msg(sourcetrunc, "Stdby 4 msgs til "+timestrtxt+ " 2359Z.CQ[spc]msg QSP. Info:HELP or aprsph.net" )
#                       logger.info("Replying to %s checkin message", sourcetrunc)

# # Record the message somewhere to check if next message is dupe
#            dupecheck = qry + " " + args
#            with open('/home/pi/ioreth/ioreth/ioreth/lastmsgdir/' + sourcetrunc, 'w') as g:
#                 lasttext = args
#                 g.write(dupecheck)
#                 logger.info("Writing %s message somewhere to check for future dupes", sourcetrunc)
#                 g.close()

#         elif qry == "list" or qry == "?aprsd" or qry == "qni" :
#            sourcetrunc = source.replace('*','')
#            timestrtxt = time.strftime("%m%d")
#            if os.path.isfile(filename1):
#                  file = open(filename1, 'r')
#                  data21 = file.read()
#                  data2 = data21.replace('\n','')
#                  file.close()

#                  if len(data2) > 373:
#                        listbody1 = data2[0:58]
#                        listbody2 = data2[58:121]
#                        listbody3 = data2[121:184]
#                        listbody4 = data2[184:247]
#                        listbody5 = data2[247:310]
#                        listbody6 = data2[310:]
#                        self.send_aprs_msg(sourcetrunc, timestrtxt + " 1/7:" + listbody1 )
#                        self.send_aprs_msg(sourcetrunc, "2/7:" + listbody2 )
#                        self.send_aprs_msg(sourcetrunc, "3/7:" + listbody3 )
#                        self.send_aprs_msg(sourcetrunc, "4/7:" + listbody4 )
#                        self.send_aprs_msg(sourcetrunc, "5/7:" + listbody5 )
#                        self.send_aprs_msg(sourcetrunc, "6/7:" + listbody6 )
#                        self.send_aprs_msg(sourcetrunc, "7/7:+More stations. Refer https://aprsph.net for today's full log." )
# #                       self.send_aprs_msg(sourcetrunc, "CQ[space]text to join & msg all in today's net. Info: aprsph.net" )
# #                                                       1234567890123456789012345678901234567890123456789012345678901234567
#                        logger.info("Replying with stations heard today. Exceeded length so split into 7 and advised to go to website: %s", data2 )
#                  if len(data2) > 310 and len(data2) <=373 :
#                        listbody1 = data2[0:58]
#                        listbody2 = data2[58:121]
#                        listbody3 = data2[121:184]
#                        listbody4 = data2[184:247]
#                        listbody5 = data2[247:310]
#                        listbody6 = data2[310:]
#                        self.send_aprs_msg(sourcetrunc, timestrtxt + " 1/6:" + listbody1 )
#                        self.send_aprs_msg(sourcetrunc, "2/6:" + listbody2 )
#                        self.send_aprs_msg(sourcetrunc, "3/6:" + listbody3 )
#                        self.send_aprs_msg(sourcetrunc, "4/6:" + listbody4 )
#                        self.send_aprs_msg(sourcetrunc, "5/6:" + listbody5 )
#                        self.send_aprs_msg(sourcetrunc, "6/6:" + listbody6 )
# #                       self.send_aprs_msg(sourcetrunc, "CQ[space]text to join & msg all in today's net. Info: aprsph.net" )
# #                                                       1234567890123456789012345678901234567890123456789012345678901234567
#                        logger.info("Replying with stations heard today. Exceeded length so split into 6: %s", data2 )
#                  if len(data2) > 247 and len(data2) <= 310 :
#                        listbody1 = data2[0:58]
#                        listbody2 = data2[58:121]
#                        listbody3 = data2[121:184]
#                        listbody4 = data2[184:247]
#                        listbody5 = data2[247:310]
#                        self.send_aprs_msg(sourcetrunc, timestrtxt + " 1/5:" + listbody1 )
#                        self.send_aprs_msg(sourcetrunc, "2/5:" + listbody2 )
#                        self.send_aprs_msg(sourcetrunc, "3/5:" + listbody3 )
#                        self.send_aprs_msg(sourcetrunc, "4/5:" + listbody4 )
#                        self.send_aprs_msg(sourcetrunc, "5/5:" + listbody5 )
# #                       self.send_aprs_msg(sourcetrunc, "CQ[space]text to join & msg all in today's net. Info: aprsph.net" )
# #                       self.send_aprs_msg(sourcetrunc, "Send CQ +text to msg all in today's log. Info: aprsph.net" )
#                        logger.info("Replying with stations heard today. Exceeded length so split into 5: %s", data2 )
#                  if len(data2) > 184 and len(data2) <= 247 :
#                        listbody1 = data2[0:58]
#                        listbody2 = data2[58:121]
#                        listbody3 = data2[121:184]
#                        listbody4 = data2[184:]
#                        self.send_aprs_msg(sourcetrunc, timestrtxt + " 1/4:" + listbody1 )
#                        self.send_aprs_msg(sourcetrunc, "2/4:" + listbody2 )
#                        self.send_aprs_msg(sourcetrunc, "3/4:" + listbody3 )
#                        self.send_aprs_msg(sourcetrunc, "4/4:" + listbody4 )
# #                       self.send_aprs_msg(sourcetrunc, "CQ[space]text to join & msg all in today's net. Info: aprsph.net" )
# #                       self.send_aprs_msg(sourcetrunc, "Send CQ +text to msg all in today's log. Info: aprsph.net" )
#                        logger.info("Replying with stations heard today. Exceeded length so split into 4: %s", data2 )
#                  if len(data2) > 121 and len(data2) <= 184:
#                        listbody1 = data2[0:58]
#                        listbody2 = data2[58:121]
#                        listbody3 = data2[121:]
#                        self.send_aprs_msg(sourcetrunc, timestrtxt + " 1/3:" + listbody1 )
#                        self.send_aprs_msg(sourcetrunc, "2/3:" + listbody2 )
#                        self.send_aprs_msg(sourcetrunc, "3/3:" + listbody3 )
# #                       self.send_aprs_msg(sourcetrunc, "CQ[space]text to join & msg all in today's net. Info: aprsph.net" )
# #                       self.send_aprs_msg(source, "Send CQ +text to msg all in today's log. Info: aprsph.net" )
#                        logger.info("Replying with stations heard today. Exceeded length so split into 3: %s", data2 )
#                  if len(data2) > 58 and len(data2) <= 121:
#                        listbody1 = data2[0:58]
#                        listbody2 = data2[58:]
#                        self.send_aprs_msg(sourcetrunc, timestrtxt + " 1/2:" + listbody1 )
#                        self.send_aprs_msg(sourcetrunc, "2/2:" + listbody2 )
# #                       self.send_aprs_msg(sourcetrunc, "CQ[space]text to join & msg all in today's net. Info: aprsph.net" )
# #                       self.send_aprs_msg(sourcetrunc, "Send CQ +text to msg all in today's log. Info: aprsph.net" )
#                        logger.info("Replying with stations heard today. Exceeded length so split into 2: %s", data2 )
#                  if len(data2) <= 58:
#                        self.send_aprs_msg(sourcetrunc, timestrtxt + ":" + data2 )
# #                       self.send_aprs_msg(sourcetrunc, "CQ[space]text to join & msg all in today's net. Info: aprsph.net" )
# #                       self.send_aprs_msg(sourcetrunc, "Send CQ +text to msg all in today's log. Info: aprsph.net" )
#                        logger.info("Replying with stations heard today: %s", data2 )
# #                                                 1234567890123456789012345678901234567890123456789012345678901234567
#                  self.send_aprs_msg(sourcetrunc, "CQ[space]msg to join/chat. LAST for msg log. Info: aprsph.net" )
#            else:
#                  self.send_aprs_msg(sourcetrunc, "No stations checked in yet. CQ[space]msg to checkin.")

# # START ?APRSM or MESSAGE retrieval from aprs.fi. This feature uses the API to retrieve the last 10 messages and delivers to the user.
# # May be useful for checking for any missed messages.


# # First we test the output file
#         elif qry in ["?aprsm", "?aprsm ", "msg", "msg ", "m", "m ", "?aprsm5", "aprsm10", "aprsm5 ", "aprsm10 ", "msg5", "msg5 ", "msg10", "msg10 ", "m5", "m5 ", "m10", "m10 "] :
# # == "?aprsm" or qry == "msg" or qry == "m" or qry == "msg10" or qry == "m10" or qry == "?aprsm10" :
#            sourcetrunc = source.replace('*','')
#            timestrtxt = time.strftime("%m%d")
# # Let's throttle the response to once per 5 minutes. Otherwise, receiving the same query in rapid succession could result in varied sets of responses.
#            dupecheck = "/home/pi/ioreth/ioreth/ioreth/aprsm/" + sourcetrunc
#            if os.path.isfile(dupecheck) and args =="" :
# #                                               1234567890123456789012345678901234567890123456789012345678901234567
#                self.send_aprs_msg(sourcetrunc, "?APRSM queries for own callsign+ssid limited to 1x per 30min. " +timestrtxt )
#                logger.info("%s already made an ?APRSM query recently. Throttling response.", sourcetrunc)
#                return
#            if args == "" :
#                 callsign = sourcetrunc
#                 with open(dupecheck, 'w') as file:
#                      file.write("")
#                      logger.info("Adding a dupecheck to throttle responses for %s", sourcetrunc)

# # .split('-', 1).upper()
#            else:
#                 callsign = args.split(' ', 1)[0].upper()
#             # TODO get aprsfi token from config
#            apicall = "https://api.aprs.fi/api/get?what=msg&dst=" + callsign + "&apikey=" +  aprsfiapi + "&format=json"
# #           jsonoutput = "/home/pi/ioreth/ioreth/ioreth/aprsm/" + sourcetrunc + ".json"
# #           msgoutput = "/home/pi/ioreth/ioreth/ioreth/aprsm/" + sourcetrunc + ".txt"
# #           cmd = "wget \"" + apicall + "\" -O " + jsonoutput
#            try:
# #               hdr = { 'User-Agent' : 'Ioreth APRSPH bot (aprsph.net)' }
# #               req = urllib.request.Request(apicall, headers=hdr, timeout=2)
# #               response = urllib.request.urlopen(req).read().decode('UTF-8')
# #               hdr = "'user-agent': 'APRSPH/2023-01-28b (+https://aprsph.net)'"
# # TODO get bot name from config
#                hdr = { 'User-Agent': 'Ioreth APRSPH bot (https://aprsph.net)' }
# #               response = urllib.request.urlopen(apicall, timeout=2).read().decode('UTF-8')
#                req = urllib.request.Request(url=apicall, headers={'User-Agent':' APRSPH/2023-01-29 (+https://aprsph.net)'})
# # Mozilla/5.0 (Windows NT 6.1; WOW64; rv:12.0) Gecko/20100101 Firefox/12.0'})
#                response = urllib.request.urlopen(req, timeout=5).read().decode('UTF-8')
# #               response = urllib.request.urlopen(apicall, timeout=2).read().decode('UTF-8')
# #               response.add_header('User-Agent','APRSPH/2023-01-28 (+https://aprsph.net)')
#                jsonResponse = json.loads(response)

#            except:
#                self.send_aprs_msg(sourcetrunc, "Error in internet or connection to aprs.fi.")
# #               logger.info("%s", response)
# #               logger.info("%s", jsonResponse)

#                logger.info("Internet error in retrieving messages for %s", callsign)
#                return

#            if jsonResponse['found'] == 0:
#                    self.send_aprs_msg(sourcetrunc, "No recent msgs for " + callsign + " or old data was purged.")
#                    logger.info("No messages retrieved for %s", callsign)
#                    return
#            else:
# #                   logger.info("%s", response)
# #                   logger.info("%s", jsonResponse)
#                    timestrtxt = time.strftime("%m%d %H%MZ")

#                    count = 0
#                    for rows in jsonResponse['entries']:
# #                         logger.info("%s", rows)
# # Uncomment below to limit ?aprsm output to 5 messages and ?aprsm10 to 10. Otherwise, it generates 10 by default.
#                          if count == 5 and qry in ["m5", "msg5", "?aprsm5", "m5 ", "msg5 ", "?aprsm5 "] :
# # == "m" or qry == "msg" or qry == "?aprsm" :
#                             break
#                          count += 1
#                          msgtime = datetime.fromtimestamp(int(rows['time'])).strftime('%m-%d %H%MZ')
#                          msgsender = rows['srccall']
#                          msgmsg = rows['message']
#                          strcount = str(count)
#                          msgbody = strcount + "." + msgtime + " " + msgsender + ":" + msgmsg
#                          if len(msgbody) > 67 :
#                             msgbody1 = msgbody[0:61]
#                             msgbody2 = msgbody[61:]
#                             self.send_aprs_msg(sourcetrunc, msgbody1 + "+" )
#                             self.send_aprs_msg(sourcetrunc, strcount + ".+" + msgbody2 )
#                          else:
#                             self.send_aprs_msg(sourcetrunc, msgbody )

# #                         self.send_aprs_msg(sourcetrunc, str(count) + ".From " + msgsender + " sent on " + msgtime )
# #                         self.send_aprs_msg(sourcetrunc, str(count) + "." + msgmsg )
# #                                                              123456789012345678901234567       8901234567890123456789012345678901234567
#                    self.send_aprs_msg(sourcetrunc, str(count) + " latest msgs to " + callsign + " retrieved from aprs.fi on " + timestrtxt )
#                    logger.info("Sending last messages retrieved for %s", callsign)

# # Deprecated code below. You might want to refer to it in future for other functions.
# #           try:
# #              os.system(cmd)
# #              logger.info("Retrieved last messages for %s", sourcetrunc)
# #           except:
# #              logger.info("ERROR retrieving last messages from aprs.fi")
# #              self.send_aprs_msg(sourcetrunc, "Error retrieving latest msgs from aprs.fi. Try again later.")
# #              return

# # Now we parse the file
# #           with open(jsonoutput, 'r') as file:
# #                messages = json.load(file)
# #           with open(msgoutput, 'w') as msgfile:
# #                for rows in messages:


# #                time1 = datetime.datetime.fromtimestamp(int(messages['entries'][0]["time"])).strftime('%Y-%m-%d %H:%M:%S UTC')
# #                time2 = datetime.datetime.fromtimestamp(int(messages['entries'][1]["time"])).strftime('%Y-%m-%d %H:%M:%S UTC')
# #                time3 = datetime.datetime.fromtimestamp(int(messages['entries'][2]["time"])).strftime('%Y-%m-%d %H:%M:%S UTC')
# #                time4 = datetime.datetime.fromtimestamp(int(messages['entries'][3]["time"])).strftime('%Y-%m-%d %H:%M:%S UTC')
# #                time5 = datetime.datetime.fromtimestamp(int(messages['entries'][4]["time"])).strftime('%Y-%m-%d %H:%M:%S UTC')
# #                sender1 = messages['entries'][0]["srccall"]
# #                sender2 = messages['entries'][1]["srccall"]
# #                sender3 = messages['entries'][2]["srccall"]
# #                sender4 = messages['entries'][3]["srccall"]
# #                sender5 = messages['entries'][4]["srccall"]
# #                msg1 = messages['entries'][0]["message"]
# #                msg2 = messages['entries'][1]["message"]
# #                msg3 = messages['entries'][2]["message"]
# #                msg4 = messages['entries'][3]["message"]
# #                msg5 = messages['entries'][4]["message"]

# #                msgfile.write("1.Msg from " + sender1 + " sent on " + time1 + "\n")
# #                msgfile.write("1." + msg1 + "\n")
# #                msgfile.write("2.Msg from " + sender2 + " sent on " + time2 + "\n")
# #                msgfile.write("2." + msg2 + "\n")
# #                msgfile.write("3.Msg from " + sender3 + " sent on " + time3 + "\n")
# #                msgfile.write("3." + msg3 + "\n")
# #                msgfile.write("4.Msg from " + sender4 + " sent on " + time4 + "\n")
# #                msgfile.write("4." + msg4 + "\n")
# #                msgfile.write("5.Msg from " + sender5 + " sent on " + time5 + "\n")
# #                msgfile.write("5." + msg5)
# #                msgfile.close()
# #                logger.info("Saved message file for %s", sourcetrunc)

# # Now we return the list of messages retrieved from APRS.fi
# #                self.send_aprs_msg(sourcetrunc, "Last 5 messages to " + sourcetrunc + " retrieved from aprs.fi." )
# #                with open(msgoutput, 'r') as msgfile:
# #                    lines = msgfile.readlines()
# #                    msgfile.close()
# #                                                1234567890123456789012345678901234567890123456789012345678901234567

# #                    count = 0
# #                    for line in lines:
# #                          linetrunc = line.replace('\n','')
# #                          if linetrunc == "":
# #                             self.send_aprs_msg(sourcetrunc, "No recent msgs to display, or old data has been purged.")
# #                             logger.info("Nomessages retrieved for %s", sourcetrunc)
# #                             return
# #                          count +=1
# #                          self.send_aprs_msg(sourcetrunc, linetrunc[0:67])
# #                    logger.info("Sending last 5 aprs-is messages retrieved for %s", sourcetrunc)

# #                msgfile.write("6." + messages['entries'][5]["srccall"] + ":" + messages['entries'][5]["message"] + "\n")
# #                msgfile.write("7." + messages['entries'][6]["srccall"] + ":" + messages['entries'][6]["message"] + "\n")
# #                msgfile.write("8." + messages['entries'][7]["srccall"] + ":" + messages['entries'][7]["message"] + "\n")
# #                msgfile.write("9." + messages['entries'][8]["srccall"] + ":" + messages['entries'][8]["message"] + "\n")
# #                msgfile.write("10." + messages['entries'][9]["srccall"] + messages['entries'][9]["message"] + "\n")
# #                msgfile.write("\n")


