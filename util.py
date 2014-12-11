from untwisted.network import get_event, spawn
from untwisted.utils.stdio import DumpFile

def get_env(header):
    environ = {
                'REQUEST_METHOD':'POST',
                'CONTENT_LENGTH':header['Content-Length'],
                'CONTENT_TYPE':header['Content-Type']
              }

    return environ


OPEN_FILE_ERR = get_event()
def drop(spin, filename):
    try:
        fd = open(filename, 'rb')             
    except IOError as excpt:
        err = excpt.args[0]
        spawn(spin, OPEN_FILE_ERR, err)
    else:
        DumpFile(spin, fd)



