#!/usr/bin/env python

import obspython as obs
import os, time, datetime, requests, codecs
import xml.etree.ElementTree as ET
from pprint import pprint
import time
from lib.NetCamMasterAdvertisementService import NetCamMasterAdvertisementService

debug_mode = True


def script_description():
	global debug_mode
	if debug_mode: print("Calling description")

	return "<b>Remote Source Mapper</b>" + \
		"<hr>" + \
		"Map a set of GStreamer sources to named sources in OBS"

def script_load(settings):
    master = NetCamMasterAdvertisementService(args.ip_address,54545)
    master.daemon = True
    master.start()
