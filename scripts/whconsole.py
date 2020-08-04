#!/usr/bin/env python2
# Test console for webhooks interface
#
# Copyright (C) 2020  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import sys, os, optparse, socket, fcntl, select, atexit, json

SOCKET_LOCATION = "/tmp/moonraker"

# Set a file-descriptor as non-blocking
def set_nonblock(fd):
    fcntl.fcntl(fd, fcntl.F_SETFL
                , fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)

def remove_socket():
    if os.path.exists(SOCKET_LOCATION):
        os.unlink(SOCKET_LOCATION)

def webhook_socket_create():
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    remove_socket()
    try:
        sock.bind(SOCKET_LOCATION)
    except socket.error:
        sys.stderr.write("Unable to create socket %s\n" % (SOCKET_LOCATION,))
        sys.exit(-1)
    sock.listen(1)
    sys.stderr.write("Waiting for connect\n")
    webhook_socket, client_address = sock.accept()
    sys.stderr.write("Connection.\n")
    webhook_socket.setblocking(0)
    return webhook_socket

class KeyboardReader:
    def __init__(self):
        self.kbd_fd = sys.stdin.fileno()
        set_nonblock(self.kbd_fd)
        self.webhook_socket = webhook_socket_create()
        self.poll = select.poll()
        self.poll.register(sys.stdin, select.POLLIN | select.POLLHUP)
        self.poll.register(self.webhook_socket, select.POLLIN | select.POLLHUP)
        self.kbd_data = self.socket_data = ""
    def process_socket(self):
        data = self.webhook_socket.recv(4096)
        if not data:
            sys.stderr.write("Socket closed\n")
            sys.exit(0)
        parts = data.split('\x03')
        parts[0] = self.socket_data + parts[0]
        self.socket_data = parts.pop()
        for line in parts:
            sys.stdout.write("GOT: %s\n" % (line,))
    def process_kbd(self):
        data = os.read(self.kbd_fd, 4096)
        parts = data.split('\n')
        parts[0] = self.kbd_data + parts[0]
        self.kbd_data = parts.pop()
        for line in parts:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                m = json.loads(line)
            except:
                sys.stderr.write("ERROR: Unable to parse line\n")
                continue
            cm = json.dumps(m, separators=(',', ':'))
            sys.stdout.write("SEND: %s\n" % (cm,))
            self.webhook_socket.send("%s\x03" % (cm,))
    def run(self):
        while 1:
            res = self.poll.poll(1000.)
            for fd, event in res:
                if fd == self.kbd_fd:
                    self.process_kbd()
                else:
                    self.process_socket()

def main():
    usage = "%prog [options]"
    opts = optparse.OptionParser(usage)
    options, args = opts.parse_args()
    if len(args) != 0:
        opts.error("Incorrect number of arguments")

    atexit.register(remove_socket)

    ml = KeyboardReader()
    ml.run()

if __name__ == '__main__':
    main()
