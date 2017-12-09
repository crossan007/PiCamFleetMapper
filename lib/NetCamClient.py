from uuid import getnode
import socket
from gi.repository import Gst
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

    def __init__(self,host,camType):
        self.host=host
        self.camType = camType
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
        s.close()
       
    def run(self):
        self.start_video_stream()
        while not self.shouldExit:
            print("continuing NetCamClient loop")
            time.sleep(5)

        self.coreStreamer.end()

        
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

    def on_eos(self):
        self.end()

    def start_video_stream(self):
        server_caps = Util.get_server_config(self.host)
        core_clock = Util.get_core_clock(self.host)
        pipeline = self.get_pipeline()
        self.coreStreamer = GSTInstance(pipeline, core_clock)
        self.coreStreamer.pipeline.bus.connect("message::eos",self.on_eos)
        self.coreStreamer.pipeline.bus.connect("message::error",self.on_eos)

    def end(self):
        self.shouldExit = True
        