#!/usr/bin/env python3

"""
Handler for a fleet of IP cameras into VoctoCore


Script can operate in two modes:  Master or Camera


Master mode operation:

    Always awaits new camera control connections - UDP broadcasts
        Foreach Camera Connection Request
            Negotiates camera's mapping to voctocore via MAC address lookup
            Sets up gstreamer pipeline to decode camera's incoming video into voctocore
            sends signal to camera to begin streaming

Camera mode operation

    On start, broadcasts "hello from <MAC Address>
    After broadcast, listen for core response
    After core response, begin stream to address provided in core's response
    
"""

import argparse
from pprint import pprint
import sys
import time
from queue import Queue
from threading import Thread
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstNet', '1.0')
from gi.repository import Gst, GstNet, GObject
import asyncore
import socket
import socketserver
from uuid import getnode
import logging

class NetCamClient(Thread):

    def __init__(self):
        Thread.__init__(self)

    def get_self_id(self):
        h = iter(hex(getnode())[2:].zfill(12))
        return ":".join(i + next(h) for i in h)

    def run(self):
        broadcastSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        broadcastSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        broadcastSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        broadcastSocket.bind(('',54545))
        message = "hello %s" % (self.get_self_id())
        print(message)
        broadcastSocket.sendto(bytes(message,'UTF-8'), ('<broadcast>', 54545))

    def start_video_stream():
        pipelineText = "rpicamsrc bitrate=7000000 do-timestamp=true ! h264parse ! matroskamux ! queue ! tcpclientsink render-delay=800 host=172.30.9.156 port=30001"
        print(pipelineText)

class NetCamClientHandler(socketserver.BaseRequestHandler):
    video_port=0
    socket = 0
    remote_host = 0

    def handle(self):
        self.data = self.request.recv(1024).strip()
        print("{} wrote:".format(self.client_address[0]))
        print(self.data)
        # just send back the same data, but upper-cased
        self.request.sendall(self.data.upper())

    def signal_client_start(self):
        broadcastSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        broadcastSocket.bind(('',444))
        message = "OK TO START"
        print ("sending message to ",self.remote_host)
        broadcastSocket.sendto(bytes(message,'UTF-8'), self.remote_host)

    def setup_core_listener(self):
        pipelineText = "tcpserversrc host=0.0.0.0, port={video_port} ! ".format(video_port = self.video_port)
        print(pipelineText)
        pipeline = Gst.parse_launch(pipelineText)

class NetCamMasterServer(socketserver.TCPServer):

    clients_connected = 0

    def __init__(self, server_address,
                 handler_class,
                 ):
        self.logger = logging.getLogger('EchoServer')
        self.logger.debug('__init__')
        socketserver.TCPServer.__init__(self, server_address,
                                        handler_class)
        return

    def server_activate(self):
        self.logger.debug('server_activate')
        socketserver.TCPServer.server_activate(self)
        return

    def serve_forever(self, poll_interval=0.5):
        self.logger.debug('waiting for request')
        self.logger.info(
            'Handling requests, press <Ctrl-C> to quit'
        )
        socketserver.TCPServer.serve_forever(self, poll_interval)
        return

    def handle_request(self):
        self.logger.debug('handle_request')
        return socketserver.TCPServer.handle_request(self)

    def verify_request(self, request, client_address):
        self.logger.debug('verify_request(%s, %s)',
                          request, client_address)
        return socketserver.TCPServer.verify_request(
            self, request, client_address,
        )

    def process_request(self, request, client_address):
        self.logger.debug('process_request(%s, %s)',
                          request, client_address)
        self.clients_connected += 1
        print(self.clients_connected)
        return socketserver.TCPServer.process_request(
            self, request, client_address,
        )

    def server_close(self):
        self.logger.debug('server_close')
        return socketserver.TCPServer.server_close(self)

    def finish_request(self, request, client_address):
        self.logger.debug('finish_request(%s, %s)',
                          request, client_address)
        return socketserver.TCPServer.finish_request(
            self, request, client_address,
        )

    def close_request(self, request_address):
        #elf.clients_connected -= 1
        self.logger.debug('close_request(%s)', request_address)
        return socketserver.TCPServer.close_request(
            self, request_address,
        )

    def shutdown(self):
        self.logger.debug('shutdown()')
        return socketserver.TCPServer.shutdown(self)

class NetCamMasterServiceDiscoveryService():
    socket = 0
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', 54545))

    # This is called every time there is something to read
    def wait_for_core(self):
        print("Waiting for service announcement")
        while True:
            data, addr = self.socket.recvfrom(2048)
            print("Core found: ", addr)
            return addr
            break

class NetCamMasterAdvertisementService(Thread):
    should_continue = 1 

    def __init__(self,listen_address,port):
        Thread.__init__(self)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((listen_address,54545))

    def run(self):
        while self.should_continue:
            message = "hello "
            print(message)
            self.socket.sendto(bytes(message,'UTF-8'), ('<broadcast>', 54545))
            time.sleep(5)

    def stop(self):
        self.should_continue = 0 

def get_args():
    parser = argparse.ArgumentParser(
            description='''IP connected camera fleet manager for VoctoCore
            With Net-time support.
            Gst caps are retrieved from the server.
            ''')

    parser.add_argument(
        '-m', '--master', action='store_true',
        help="Use this when running on the core server to receive video streams")

    parser.add_argument(
        '-c', '--camera', action='store_true',
        help="Use this when capturing from a device.  Automatically finds core and streams on live")

    parser.add_argument(
        '-a', '--ip-address', action="store",
        default="0.0.0.0",
        help="The IP address to which to bind"
    )

    args = parser.parse_args()

    return args


def main():
    args = get_args()
    if args.master:
        master = NetCamMasterAdvertisementService('172.30.9.154',54545)
        master.daemon = False
        master.start()


        myServer = NetCamMasterServer(('172.30.9.154',5455),NetCamClientHandler)
        t = Thread(target=myServer.serve_forever)
        t.daemon = False  # don't hang on exit
        t.start()
       
        master.stop()
    if args.camera:
        camera = NetCamMasterServiceDiscoveryService()
        core = camera.wait_for_core()

        

if __name__ == '__main__':
    main()
