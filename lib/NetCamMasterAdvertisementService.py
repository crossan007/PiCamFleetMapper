from threading import Thread
import socket
import time

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


