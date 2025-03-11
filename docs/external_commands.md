External Commands
=================

End users can create their own commands to integrate into ioreth. The
command needs to be written in Python and placed in the `commands`
directory. The Python script is required to implement two functions:

    - register
    - invoke

Register function
-----------------

The Python script is required to implement the `register` function with
the following signature:

    register(bot_config: configparser): list

The purpose of this function is to provide a definition of the command
to the bot infrastructure and allow the command to perform any initialization
that needs to be accomplished. The `register` function needs to return
a list of dictionaries which have the form of:

    {
        'command': 'unsubscribe',
        'status': False,
        'help': 'UNSUBSCRIBE|UNSUB|U: check out of the net & stop checking notifications',
        'cron': [],
        'alias': ['u', 'unsub'],
    }

Most of these fields should be self explanatory but the following
discussion should clear up any questions concerning the use of the
fields.

### command (Required)

This is the text that qualifies as how to invoke the command. If you have
aliases for the command, they should be specified using the `alias` field.

### help (Required)

This is the help test that is sent to the user when the `help` command
is received by the bot. The length of the text should not be more than
63 characters.

### status

If the command needs to inject APRS status packets then the `status`
field needs to be set to `True`. This feature is still currently in
development.

### alias

If the command should also be known as other commands, then the additional
commands need to be listed in the `alias` field.

### cron

If the command needs to have any scheduled or periodic tasks then they
need to be declared in the `cron` field. The field accepts a list of
strings. Each string consists of a Python `cronex` expression (summarized
in the `aprsbot-sample.conf`). At the designated time that the `cronex`
expression has specified, the function `periodic()` will be called with
command portion of the `cronex` expression.


Invoke function
---------------

The Python script is required to implement the `invoke` function with
the following signature:

    invoke(frame: ax25.Frame, cmd: str, args: str): list

The `invoke` function will be called every time that the bot receives an
APRS message packet with the command (or any aliases) as the first word.
The `invoke` function will receive a copy of the actual AX.25 frame in
case there needs to be more interrogation into the frame. In addition,
the function receives the original command sent and everything after the
command as the `args` parameter.

The `invoke` function should return a list of messages to send to APRS.
Each entry of the list of messages can take on of two forms: a string
and an ax25.Frame. The string form should be no longer than 63 characters
and the message will be sent to the original station that sent the message
with the command. The ax25.Frame form allows the command to construct any
APRS packet and send it.


Periodic function
-----------------

The `periodic` function gets called when a registered `cronex` expression
is triggered. The function will take a single string as shown by the
following signature:

    periodic(func: str): list

The `func` parameter is the command portion of the `cronex` expression
so the `periodic` function must examine the parameter if there are multiple
`cronex` expressions registered to determine which expression is being
triggered.

The `periodic` function has the option to a list of ax25.Frame objects
that will be sent as APRS packets.
