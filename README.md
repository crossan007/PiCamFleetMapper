# PiCamFleetMapper

Simplifies the use of networked video sources with VoctoCore by:
*  Providing an auto-discovery daemon to inform networked sources of the VoctoCore server address
*  Automatically launching an intermediate Gstreamer pipeline to convert the incoming video frames into something VoctoCore will tolerate
*  Automatically launching the gstreamer instance on the networked camera configured for Voctocore
