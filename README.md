# PiCamFleetMapper

Simplifies the use of networked video sources with VoctoCore by:
*  Providing an auto-discovery daemon to inform networked sources of the VoctoCore server address
*  Automatically launching an intermediate Gstreamer pipeline to convert the incoming video frames into something VoctoCore will tolerate
*  Automatically launching the gstreamer instance on the networked camera configured for Voctocore


# Example Topology
```
RasPi Cam v2 --(rpicamsrc)-->  RaspberryPi Zero * \
                                                   \
                                                    \
RasPi Cam v2 --(rpicamsrc)-->  RaspberryPi 3 *      |
                                                    |
                                         [Wi-Fi Access Point]
                                                    |
                                               [Ethernet]
                                                    |
Logitec C922X --(v4l2src) -->  RaspberryPi 3*  ---> |                                      
                                                    |
                                      [PiCamFleetMapper - Master]
                                                    |
Allen and Heath QU32 (USB) --(alsasrc)---->   [VoctoCore]   <<----(ximagesrc) -- Presentation PC FrameGrabber (Matroska / MJPEG)

* All RaspberyPi Devices are running PiCamFleetMapper to sync clock and download config from master.
   Transport from Pi to Core is in a Matroska container, and can be any codec.  The above pipeline uses h264 for rpicamsrc, and MJPEG for v4l2src.

```
![voctogui](https://github.com/crossan007/PiCamFleetMapper/blob/master/img/voctogui.PNG?raw=true)
