import socketserver
import configparser
import logging
from gi.repository import Gst
from lib.Util import Util
from lib.GSTInstance import GSTInstance
import io

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

            identity name=videosrc !
            
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
        
        offset = int(self.cam_config.get(self.cam_id,"offset")) * NS_TO_MS
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

   