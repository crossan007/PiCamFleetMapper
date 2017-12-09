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

from uuid import getnode
import logging
import os
import configparser
import io

from lib.connection import Connection

from lib.NetCamClient import NetCamClient
from lib.Util import Util
from lib.GSTInstance import GSTInstance
from lib.NetCamClientHandler import NetCamClientHandler
from lib.NetCamMasterServer import NetCamMasterServer
from lib.NetCamMasterServiceDiscoveryService import NetCamMasterServiceDiscoveryService
from lib.NetCamMasterAdvertisementService import NetCamMasterAdvertisementService

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
        help="Use this when capturing from a device.  Automatically finds core, downloads config, and streams on live")

    parser.add_argument(
        '-a', '--ip-address', action="store",
        default="0.0.0.0",
        help="The IP address to which to bind"
    )

    args = parser.parse_args()

    return args

args = 0 
config = 0
mainloop = 0
t = 0 
master = 0
myserver = 0
camera = 0

def exit_master():
    global args, mainloop, t, master, myserver, camera
    print("exit_master invoked")
    if args.master:
        print("Cleaning Up master")
        myserver.shutdown()
        myserver.server_close()
        master.stop()
        print("Exiting")


    if args.camera:
        print("Cleaning Up client")
        camClient.end()
        print("Exiting")

    mainloop.quit()


def main():
    global args, mainloop, t, master, myserver, camClient
    Gst.init([])
    if args.master:
        master = NetCamMasterAdvertisementService(args.ip_address,54545)
        master.daemon = True
        master.start()
        myserver = NetCamMasterServer((args.ip_address,5455),NetCamClientHandler)
        t =Thread(target=myserver.serve_forever)
        t.daemon = True  # don't allow this thread to capture the keyboard interrupt
        t.start()

    if args.camera:
        camera = NetCamMasterServiceDiscoveryService()
        while True:
            core = camera.wait_for_core()
            address, port = core
            camClient = NetCamClient(address,args.camera)



if __name__ == '__main__':
    mainloop = GObject.MainLoop()
    try:
        args = get_args()
        main()
        mainloop.run()
    except KeyboardInterrupt:
        exit_master()
