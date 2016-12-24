#!/usr/bin/python

import sys
import smbus
from spidev import SpiDev

# Pi-Top Battery Address & Registers
PI_BUS = 1
PI_TOP_MAX_READ_ATTEMPTS = 20
PI_TOP_BATTERY_ADDRESS = 0x0b
PI_TOP_BATTERY_REGISTER_STATE = 0x0a
PI_TOP_BATTERY_REGISTER_DISCHARGE_TIME = 0x12
PI_TOP_BATTERY_REGISTER_CHARGING_TIME = 0x13
PI_TOP_BATTERY_REGISTER_CAPACITY = 0x0d
PI_TOP_BATTERY_STATE_MASK = int('1000000000000000', 2)

PI_TOP_HUB_COMMAND_GET_STATUS = 0xFF

PI_TOP_BRIGHTNESS_PARITY_MASK = 0x80
PI_TOP_BRIGHTNESS_MASK = 0x78
PI_TOP_LID_OPEN_MASK = 0x04
PI_TOP_STATE_PARITY_MASK = 0x04
PI_TOP_SCREEN_OFF_MASK = 0x02
PI_TOP_POWER_OFF_MASK = 0X01

# Valid Devices and Command lists
ARG_DEVICE_LIST = ["battery", "system", "backlight"]
ARG_COMMAND_LIST = {
    "battery": ["state","capacity","time"],
    "system": ["state"],
    "backlight": ["increase", "decrease", "on", "off"]
}

class RequestResult:
    data = None
    formattedData = None
    errorMessage = None
    def __init__(self, data = None, formatted_data = None, error_message = None):
        self.data = data
        self.formattedData = formatted_data
        self.errorMessage = error_message

class HubState:
    power_off = 0
    screen_off = 0
    state_parity = 0
    brightness = 5
    brightness_parity = 0
    lid_open = 0

    def decode(self, data):
        self.power_off = data & PI_TOP_POWER_OFF_MASK
        self.screen_off = (data & PI_TOP_SCREEN_OFF_MASK) >> 1
        self.lid_open = (data & PI_TOP_LID_OPEN_MASK) >> 2
        self.state_parity = self.parityOf(data & 3)
        self.brightness = (data & PI_TOP_BRIGHTNESS_MASK) >> 3
        self.brightness_parity = self.parityOf(self.brightness)

    def encode(self):
        result = self.brightness << 3
        if self.parityOf(result & PI_TOP_BRIGHTNESS_MASK):
            result = result + PI_TOP_BRIGHTNESS_PARITY_MASK
        if self.power_off:
            result = result + PI_TOP_POWER_OFF_MASK
        if self.screen_off:
            result = result + PI_TOP_SCREEN_OFF_MASK
        if self.parityOf(result & 3):
            result = result + PI_TOP_STATE_PARITY_MASK
        return result

    def parityOf(self, data):
        parity = 0
        for bit in bin(data)[2:]:
            parity ^= int(bit)
        return parity

    def __str__(self):
        result = "{ \"power off\": %s" % self.power_off
        result += ", \"screen_off\": %s" % self.screen_off
        result += ", \"state_parity\": %s" % self.state_parity
        result += ", \"lid_open\": %s" % self.lid_open
        result += ", \"brightness\": %s" % self.brightness
        result += ", \"brightness_parity\": %s }" % self.brightness_parity
        return result

bus = None
spi = None

def configBus():
    global bus
    if bus == None:
        bus = smbus.SMBus(PI_BUS)

def configSpi():
    global spi
    if spi == None:
        spi = SpiDev()
        spi.open(0, 1)  # Bus 0, Chip Select 1
        spi.max_speed_hz = 9600
        spi.mode = 0b00
        spi.bits_per_word = 8
        spi.cshigh = True
        spi.lsbfirst = False

def busGetData(address, register, length = 2):
    configBus()
    readAttempt = 1
    success = False
    data = None

    if length == 1:
        data = bus.read_byte_data(address, register)
    elif length == 2:
        data = bus.read_word_data(address, register)
    else:
        data = bus.read_i2c_block_data(address, register, length)

    #print("Bus read output %s" % [data])

    return data

def busWriteData(address, register, data):
    # TODO Figure this out
    configBus()

def spiWriteData(data):
    configSpi()
    spi.cshigh = False
    data = spi.xfer(data, spi.max_speed_hz)
    spi.cshigh = True

    for chunk in data:
        chunk_hex_str = '0x' + str(hex(chunk))[2:].zfill(2)
        chunk_bin_str = '{0:b}'.format(int(chunk_hex_str[2:], 16)).zfill(8)
        print("spi write returned %s" % chunk_bin_str)

    return data

