#!/usr/bin/env python3


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
from uuid import getnode

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
        print("asdf")


class NetCamClientHandler(Thread):
    video_port=0
    def __init__(self,ip_address,video_port):
        Thread.__init__(self)
        self.video_port=video_port
        print ("New Client: ", ip_address)
        self.setup_core_listener()

    def setup_core_listener(self):
        pipeline = "tcpserversrc host=0.0.0.0, port={video_port}".format(video_port = self.video_port)
        print(pipeline)
        

class NetCamMaster(asyncore.dispatcher):

    cameras = []

    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.bind((host, port))

    # This is called every time there is something to read
    def handle_read(self):
        data, addr = self.recvfrom(2048)
        tempCam = NetCamClientHandler(addr,444)
        self.cameras.append(tempCam)
        print(data," ", addr)

    def writable(self): 
        return False # don't want write notifies


def broadcast_camera_presence():
    camera = NetCamClient()
    camera.daemon = False
    camera.start()

def wait_for_cameras(ip_address):
    master = NetCamMaster(ip_address,54545)
    asyncore.loop()


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
        wait_for_cameras(args.ip_address)
    if args.camera:
        broadcast_camera_presence()
        

if __name__ == '__main__':
    main()
