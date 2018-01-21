from threading import Thread
import socket
import time

class NetCamMasterAdvertisementService(Thread):

    def __init__(self,listen_address,port):
        self.advertiseAddress = listen_address
        self.advertise_port = port
        Thread.__init__(self)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((listen_address,self.advertise_port))
        self.should_continue = 1 

    def run(self):
        while self.should_continue:
            self.socket.sendto(bytes("Hello",'UTF-8'), ('<broadcast>',self.advertise_port))
            print("sending Hello via {port}".format(port=self.advertise_port))
            time.sleep(5)

    def stop(self):
        self.socket.close()
        self.should_continue = 0 


