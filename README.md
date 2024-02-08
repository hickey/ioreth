
# About

Ioreth is a **very experimental** APRS bot. There is a lot f things to be
done yet, including writing the documentation. For now, you are welcome to
use it as you want.

Note that transmitting on the usual APRS ham bands requires (at least) an
Amateur Radio license and additional conditions and limitations for this
particular mode of operation may apply on your country or region. You MUST
ensure compliance with your local regulations before transmitting, but all
other uses are only subjected to the GNU GPLv3+ (see license bellow).

Connecting this program to the APRS-IS network also requires a license as
you will be, effectively, operating remote transmitters through the Internet.




# License

Copyright (C) 2020  Alexandre Erwin Ittner, PP5ITT <alexandre@ittner.com.br>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.





# Contact information

Author: Alexandre Erwin Ittner   (callsign: PP5ITT)

Email: <alexandre@ittner.com.br>

Web: <https://www.ittner.com.br>



# Additional notes from Angelo DU2XXR / N2RAC

This fork of Ioreth was modified by Angelo DU2XXR / N2RAC to support additional
functionalities, such as a means to store callsigns from a "net" checkin
as well as a means to forward messages to all stations checked in for the day
It is also supported by local cron jobs on my own machine and web server
to publish the net log on a regular basis.
 
Pardon my code. My knowledge is very rudimentary, and I only modify or create
functions as I need them. If anyone can help improve on the code and the
logic of this script, I would very much appreciate it.
You may reach me at qsl@n2rac.com or simply APRS message me at DU2XXR-7.

A lot of the items here are still poorly documented if at all. Many also
rely on some weird or nuanced scripts or directory structures that I have
maintained on my own machine or server, so bear with me.
The non-indented comments are mine. The indented ones are by Alexandre.
A lot of this is trial-and-error for me, so again, please bear with me.

The net currently runs at <https://aprsph.net>. You may interact with the bot by sending APRS messages with APRSPH as the addressee.

The group chat/CQ log is at <https://aprsph.net/cq>.

# Supported bot commands

- **CQ [space] your message** to send a message to everyone checked in for the day. This also adds you to the net log, and you will subsequently receive any CQ messages received by APRSPH thereafter. Subsequent CQ messages will also be sent to everyone in the list.
- **NET [space] your message** will quietly join you into the daily net. This will not alert everyone in the net, but your message will be logged below. The message is optional. Sending NET without a message after will still log your callsign into the net and the recipient list.
- **LIST** to view the current day's list of checked-in stations.
- **LAST** to see the last 5 messages (use LAST10 for 10 messages or LAST15 for 15 messages).
- **MINE** to view the recent CQ/NET messages sent by your own station to the net in the current month. You may include a callsign-ssid to review the last messages sent by that station (e.g., MINE DU2XXR-7). Use MINE10 or MINE15 for 10 or 15 messages, respectively.
- **SEARCH [space] word or phrase** to find the last 5 messages from the month that contain the word or phrase. SEARCH10 or SEARCH15 to fetch 10 or 15 messages, respectively
- **?APRST** or ?PING? to get a message with the path/s your packet took to the bot.
- **?APRSM** or MSG to retrieve the last 5 messages sent to your callsign+ssid, using the aprs.fi API. Add a callsign-ssid after to retrieve messages directed to that callsign. Example: ?APRSM DU2XXR-7
- **HELP** for a list of other commands.
- **IC** - Set of commands that let the user draft a longer piece of message (multiple lines), then publish these onto a web log and simultaneously sent to a pre-designated station and/or email. 
- **SMS (space) XXXXXXXXXXX (space) Message** - Sends a text message the the number XXXXXXXXXXX along with the message. This supports replies or new messages from SMS users by sending @CALLSIGN-SSID to the gateway number. Currently, the script supports numbers in the Philippines, since that is where I operate. This requires gammu-smsd daemon. Some modems might have issue processing received messages, but I have found that setting AT+CNMI to 1,2,0,0 works.
- **SMSALIAS (space) XXXXXXXXXXX (space) Message** - Sets an alias so that the SMS recipient/sender number will no longer appear in subsequent messages.
- **?APRST** or **?PING?** returns the path taken by the user's current ping message to the bot. 
- **TIME** returns the machine's current time.
- **VERSION** returns the python version.
- **HELP** returns a list of commands.
- Commands to run server-side commands are also supported.
- 
# Changelog

- 2023-01-28: Added the ?APRSM feature, which lets users retrieve their last 5 messages from aprs.fi.
- 2023-02-02: Improved handling of longer messages in relay and retrieval (pagination into 2 messages so it is not truncated)
- 2023-03-26: Page now refreshes every 10 minutes. APRSPH also automatically advises all checked in stations that the net is about to restart.
- 2023-03-29: Improved reply for CQ and NET messages to include timestamp to better handle clients that ignore duplicate messages (because our messages don't have msgID).
- 2023-04-04: Added UNSUBSCRIBE command.
- 2023-04-12: Added queries for retrieving #APRSThursday entries. Also improved the MINE, SEARCH commands to cover current month plus archives.
- 2023-04-16: Throttled self ?APRSM to 1 query per 5 minutes, since a duplicate query will result in a different response set every time because the responses will now be the last messages received. Update: Changed to 30 minutes, as of 2023-05-04.
- 2023-06-05: Minor fix to the SMSALIAS code to accommodate for extra spaces which results in no match.
- 2023-06-30: Fixes to the back-end code to deal with looping messages and garbage characters from igates that cause looping.
- 2023-07-04: Added support for ?APRSP and ?APRSS commands.
- 2023-09-04: Edits to replace brackets to avoid HTML tags in log
- 2024-01-11: Changed relay mechanism to include original callsign and SSID as the sender instead of APRSPH. Started to support direct logging of APRSThursday net without ANSRVR relay.

More updated commands and instructions at https://aprsph.net.

# Contact information
- **Email**: info@aprsph.net
- **Telegram**: jangelor
- **Web**: <https://aprsph.net>
- **APRS**: DU2XXR-7
