from datetime import datetime
import os
from spidev import SpiDev
import subprocess
import time

# TODO: Rewrite this code
def setupSPI():
    spi = SpiDev()
    spi.open(0,1) # Bus 0, Chip Select 1
	spi.max_speed_hz = 9600
	spi.mode = 0b00
	spi.bits_per_word = 8
	spi.cshigh = True
	spi.lsbfirst = False
	return spi

