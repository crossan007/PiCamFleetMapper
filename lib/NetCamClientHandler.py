import socketserver
import configparser
import logging
from gi.repository import Gst
from lib.Util import Util
from lib.GSTInstance import GSTInstance
import io
import json

class NetCamClientHandler(socketserver.BaseRequestHandler):

    cam_config = 0
    cam_id = 0
    coreStreamer = 0

    def __init__(self, request, client_address, server):
        self.logger = logging.getLogger('EchoRequestHandler')
        self.logger.debug('__init__')
        self.video_port = server.clients_connected -1 + server.base_port # this could be hardcoded to MAC<->Port correlation
        self.server = server
        socketserver.BaseRequestHandler.__init__(self, request,
                                                 client_address,
                                                 server)
        return

    def handle(self):
      
        self.cam_id = self.request.recv(1024).strip().decode('UTF-8')
        if self.server.client_configs[self.cam_id]:
            print("found client config: {data}".format(data=self.cam_id))
            self.cam_config = self.server.client_configs[self.cam_id]

        elif self.cam_id != 0:
            print("Not found client config: {data}".format(data=self.cam_id))
          
        self.print_self()
        self.setup_core_listener()
        self.signal_client_start()

    def print_self(self):
        print(json.dumps(self.cam_config, indent=4, sort_keys=True))

    def signal_client_start(self):
        temp = io.StringIO()
        json.dump(self.cam_config, temp)
        message = "{config}".format(config=temp.getvalue()).encode()
        print ("Telling {client}: {message}".format(client=self.client_address[0], message=message))
        self.request.sendall(message)

    def get_virtual_camera_angles(self):
        global config
        if not (self.cam_config["virtual_camera_angles"]) :
            return "", "", ""

        virt_camera_angle_string = """
            tee name=videotee !"""
        virt_audio_string = ""
        virt_muxes = ""
        angle_count = 0

        for virt_cam_angle in self.cam_config["virtual_camera_angles"]:
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
        NS_TO_MS = 1000000
        offset = 0 
        server_caps = Util.get_server_config('127.0.0.1')
        virt_cam_angles, virt_audio_mixes, virt_muxes = self.get_virtual_camera_angles()
        virt_cam_angles = virt_cam_angles.format(video_caps = server_caps['videocaps'])

        pipelineText = """
            tcpserversrc host=0.0.0.0 port={video_port} ! matroskademux name=d ! {decode}  !

            videoconvert ! videorate ! videoscale ! {video_caps} ! 

            identity name=videosrc !
            
            {server_custom_pipe} {virt_cam_angles} mainmux.

            audiotestsrc ! audiorate ! 
            {audio_caps} ! tee name=audiosrc ! queue ! mainmux.

            {virt_audio_mixes}

            {virt_muxes}

            matroskamux name=mainmux !
            queue max-size-time=4000000000 !
            tcpclientsink host=127.0.0.1 port={core_port}

        """.format(video_port = self.cam_config["video_port"], 
                video_caps = server_caps['videocaps'],
                audio_caps = server_caps['audiocaps'],
                core_port = self.cam_config["core_port"],
                server_custom_pipe = self.cam_config["server_custom_pipe"].strip(),
                virt_cam_angles = virt_cam_angles,
                virt_audio_mixes = virt_audio_mixes,
                virt_muxes = virt_muxes,
                decode=self.cam_config["decode"]
                )

        print(pipelineText)

        pipeline = Gst.parse_launch(pipelineText)
        
        offset = int(self.cam_config["offset"]) * NS_TO_MS
        if offset:
            print("Using offset: {offset}".format(offset=offset))
            pipeline.get_by_name("videosrc").get_static_pad("src").set_offset(offset)

        core_clock = Util.get_core_clock("127.0.0.1")
        self.coreStreamer = GSTInstance(pipeline,core_clock)
        self.coreStreamer.pipeline.bus.add_signal_watch()
        self.coreStreamer.pipeline.bus.connect("message::eos",self.on_eos)
        self.coreStreamer.pipeline.bus.connect("message::error",self.on_eos)

    def on_eos(self,bus,message):
        self.coreStreamer.end()

    #def finish(self):
        #here we clean up the running coreStreamer thread
        #self.coreStreamer.end()

   