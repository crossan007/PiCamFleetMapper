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
import signal

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

class GSTInstance():
    pipeline = 0

    def __init__(self, pipeline, clock=None):
        print("Starting Gstremer local pipeline")
        self.pipeline = pipeline
        if clock != None:
            print("Using remote clock")
            self.pipeline.use_clock(clock)
        print("playing...")
        self.pipeline.set_state(Gst.State.PLAYING)

    def end(self):
        print('Shutting down...')
        self.pipeline.set_state(Gst.State.NULL)


class NetCamClient():
    host = 0
    camType = ''
    config = 0
    cam_id = 0
    coreStreamer = 0

    def __init__(self,host,camType):
        self.host=host
        self.camType = camType
        self.run()
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
        
    def get_self_id(self):
        h = iter(hex(getnode())[2:].zfill(12))
        return ":".join(i + next(h) for i in h)      

    def get_pipeline(self):
        srcText = ''
        NS_TO_MS = 100000
        offset = 0 

        srcText = self.config.get(self.cam_id,"client_src").strip()

        pipelineText = "{srcText} ! queue ! matroskamux ! queue ! tcpclientsink host={host} port={port}".format(srcText=srcText, 
            host=self.host, 
            port=self.config.get(self.cam_id,"video_port"))
        
        print(pipelineText)
        pipeline = Gst.parse_launch(pipelineText)

        offset = int(self.config.get(self.cam_id,"offset")) * NS_TO_MS
        if offset:
            print("Using offset: {offset}".format(offset=offset))
            pipeline.get_by_name("videosrc").get_static_pad("src").set_offset(offset)


        return pipeline

    def start_video_stream(self):
        server_caps = Util.get_server_config(self.host)
        core_clock = Util.get_core_clock(self.host)
        pipeline = self.get_pipeline()
        self.coreStreamer = GSTInstance(pipeline, core_clock)


    def end(self):
        self.coreStreamer.end()


class NetCamClientHandler(socketserver.BaseRequestHandler):

    cam_config = 0
    cam_id = 0
    coreStreamer = 0

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

    def get_virtual_camera_angles(self):
        global config
        if not self.cam_config.get(self.cam_id,"virtual_camera_angles").strip():
            return "", "", ""

        virt_camera_angle_string = """
            tee name=videotee !"""
        virt_audio_string = ""
        virt_muxes = ""
        angle_count = 0

        for virt_cam_angle in self.cam_config.get(self.cam_id,"virtual_camera_angles").split(','):
            if angle_count > 0:
                virt_camera_angle_string += """
                
                videotee. ! queue ! """
            virt_camera_angle_string += config.get(virt_cam_angle,"server_custom_pipe").strip() 
            virt_camera_angle_string +=  """
                videoconvert ! videorate ! videoscale ! {video_caps} ! mux-{virt_cam_angle}.
                """.format( core_port=config.get(virt_cam_angle,"core_port").strip(),
                video_caps="{video_caps}",
                virt_cam_angle=virt_cam_angle
                )
            
            
            virt_muxes +=  """
            matroskamux name=mux-{virt_cam_angle} ! 
                queue max-size-time=4000000000 !
                tcpclientsink host=127.0.0.1 port={core_port}
                
                """.format(core_port=config.get(virt_cam_angle,"core_port").strip(),
                virt_cam_angle=virt_cam_angle)

            virt_audio_string += """
                audiosrc. ! queue ! mux-{virt_cam_angle}.
                
            """.format(virt_cam_angle=virt_cam_angle)
            angle_count += 1

            
        virt_camera_angle_string += """
        
            videotee. ! queue ! """

        return virt_camera_angle_string, virt_audio_string, virt_muxes

    def setup_core_listener(self):

      
       
        server_caps = Util.get_server_config('127.0.0.1')
        virt_cam_angles, virt_audio_mixes, virt_muxes = self.get_virtual_camera_angles()
        virt_cam_angles = virt_cam_angles.format(video_caps = server_caps['videocaps'])

        pipelineText = """
            tcpserversrc host=0.0.0.0 port={video_port} ! matroskademux name=d ! {decode}  !

            videoconvert ! videorate ! videoscale ! {video_caps} ! 
            
            {server_custom_pipe} {virt_cam_angles} mainmux.

            audiotestsrc ! audiorate ! 
            {audio_caps} ! tee name=audiosrc ! queue ! mainmux.

            {virt_audio_mixes}

            {virt_muxes}

            matroskamux name=mainmux !
            queue max-size-time=4000000000 !
            tcpclientsink host=127.0.0.1 port={core_port}

        """.format(video_port = self.cam_config.get(self.cam_id,"video_port"), 
                video_caps = server_caps['videocaps'],
                audio_caps = server_caps['audiocaps'],
                core_port = self.cam_config.get(self.cam_id,"core_port"),
                server_custom_pipe = self.cam_config.get(self.cam_id,"server_custom_pipe").strip(),
                virt_cam_angles = virt_cam_angles,
                virt_audio_mixes = virt_audio_mixes,
                virt_muxes = virt_muxes,
                decode=self.cam_config.get(self.cam_id,"decode")
                )

        print(pipelineText)

        pipeline = Gst.parse_launch(pipelineText)
        core_clock = Util.get_core_clock("127.0.0.1")
        self.coreStreamer = GSTInstance(pipeline,core_clock)


    #def finish(self):
        #here we clean up the running coreStreamer thread
        #self.coreStreamer.end()

       


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
        '-c', '--camera', action='store_true',
        help="Use this when capturing from a device.  Automatically finds core, downloads config, and streams on live")

    parser.add_argument(
        '-a', '--ip-address', action="store",
        default="0.0.0.0",
        help="The IP address to which to bind"
    )

    args = parser.parse_args()

    return args

def exit_master(signal, frame):
    print("Cleaning Up master")
    t.close()
    t.shutdown()
    master.end()
    print("Exiting")
    sys.exit(0)


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
        signal.signal(signal.SIGINT, exit_master)


    if args.camera:
        camera = NetCamMasterServiceDiscoveryService()
        core = camera.wait_for_core()
        address, port = core
        camClient = NetCamClient(address,args.camera)

config = 0
mainloop = 0

if __name__ == '__main__':
    mainloop = GObject.MainLoop()
    try:
        main()
        mainloop.run()
    except KeyboardInterrupt:
        mainloop.quit()
