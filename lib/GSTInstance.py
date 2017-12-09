from gi.repository import Gst

class GSTInstance():
    pipeline = 0

    def __init__(self, pipeline, clock=None):
        print("Starting GSTInstance local pipeline")
        self.pipeline = pipeline
        if clock != None:
            print("Using remote clock")
            self.pipeline.use_clock(clock)
        print("playing...")
        self.pipeline.set_state(Gst.State.PLAYING)

    def end(self):
        print('Shutting down GSTInstance')
        self.pipeline.set_state(Gst.State.NULL)