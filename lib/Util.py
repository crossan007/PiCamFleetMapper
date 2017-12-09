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