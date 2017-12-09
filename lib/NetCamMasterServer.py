
class NetCamMasterServer(socketserver.TCPServer):

    allow_reuse_address = True
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
        print('server_close')
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
        print('shutdown()')
        return socketserver.TCPServer.shutdown(self)
