from uuid import getnode
import socket
from gi.repository import Gst, GObject
import configparser
from lib.Util import Util
from lib.GSTInstance import GSTInstance
import time

class NetCamClient():
    host = 0
    camType = ''
    config = 0
    cam_id = 0
    coreStreamer = 0
    shouldExit = False
    mainloop = 0

    def __init__(self):
        self.cam_id = self.get_self_id()
        self.mainloop =  GObject.MainLoop()

    def wait_for_core(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', 54545))
        print("Waiting for service announcement")
        while True:
            data, addr = self.socket.recvfrom(2048)
            print("Core found: ", addr)
            break
        self.socket.close()
        return addr

    def initalize_video(self):
        core = self.wait_for_core()
        self.host, self.port = core
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host, 5455))
        message = "{mac}".format(mac=self.cam_id)
        mesbytes = bytes(message,'UTF-8')
        len_sent = s.send(mesbytes)
        response = s.recv(2048).decode('UTF-8')
        print(response)
        self.config = configparser.ConfigParser()
        self.config.read_string(response)
        s.close()

    def run(self):
        while not self.shouldExit:
            try:
                self.initalize_video()
                self.start_video_stream()
                self.mainloop.run()
            except:
                pass
            print("Restarting NetCamClient")
        
    def get_self_id(self):
        """
            returns the ID of this camera
            after first execution, the ID should persist to a file
        """
        configfilepath="/etc/camera.ini"

        config = configparser.ConfigParser()
        config.read(configfilepath)
        camid = ""
        if config.has_section("camera"):
            camid = config.get("camera","id")
            print("Found CamID in camera.ini: " + camid)
        else:
            config.add_section("camera")

        if (camid == ""):
            h = iter(hex(getnode())[2:].zfill(12))
            camid = ":".join(i + next(h) for i in h)
            config.set("camera","id",camid)
            with open(configfilepath, 'w') as configfile:
                config.write(configfile)
            print("Generated CamID and wrote to camera.ini: " + camid)
        
        return camid

    def get_pipeline(self):
        srcText = ''

        srcText = self.config.get(self.cam_id,"client_src").strip()

        pipelineText = "{srcText} ! queue ! matroskamux ! queue ! tcpclientsink host={host} port={port}".format(srcText=srcText, 
            host=self.host, 
            port=self.config.get(self.cam_id,"video_port"))
        
        print(pipelineText)
        pipeline = Gst.parse_launch(pipelineText)

       


        return pipeline


    def on_eos(self,bus,message):
        print(message)
        self.coreStreamer.end()
        self.mainloop.quit()

    def start_video_stream(self):
        server_caps = Util.get_server_config(self.host)
        core_clock = Util.get_core_clock(self.host)
        pipeline = self.get_pipeline()
        self.coreStreamer = GSTInstance(pipeline, core_clock)
        self.coreStreamer.pipeline.bus.add_signal_watch()
        self.coreStreamer.pipeline.bus.connect("message::eos",self.on_eos)
        self.coreStreamer.pipeline.bus.connect("message::error",self.on_eos)

    def end(self):
        self.shouldExit = True
        self.mainloop.quit()
        