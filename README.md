# PiCamFleetMapper

Simplifies the use of networked video sources with VoctoCore by:
*  Providing an auto-discovery daemon to inform networked sources of the VoctoCore server address
*  Automatically launching an intermediate Gstreamer pipeline to convert the incoming video frames into something VoctoCore will tolerate
*  Automatically launching the gstreamer instance on the networked camera configured for Voctocore

# Installation Instructions
1.  Start with a base installation of [Raspbian Stretch Lite ](https://www.raspberrypi.org/downloads/raspbian/)
2.  Pre-stage [wpa_supplicant.conf](https://howchoo.com/g/ndy1zte2yjn/how-to-set-up-wifi-on-your-raspberry-pi-without-ethernet) and [ssd](https://howchoo.com/g/ote0ywmzywj/how-to-enable-ssh-on-raspbian-jessie-without-a-screen) on the SD card's /boot volume for frist-time headless connection to wifi
3.  Install prerequisites

```
sudo apt-get update
sudo apt-get install -y git autoconf automake libtool pkg-config libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libraspberrypi-dev
sudo apt-get install -y gstreamer1.0-plugins-bad gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly gstreamer1.0-tools libgstreamer1.0-0 python3 python3-gi python3-gi-cairo gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 gstreamer1.0-tools

```

4.  Enable the rpi camera interface
```
printf "start_x=1\ngpu_mem=128" | sudo tee -a /boot/config.txt
```

5.  Build [GStreamer rpicamsrc](https://github.com/thaytan/gst-rpicamsrc)
```
cd ~
git clone https://github.com/thaytan/gst-rpicamsrc.git
cd gst-rpicamsrc
./autogen.sh --prefix=/usr --libdir=/usr/lib/arm-linux-gnueabihf/
make
sudo make install

```

6.  Install PiCamFleetMapper
```
cd ~
git clone https://github.com/crossan007/PiCamFleetMapper.git
cd PiCamFleetMapper
sudo cp camera.service /etc/systemd/system/
sudo systemctl enable camera.service
```


5. Reboot the pi.  The camera should come online automatically if there a running master

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
