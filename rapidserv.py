""" 
This file implements an abstraction for the http protocol over the server side perspective. 
"""

from tempfile import TemporaryFile as tmpfile
from untwisted.network import *
from untwisted.utils.stdio import Stdin, Stdout, Server, DumpFile, DUMPED, DUMPED_FILE, lose, LOAD, ACCEPT, CLOSE
from untwisted.utils.stdio import DumpFile

from socket import *
from os.path import getsize
from mimetypes import guess_type
from os.path import isfile, join, abspath, basename
from traceback import print_exc as debug

class RapidServ(object):
    """
    The rapidserv class is used to instantiate the server instance with
    handles.
    """

    def __init__(self, port, backlog):
        sock = socket(AF_INET, SOCK_STREAM)
        sock.bind(('', port))
        sock.listen(backlog)

        local = Spin(sock)
        Server(local) 
        
        xmap(local, ACCEPT, self.handle_accept)
        
        # The web apps.
        self.setup = []

    def add_handle(self, handle, *args, **kwargs):
        self.setup.append(lambda spin: handle(spin, *args, **kwargs))
    
    def handle_accept(self, local, client):
        Stdin(client)
        Stdout(client)

        HttpServer(client)
        Get(client)
        Post(client)

        # It serves to determine whether the client made
        # a request whose resource exists.
        # In case it didnt the connection is dropped.
        client.ACTIVE = False

        for ind in self.setup:
            ind(client)

        xmap(client, CLOSE, lambda con, err: lose(con))

class Get(object):
    """ 
    """

    def __init__(self, spin):
        xmap(spin, 'GET', self.tokenizer)

    def tokenizer(self, spin, header, fd, resource, version):
        """ Used to extract encoded data with get. """

        # from urlparse import parse_qs
        # query = parse_qs(data)
        # index = query['index'][0]

        data = ''
        if '?' in resource:
            resource, data = resource.split('?', 1)
            
        spawn(spin, 'GET %s' % resource, header, fd, data, version)

class Post(object):
    """ 
    """

    def __init__(self, spin):
        xmap(spin, 'POST', self.tokenizer)

    def tokenizer(self, spin, header, fd, resource, version):
        spawn(spin, 'POST %s' % resource, header, fd, version)

class HttpServer:
    def __init__(self, spin, MAX_SIZE = 124 * 1024):
        self.request  = ''
        self.header   = ''
        self.data     = ''
        self.MAX_SIZE = MAX_SIZE
        self.spin     = spin
        self.fd       = None

        xmap(spin, LOAD, self.get_header)

    def split_header(self, data):
        header  = data.split('\r\n')
        request = header[0].split(' ') 
        del header[0]

        header  = map(lambda x: x.split(': ', 1), header)
        header  = dict(header)
        return request, header

    def get_header(self, spin, data):
        DELIM       = '\r\n\r\n'
        self.header = self.header + data

        if not DELIM in data: return

        header, self.data         = self.header.split(DELIM, 1)
        self.request, self.header = self.split_header(header)

        # So, we have our request.
        # We no more will issue FOUND.
        zmap(spin, LOAD, self.get_header)
        self.check_data_existence()

    def check_data_existence(self):
        try:
            size = self.header['Content-Length']
        except KeyError:
            self.spawn_request()
            return


        # If the size of the request is greater than self.MAX_SIZE
        # it just doesnt process the request.
        # I may turn it into an event.
        if size > self.MAX_SIZE:
            return

        self.size = int(size)
        self.fd   = tmpfile('a+')
        is_done   = self.check_data_size()

        if is_done:
            return

        xmap(self.spin, LOAD, self.get_data)

    def spawn_request(self):
        spawn(self.spin, self.request[0], self.header, self.fd,
                                    self.request[1], self.request[2])

        if not self.spin.ACTIVE:
            lose(self.spin)

    def check_data_size(self):
        if not self.fd.tell() >= self.size:
            return False

        self.fd.seek(0)
        self.spawn_request()
        self.fd.close()

        return True

    def get_data(self, spin, data):
        """

        """

        try:
            self.fd.write(data)
        except Exception:
            zmap(spin, LOAD, self.get_data)
            debug()

        is_done = self.check_data_size()

        if is_done:
            zmap(spin, LOAD, self.get_data)

        # Case the client is using Keep-Alive 
        # it lets the spin instance ready for another request.
        self.__init__(self, self.spin)


class Locate(object):
    def __init__(self, spin, path):
        xmap(spin, 'GET', self.locate)
        self.path     = abspath(path)

    def locate(self, spin, header, fd, resource, version):
        path = join(self.path, basename(resource))

        if not isfile(path):
            return

        # This is used to tell rapidserv reactor that 
        # the connection will keep alive to process
        # sending of data.
        spin.ACTIVE = True

        # Where we are going to serve files.
        # I might spawn an event like FILE_NOT_FOUND.
        # So, users could use it to send appropriate answers.
        type_file, encoding = guess_type(path)
        default_type = 'application/octet-stream'

        response = Response()
        response.set_response('HTTP/1.1 200 OK')
        response.add_header(('Content-Type', type_file if type_file else default_type),
                     ('Content-Length', getsize(path)))
      
        # Start sending the header.
        spin.dump(str(response))

        # Wait to dump the header.
        xmap(spin, DUMPED, lambda con: drop(con, path))

        # Wait to dump the file.

        xmap(spin, DUMPED_FILE, lose)
        xmap(spin, OPEN_FILE_ERR, lambda con, err: lose(con))

class Response(object):
    """ 
    """
    def __init__(self):
        self.response = ''
        self.header   = dict()
        self.data     = ''

    def set_response(self, data):
        """ Used to add a http response. """
        self.response = data

    def add_header(self, *args):
        """ 
        Add headers to the http response. 
        """
        self.header.update(args)

    def add_data(self, data):
        self.data = self.data + data

    def __str__(self):
        """
        """
        self.header['Content-Length'] = len(self.data)
        data = self.response
        for key, value in self.header.iteritems():
            data = '%s\r\n%s :%s' % (data, key, value)
        data = '%s\r\n\r\n' % data
        data = data + self.data
        return data

class DebugPost(object):
    """

    """

    def __init__(self, spin):
        xmap(spin, 'POST' , self.show_header)

    def show_header(self, spin, header, fd, resource, version):
        print 'POST request handled, ', header, version, resource, fd, spin.getpeername()  


class DebugGet(object):
    """

    """

    def __init__(self, spin):
        xmap(spin, 'GET' , self.show_header)

    def show_header(self, spin, header, fd, resource, version):
        print 'GET request handled, ', header, resource, version, spin.getpeername()   


def send_response(spin, response):
    spin.ACTIVE = True
    spin.dump(str(response))
    xmap(spin, DUMPED, lambda con: lose(con))

def send_response_wait(spin, response):
    pass


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





