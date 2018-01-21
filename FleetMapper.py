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

from threading import Thread
import gi
import json
gi.require_version('Gst', '1.0')
gi.require_version('GstNet', '1.0')
from gi.repository import Gst, GstNet, GObject

from lib.NetCamClient import NetCamClient
from lib.NetCamClientHandler import NetCamClientHandler
from lib.NetCamMasterServer import NetCamMasterServer
from lib.NetCamMasterAdvertisementService import NetCamMasterAdvertisementService

import os

config = 0
mainloop = 0
t = 0 
master = 0
myserver = 0
camera = 0
shouldExit = False

def exit_master():
    global config, mainloop, t, master, myserver, camera, shouldExit
    print("exit_master invoked")
    if config['applicationMode'] == "master":
        print("Cleaning Up master")
        myserver.shutdown()
        myserver.server_close()
        master.stop()
        print("Exiting")


    if config['applicationMode'] == "camera":
        print("Cleaning Up client")
        camClient.end()
        shouldExit = True
        print("Exiting")


    mainloop.quit()


def main():
    global config, mainloop, t, master, myserver, camClient, shouldExit
    
    config_file = "config.json"
    if os.path.isfile(config_file):
        config = json.load(open(config_file))
    else:
        config = {}
        config['applicationMode'] = "camera"

    Gst.init([])
    if config['applicationMode'] == "master":
        print("Running as master")
        master = NetCamMasterAdvertisementService(config['listenIP'],config['advertisePort'])
        master.daemon = True
        master.start()
        myserver = NetCamMasterServer((config['listenIP'],config['listenPort']),NetCamClientHandler)
        t =Thread(target=myserver.serve_forever)
        t.daemon = True  # don't allow this thread to capture the keyboard interrupt
        t.start()

    if config['applicationMode'] == "camera":
        print("Running as camera")
        camClient = NetCamClient()
        t = Thread(target=camClient.run)
        t.daemon = True
        t.start()




if __name__ == '__main__':
    mainloop = GObject.MainLoop()
    try:
        main()
        mainloop.run()
    except KeyboardInterrupt:
        exit_master()
