import time
from neopixel import *
import sys
import math
from array import *
import RPi.GPIO as GPIO
from collections import deque
import os, errno
import pyaudio
import spl_lib as spl
from scipy.signal import lfilter
import numpy
import Adafruit_ADS1x15
import signal
import struct 

#enable print statements if True
DEBUG = False
#DEBUG = True

# LED strip configuration:
LED_COUNT      = 16      # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (must support PWM!).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 5       # DMA channel to use for generating signal (try 5)
LED_BRIGHTNESS = 255     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)

LEVEL_MIN = 30 #minimum sound level
DELTA_LEVEL = 45 #delta between minimum displayble value and max
PEAK_DELAY = 100 #showing peak value during this many loops

threshold = 0
interrupted = False

adc = Adafruit_ADS1x15.ADS1115()


''' The following is similar to a basic CD quality
   When CHUNK size is 4096 it routinely throws an IOError.
   When it is set to 8192 it doesn't.
   IOError happens due to the small CHUNK size

   What is CHUNK? Let's say CHUNK = 4096
   math.pow(2, 12) => RATE / CHUNK = 100ms = 0.1 sec
'''
CHUNKS = [4096, 8192]       # Use what you need
CHUNK = CHUNKS[1]
FORMAT = pyaudio.paInt16    # 16 bit
CHANNEL = 1    # 1 means mono. If stereo, put 2

'''
Different mics have different rates.
For example, Logitech HD 720p has rate 48000Hz
'''
RATES = [44100]
RATE = RATES[0]

NUMERATOR, DENOMINATOR = spl.A_weighting(RATE)

def trace(msg):
    if DEBUG == True:
        print(msg);

class Simplemovingaverage():
    def __init__(self, period):
        assert period == int(period) and period > 0, "Period must be an integer >0"
        self.period = period
        self.stream = deque()
 
    def __call__(self, n):
        stream = self.stream
        stream.append(n)    # appends on the right
        streamlength = len(stream)
        if streamlength > self.period:
            stream.popleft()
            streamlength -= 1
        if streamlength == 0:
            average = 0
        else:
            average = sum( stream ) / streamlength
 
        return average

sma = Simplemovingaverage(7)
#sma2 = Simplemovingaverage(7)


def wheel(pos,brightness = 100):
	brightness = brightness / float(100);
	##Generate rainbow colors across 0-255 positions.
	if pos < 85:
		return Color(int(pos * 3 * brightness), int((255 - pos * 3)* brightness), 0)
	elif pos < 170:
		pos -= 85
		return Color(int((255 - pos * 3) * brightness), 0, int(pos * 3 * brightness))
	else:
		pos -= 170
		return Color(0, int(pos * 3 * brightness), int((255 - pos * 3)* brightness))

		
def display(strip,level,peak,minLevel,maxLevel):
        if level > maxLevel :
                level = maxLevel
        ## this is kind of "sub-pixel rendering"
	## calculate number of lit-up leds as if 100 leds and
	## use "fractional value" to drive the top-most led to an intermediate brightness
	subPix = int(round((level-minLevel)*strip.numPixels()*100/(maxLevel-minLevel)))
	pix = int(math.floor(subPix / 100)) 
        if pix >= strip.numPixels():
                pix = strip.numPixels()-1
        trace("pix= %s" % pix)
        for i in range(strip.numPixels()):
                strip.setPixelColor(i,Color(0,0,0))
        for i in range(pix,-1,-1):               
                strip.setPixelColor(i,wheel(wheelPos[i] & 255,100))
	subPix = subPix - (pix * 100)
        trace("subPix= %s" % subPix)
	if pix < strip.numPixels() - 1 and pix >= 0:
		strip.setPixelColor(pix+1,wheel(wheelPos[pix+1] & 255,subPix))	
        
	#peak level
        subPix = int(round((peak-minLevel)*strip.numPixels()*100/(maxLevel-minLevel)))
	pix = int(math.floor(subPix / 100)) 
	subPix = subPix - (pix * 100)
        if pix >= strip.numPixels():
                pix = strip.numPixels()-1
        if pix < 0:
                pix = 0
	if pix < strip.numPixels() - 1 and subPix > 20:
		strip.setPixelColor(pix+1,wheel(wheelPos[pix+1] & 255,100))	
        else:
        	strip.setPixelColor(pix,wheel(wheelPos[pix] & 255,100))

 
        strip.show()


# create analog read function for reading charging and discharging data
def analog_read():
    val = adc.get_last_result()
    smoothed_val = sma(val)
    #trace("analog_read: %d" % smoothed_val)
    return smoothed_val

def getDBThreshold():
    t = ((DELTA_LEVEL + LEVEL_MIN) * analog_read()/26347); 
    if(t < LEVEL_MIN):
        t = LEVEL_MIN 
    trace("threshold: %d" % t)
    return t

def signal_handler(sig, frame):
    global interrupted
    interrupted = True

# Main program logic follows:
if __name__ == '__main__':
        GPIO.setmode(GPIO.BCM)
        signal.signal(signal.SIGINT, signal_handler)
        #start continous conversions
        adc.start_adc(0, gain=1, data_rate=64)
        
        wheelPos = array('i',[126,126,108,108,87,87,65,65,45,45,38,38,22,22,0,0])
	# Create NeoPixel object with appropriate configuration.
	strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS)
	# Intialize the library (must be called once before other functions).
	strip.begin()

        peak = 0
        counter = 0

        pa = pyaudio.PyAudio()
        
        stream = pa.open(format = FORMAT,
                channels = CHANNEL,
                rate = RATE,
                input = True,
                input_device_index=0,
                frames_per_buffer = CHUNK)
        trace ("listening to mic")
        trace ('Press Ctrl-C to quit.')
        while interrupted == False:
            t1 = time.time() * 1000
            try:
                block = stream.read(CHUNK)
            except IOError, e:
                print("Error recording: %s" % (e))
            else:
                ## Int16 is a numpy data type which is Integer (-32768 to 32767)
                ## If you put Int8 or Int32, the result numbers will be ridiculous
                decoded_block = numpy.fromstring(block, 'Int16') #**3
                ## This is where you apply A-weighted filter
                y = lfilter(NUMERATOR, DENOMINATOR, decoded_block)
                dB = 20*numpy.log10(spl.rms_flat(y)) * 3 #/ 1.5 ##added / 1.5 to adjust sensitivity
                #smoothing
		#dB = sma2(dB)
                trace('A-weighted: {:+.2f} dB'.format(dB))

                if(dB > peak):
                        peak = dB
                        counter = 0
                        
                if(counter % PEAK_DELAY == 0):
                        peak = dB
                        counter = 0
               # if(counter % PEAK_DELAY / 8 == 0):
                #        threshold = getDBThreshold()
                threshold = getDBThreshold()
		levelMin = threshold - DELTA_LEVEL 
                if (levelMin < LEVEL_MIN):
			levelMin = LEVEL_MIN
		trace("levelMin= %d" % levelMin)
		display(strip,dB,peak,levelMin,threshold+1)
                
                counter = counter+1

                t2 = time.time() * 1000
                #print ("XX: {}".format(t2-t1))

        adc.stop_adc()
	for i in range(0,strip.numPixels()):
                strip.setPixelColor(i,Color(0,0,0))
        	strip.show()
        stream.stop_stream()
        stream.close()
        pa.terminate()
