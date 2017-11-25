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
import os
import configparser
import io

from lib.connection import Connection

class Util:
    def get_server_config(server_address):
        # establish a synchronus connection to server
        conn = Connection(server_address)

        # fetch config from server
        server_config = conn.fetch_config()

        # Pull out the configs relevant to this client
        server_conf = {
            'videocaps': server_config['mix']['videocaps'],
            'audiocaps': server_config['mix']['audiocaps']
            }
        return server_conf

    def get_core_clock(core_ip, core_clock_port=9998):

        clock = GstNet.NetClientClock.new(
            'voctocore', core_ip, core_clock_port, 0)

        print('obtained NetClientClock from host: {ip}:{port}'.format(
            ip=core_ip, port=core_clock_port))

        print('waiting for NetClientClock to sync...')
        clock.wait_for_sync(Gst.CLOCK_TIME_NONE)
        print('synced with NetClientClock.')

        return clock

class GSTInstance(Thread):
    pipeline = 0 
    def __init__(self, pipeline, clock=None):
        Thread.__init__(self)
        print("Starting Gstremer local pipeline")
        self.pipeline = pipeline
        if clock != None:
            print("Using remote clock")
            self.pipeline.use_clock(clock)

    def run(self):
        print("playing...")
        self.pipeline.set_state(Gst.State.PLAYING)

        mainloop = GObject.MainLoop()
        try:
            mainloop.run()
        except KeyboardInterrupt:
            print('Terminated via Ctrl-C')
            raise

        print('Shutting down...')
        self.pipeline.set_state(Gst.State.NULL)
        print('Done.')
        os._exit()
        return


class NetCamClient(Thread):
    host = 0
    camType = ''
    config = 0
    cam_id = 0

    def __init__(self,host,camType):
        Thread.__init__(self)
        self.host=host
        self.camType = camType
        self.run()
        
    def get_self_id(self):
        h = iter(hex(getnode())[2:].zfill(12))
        return ":".join(i + next(h) for i in h)


    def run(self):
        self.cam_id = self.get_self_id()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host, 5455))
        message = "{mac}".format(mac=self.cam_id)
        mesbytes = bytes(message,'UTF-8')
        len_sent = s.send(mesbytes)
        response = s.recv(2048).decode('UTF-8')
        print(response)
        self.config = configparser.ConfigParser()
        self.config.read_string(response)
        self.start_video_stream()
        s.close()
        return

    def get_pipeline(self):
        srcText = ''
        NS_TO_MS = 100000
        offset = 0 

        client_src_opts = self.config.get(self.cam_id,"client_src_opts").strip()
        if not client_src_opts:
            client_src_opts = " "
        if self.camType == "rpicamsrc":
            srcText = 'rpicamsrc name=videosrc {client_src_opts} ! h264parse ! '
        elif self.camType == 'v4l2src':
             srcText = 'v4l2src name=videosrc {client_src_opts}  ! jpegparse ! '
        pipelineText = """
            {srcText} matroskamux ! queue ! tcpclientsink sync=true host={host} port={port}
        """.format(srcText=srcText, 
            host=self.host, 
            port=self.config.get(self.cam_id,"video_port"),
            client_src_opts = client_src_opts)
        print(pipelineText )
        pipeline = Gst.parse_launch(pipelineText)

        offset = int(self.config.get(self.cam_id,"offset")) * NS_TO_MS
        pipeline.get_by_name("videosrc").get_static_pad("src").set_offset(offset)


        return pipeline

    def start_video_stream(self):
        #pipeline = "rpicamsrc bitrate=7000000 do-timestamp=true ! h264parse ! matroskamux ! queue ! tcpclientsink render-delay=800 host=172.30.9.156 port=30001"
        server_caps = Util.get_server_config(self.host)
        core_clock = Util.get_core_clock(self.host)
        pipeline = self.get_pipeline()
        coreStreamer = GSTInstance(pipeline, core_clock)
        coreStreamer.daemon = True
        coreStreamer.start()
        while coreStreamer.is_alive():
            time.sleep(5)
        os._exit()

