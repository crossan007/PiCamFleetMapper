import socket

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