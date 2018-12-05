# Luminous Raspberry Pi SPL meter
* Sound Pressure Level meter with RPI implemented with Python.
* Author: Patrice GODARD, based on SPL Meter implementation by Seyoung Park
* E-mail: patrice.godard@laposte.net, seyoung.arts.park@protonmail.com
* Date: 2018 Nov 11th

## Demo
Luminous SPL Demo (Old one with an external SPL Meter, the new one is only using an USB microphone): https://www.youtube.com/watch?v=ojf781tA3Rg


## Requirements
### HW
* Raspberry Pi
* Microphone 
* Neopixel (WS2812) leds and 3.3 to TTL level shifter
* ADS1115 ADC breakout board

### SW
* Python 2
* EasyProcess==0.2.2
* numpy==1.10.4
* PyAudio==0.2.9
* scipy==0.17.0
* wheel==0.24.0
* rpi_ws281x=1.0.3
* Adafruit-ADS1x15=1.0.2

## Filter: A-weighting
I applied A-weighting to filter to filter the stream. A-weighting results frequencies which average person can hear. For further information read: [Frequency Weightings - A-Weighted, C-Weighted or Z-Weighted?](https://www.noisemeters.com/help/faq/frequency-weighting.asp)
For the actual programmatic implementation I borrowed the code from [endolith](https://gist.github.com/endolith/148112) and is saved as /spl_lib.py. A-weighting() is translated from [MATLAB script](: http://www.mathworks.com/matlabcentral/fileexchange/69).