class NetCamClientHandler(socketserver.BaseRequestHandler):

    cam_config = 0
    cam_id = 0
    def __init__(self, request, client_address, server):
        self.logger = logging.getLogger('EchoRequestHandler')
        self.logger.debug('__init__')
        self.video_port = server.clients_connected -1 + server.base_port # this could be hardcoded to MAC<->Port correlation
        socketserver.BaseRequestHandler.__init__(self, request,
                                                 client_address,
                                                 server)
        return

    def handle(self):
        global config 
        config = configparser.ConfigParser()
        config.read("remotes.ini")
        self.cam_id = self.request.recv(1024).strip().decode('UTF-8')
        if config.has_section(self.cam_id):
            print("found client config: {data}".format(data=self.cam_id))
            self.cam_config = configparser.ConfigParser()
            self.cam_config[self.cam_id] = config[self.cam_id]
        elif self.cam_id != 0:
            print("Not found client config: {data}".format(data=self.cam_id))
            config.add_section(self.cam_id)
            with open("remotes.ini","w") as configfile:
                config.write(configfile)
            return
        self.print_self()
        #print("{} connected:".format(self.client_address[0]))
        self.setup_core_listener()
        self.signal_client_start()

    def print_self(self):
        print("Cam ID: {id}".format(id=self.cam_id))
        print("Cam Name: {name}".format(name=self.cam_config.get(self.cam_id,"name")))
        print("Cam Core_Port: {core_port}".format(core_port=self.cam_config.get(self.cam_id,"core_port")))
        print("Cam Encoded Port: {video_port}".format(video_port=self.cam_config.get(self.cam_id,"video_port")))

    def signal_client_start(self):
        temp = io.StringIO()
        self.cam_config.write(temp)
        message = "{config}".format(config=temp.getvalue()).encode()
        print ("Telling {client}: {message}".format(client=self.client_address[0], message=message))
        self.request.sendall(message)


    def setup_core_listener(self):
       
        server_caps = Util.get_server_config('127.0.0.1')
        pipelineText = """
            tcpserversrc host=0.0.0.0 port={video_port} ! matroskademux name=d ! decodebin  !
            videoconvert ! videorate ! videoscale !
            {video_caps} ! {server_custom_pipe} mux.

            audiotestsrc ! audiorate ! 
            {audio_caps} ! mux.

            matroskamux name=mux !
            queue max-size-time=4000000000 !
            tcpclientsink host=127.0.0.1 port={core_port}

        """.format(video_port = self.cam_config.get(self.cam_id,"video_port"), 
                video_caps = server_caps['videocaps'],
                audio_caps = server_caps['audiocaps'],
                core_port = self.cam_config.get(self.cam_id,"core_port"),
                server_custom_pipe = self.cam_config.get(self.cam_id,"server_custom_pipe").strip()
                )

        pipeline = Gst.parse_launch(pipelineText)
        core_clock = Util.get_core_clock("127.0.0.1")
        coreStreamer = GSTInstance(pipeline,core_clock)
        coreStreamer.daemon = True
        coreStreamer.start()

class NetCamMasterServer(socketserver.TCPServer):

    clients_connected = 0
    base_port = 20000
    core_start_port = 10004

    def __init__(self, server_address,
                 handler_class,
                 ):
        self.logger = logging.getLogger('EchoServer')
        self.logger.debug('__init__')
        global config
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
            self, request, client_address
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
        #self.clients_connected -= 1
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
            self.socket.sendto(bytes("Hello",'UTF-8'), ('<broadcast>', 54545))
            time.sleep(5)

    def stop(self):
        self.socket.close()
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
        '-c', '--camera', action='store',
        choices=['rpicamsrc','v4l2src'],
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
    Gst.init([])
    if args.master:
        master = NetCamMasterAdvertisementService(args.ip_address,54545)
        master.daemon = True
        master.start()
        myServer = NetCamMasterServer((args.ip_address,5455),NetCamClientHandler)
        t = Thread(target=myServer.serve_forever)
        t.daemon = True  # don't hang on exit
        t.start()
        while not exitapp:
            time.sleep(1)
        t.shutdown()
        print("Exiting")


    if args.camera:
        camera = NetCamMasterServiceDiscoveryService()
        core = camera.wait_for_core()
        address, port = core
        camClient = NetCamClient(address,args.camera)
        while not exitapp:
            time.sleep(1)

        print("Exiting")

        
exitapp = False
config = 0

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("setting exitapp=true")
        exitapp = True
        raise
