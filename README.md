# PiCamFleetMapper

Simplifies the use of networked video sources with VoctoCore by providing:
*  An auto-discovery daemon to inform networked sources of the VoctoCore
*  Automatically launching an intermediate Gstreamer pipeline to convert the incoming video frames into something Voctocore will tolerate
*  Automaticall launching the Gstreamer instance on the networked camera configured for Voctocore