def batteryGetState():
    result = RequestResult("Unknown")
    readAttempt = 1
    while result.data == "Unknown" and readAttempt <= PI_TOP_MAX_READ_ATTEMPTS:
        rawData = busGetData(PI_TOP_BATTERY_ADDRESS, PI_TOP_BATTERY_REGISTER_STATE)

        # TODO Research zen buddhism and acquire a better understanding of the logic below
        if (rawData & PI_TOP_BATTERY_STATE_MASK == 0):
            data = rawData
        else:
            data = -1 * ((~rawData) + 1 + 65536)

        if (data >= -4000) and (data <= 4000):
            if data >= -10:
                result.data = "Charging"
            else:
                result.data = "Discharging"

        readAttempt += 1

    if readAttempt > PI_TOP_MAX_READ_ATTEMPTS:
        result.error = "Bus read failed %i times in a row." % readAttempt
    else:
        result.formattedData = result.data

    return result

def batteryGetCapacity():
    result = RequestResult()
    readAttempt = 1
    while result.data == None and readAttempt <= PI_TOP_MAX_READ_ATTEMPTS:
        rawData = busGetData(PI_TOP_BATTERY_ADDRESS, PI_TOP_BATTERY_REGISTER_CAPACITY)
        if rawData <= 100:
            result.data = rawData

        readAttempt += 1

    if readAttempt > PI_TOP_MAX_READ_ATTEMPTS:
        result.error = "Bus read failed %i times in a row." % readAttempt
    else:
        result.formattedData = "%s%%" % result.data

    return result

def batteryGetTime():
    batteryState = batteryGetState()

    if batteryState.errorMessage == None:
        result = RequestResult()
        readAttempt = 1
        while result.data == None and readAttempt <= PI_TOP_MAX_READ_ATTEMPTS:
            if (batteryState.data == "Charging"):
                rawData = busGetData(PI_TOP_BATTERY_ADDRESS, PI_TOP_BATTERY_REGISTER_CHARGING_TIME)
                if (rawData <= 2400):
                    result.data = rawData
            elif (batteryState.data == "Discharging"):
                rawData = busGetData(PI_TOP_BATTERY_ADDRESS, PI_TOP_BATTERY_REGISTER_DISCHARGE_TIME)
                if (rawData <= 1800):
                    result.data = rawData

            readAttempt += 1

        if readAttempt > PI_TOP_MAX_READ_ATTEMPTS:
            result.errorMessage = "Bus read failed %i times in a row." % readAttempt
        else:
            result.formattedData = "%i mins" % result.data

        return result

    return batteryState

def systemGetState():
    result = RequestResult()
    readAttempt = 1
    while result.data == None and readAttempt <= PI_TOP_MAX_READ_ATTEMPTS:
        rawData = spiWriteData([PI_TOP_HUB_COMMAND_GET_STATUS])
        if len(rawData) >= 1:
            state = HubState()
            state.decode(rawData[0])
            result.data = state
            readAttempt += 1

    if readAttempt > PI_TOP_MAX_READ_ATTEMPTS:
        result.errorMessage = "Bus read failed %i times in a row." % readAttempt
    else:
        result.formattedData = "%s" % result.data

    return result

# Check to see that minimum required number of arguments have been provided (script name is sys.argv[0])
if len(sys.argv) <= 2:
    print("Error: Device and Command are both required arguments", file=sys.stderr)
    quit(1)

device = sys.argv[1].lower()
command = sys.argv[2].lower()

if device not in ARG_DEVICE_LIST:
    print("Error: Device must be one of the following: %s" % ARG_DEVICE_LIST, file=sys.stderr)
    quit(1)

if command not in ARG_COMMAND_LIST.get(device):
    print("Error: Command must be one of the following: %s" % ARG_COMMAND_LIST.get(device), file=sys.stderr)
    quit(1)

result = RequestResult()

if device == "battery":
    if command == "state":
        result = batteryGetState()
    if command == "capacity":
        result = batteryGetCapacity()
    if command == "time":
        result = batteryGetTime()
elif device == "system":
    if command == "state":
        result = systemGetState()

if result.errorMessage != None:
    print("Error: %s" % result.errorMessage, file=sys.stderr)
else:
    print(result.formattedData)