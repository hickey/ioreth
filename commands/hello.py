

def register(config):
    return [{ 'command': 'hello',
              'alias': ['allo', 'nihao'],
              'status': False,
              'help': 'HELLO|ALLO|NIHAO: respond with a greating'
            }]

def invoke(frame, cmd: str, args: str):
    station = str(frame.source).replace('*', '')
    return f"{cmd} {station}"

