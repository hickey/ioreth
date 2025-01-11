

def register(config):
    return { 'command': 'hello',
             'aliases': ['allo', 'nihao'],
             'status': False,
             'help': 'HELLO|ALLO|NIHAO: respond with a greating'
             }

def invoke(frame, cmd: str, args: str):
    return f"hello {frame.source}"

