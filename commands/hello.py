

def register(config):
    return { 'command': 'hello',
             'aliases': ['allo', 'nihao'],
             'status': False,
             }

def invoke(frame, args: str):
    return f"hello {frame.source}"

def help():
           #1234567891123456789212345678931234567894123456789512345678961234567
    return "hello/allo/nihao: respond with a greeting"