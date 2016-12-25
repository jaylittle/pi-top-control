#!/usr/bin/python

import os
import sys
import smbus
from spidev import SpiDev
from time import sleep
import subprocess

# Pi-Top Battery Address & Registers
PI_BUS = 1
PI_TOP_MAX_READ_ATTEMPTS = 20
PI_TOP_BATTERY_ADDRESS = 0x0b
PI_TOP_BATTERY_REGISTER_STATE = 0x0a
PI_TOP_BATTERY_REGISTER_DISCHARGE_TIME = 0x12
PI_TOP_BATTERY_REGISTER_CHARGING_TIME = 0x13
PI_TOP_BATTERY_REGISTER_CAPACITY = 0x0d
PI_TOP_BATTERY_STATE_MASK = 0x20000000

#Pi-Top Hub commands
PI_TOP_HUB_COMMAND_GET_STATUS = 0xff

#Pi-Top Hub State Command Masks
PI_TOP_BRIGHTNESS_PARITY_MASK = 0x80
PI_TOP_BRIGHTNESS_MASK = 0x78
PI_TOP_LID_OPEN_MASK = 0x04
PI_TOP_STATE_PARITY_MASK = 0x04
PI_TOP_SCREEN_OFF_MASK = 0x02
PI_TOP_POWER_OFF_MASK = 0X01

# Pi-Top Speaker Address & Registers
PI_TOP_SPEAKER_ADDRESS = 0x18
PI_TOP_SPEAKER_REGISTER_WRITE_ENABLE = 0x00
PI_TOP_SPEAKER_CONFIG_PATH = os.path.dirname(os.path.realpath(__file__)) + "/speaker.i2c"

# Valid Devices and Command lists
ARG_DEVICE_LIST = ["battery", "system", "backlight", "lid", "speaker"]
ARG_COMMAND_LIST = {
    "battery": ["state","capacity","time"],
    "system": ["state", "off"],
    "backlight": ["state", "increase", "decrease", "on", "off", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
    "lid": ["state"],
    "speaker": ["left", "right", "mono"]
}
DEVICES_REQUIRING_STATE = ["system", "backlight", "lid"]

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

    def __init__(self, data):
        self.decode(data)

    # Bit layout is identical to encode except 3rd bit (power + screen parity) represents lid state now
    def decode(self, data):
        self.power_off = data & PI_TOP_POWER_OFF_MASK
        self.screen_off = (data & PI_TOP_SCREEN_OFF_MASK) >> 1
        self.lid_open = (data & PI_TOP_LID_OPEN_MASK) >> 2
        self.state_parity = self.parityOf(data & 3)
        self.brightness = (data & PI_TOP_BRIGHTNESS_MASK) >> 3
        self.brightness_parity = self.parityOf(self.brightness)

    # Bit layout: 1 (brightness parity), 4 (brightness), 1 (power + screen parity), 1 (screen), 1 (power)
    def encode(self):
        result = self.brightness << 3
        if self.parityOf(result & PI_TOP_BRIGHTNESS_MASK):
            result += PI_TOP_BRIGHTNESS_PARITY_MASK
        if self.power_off:
            result += PI_TOP_POWER_OFF_MASK
        if self.screen_off:
            result += PI_TOP_SCREEN_OFF_MASK
        if self.parityOf(result & 3):
            result += PI_TOP_STATE_PARITY_MASK
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

def busReadData(address, register, length = 2, ignoreZeroResult = False):
    configBus()
    result = None

    #Pull data, filtering out zero valued returns when desirable
    while (result == None) \
            or (ignoreZeroResult == False and isinstance(result, int) and result == 0) \
            or (ignoreZeroResult == False and isinstance(result, list) and len(result) > 0 and result[0] != None and result[0] == 0):
        if length == 1:
            result = bus.read_byte_data(address, register)
        elif length == 2:
            result = bus.read_word_data(address, register)
        else:
            result = bus.read_i2c_block_data(address, register, length)

    return result

def busWriteData(address, register, data):
    configBus()
    if isinstance(data, list):
        bus.write_i2c_block_data(address, register, data)
    else:
        bus.write_byte_data(address, register, data)

def spiWriteData(data, ignoreZeroResult = False):
    configSpi()
    result = None

    # Pull data, filtering out zero valued returns when desirable
    while (result == None) \
            or (ignoreZeroResult == False and isinstance(result, int) and result == 0) \
            or (ignoreZeroResult == False and isinstance(result, list) and len(result) > 0 and result[0] != None and result[0] == 0):
        spi.cshigh = False
        result = spi.xfer(data, spi.max_speed_hz)
        spi.cshigh = True

    return result

def speakerProcessCommand(command, address):
    result = RequestResult()
    mode = command[0].lower()

    interface = None
    for mix_output in runProcess(["/bin/bash", "-c", "amixer cget numid=3"]): # | grep "": values="" | cut -d'=' -f2")
        mix_output_string = "%s" % mix_output
        if "values=" in mix_output_string:
            mix_output_fields = mix_output_string.split("=")
            interface = mix_output_fields[1]

    if interface != None:
        if interface != "2":
            runProcessBlocked(["/bin/bash", "-c", "amixer cset numid=3 2"])

        if os.path.exists(PI_TOP_SPEAKER_CONFIG_PATH):
            # Open the speaker for writing
            busWriteData(address, PI_TOP_SPEAKER_REGISTER_WRITE_ENABLE, 0x01)

            # Write applicable commands from speaker.i2c file
            write_counter = 0
            with open(PI_TOP_SPEAKER_CONFIG_PATH) as pbc:
                for line in pbc:
                    if (len(line) > 0) and (line[0].lower() == "w") or (line[0].lower() == mode):
                        fields = line.split()
                        if len(fields) > 3:
                            values = [int(i, 16) for i in fields[3:]]
                            # print("speaker bus write @ address %x : register %x : data %s" % (PI_TOP_SPEAKER_ADDRESS, int(fields[2], 16), values))
                            busWriteData(PI_TOP_SPEAKER_ADDRESS, int(fields[2], 16), values)
                            write_counter += 1

            # Close the speaker for writing
            busWriteData(address, PI_TOP_SPEAKER_REGISTER_WRITE_ENABLE, 0x00)

            result.data = write_counter
            result.formattedData = "%i speaker writes" % result.data
        else:
            result.errorMessage = "Required speaker.i2c file does not exist in script directory"
    else:
        result.errorMessage = "ALSA mixer call failed to produce expected output."

    return result

def runProcess(exe):
    p = subprocess.Popen(exe, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while(True):
      retcode = p.poll() #returns None while subprocess is running
      line = p.stdout.readline()
      yield line
      if(retcode is not None):
        break

def runProcessBlocked(exe):
    result = ""
    for proc_output in runProcess(exe):
        proc_output_string = "%s" % proc_output
        result = result + proc_output_string + "\n"

    return result

def batteryProcessCommand(command):
    if command == "state":
        return batteryGetState()
    elif command == "capacity":
        return batteryGetCapacity()
    elif command == "time":
        return batteryGetTime()

    return None

def batteryGetState():
    result = RequestResult("Unknown")
    readAttempt = 1
    while result.data == "Unknown" and readAttempt <= PI_TOP_MAX_READ_ATTEMPTS:
        if readAttempt > 1:
            sleep(0.1)
        rawData = busReadData(PI_TOP_BATTERY_ADDRESS, PI_TOP_BATTERY_REGISTER_STATE)

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
        if readAttempt > 1:
            sleep(0.1)
        rawData = busReadData(PI_TOP_BATTERY_ADDRESS, PI_TOP_BATTERY_REGISTER_CAPACITY)
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
            if readAttempt > 1:
                sleep(0.1)
            if (batteryState.data == "Charging"):
                rawData = busReadData(PI_TOP_BATTERY_ADDRESS, PI_TOP_BATTERY_REGISTER_CHARGING_TIME)
                if (rawData <= 2400):
                    result.data = rawData
            elif (batteryState.data == "Discharging"):
                rawData = busReadData(PI_TOP_BATTERY_ADDRESS, PI_TOP_BATTERY_REGISTER_DISCHARGE_TIME)
                if (rawData <= 1800):
                    result.data = rawData

            readAttempt += 1

        if readAttempt > PI_TOP_MAX_READ_ATTEMPTS:
            result.errorMessage = "Bus read failed %i times in a row." % readAttempt
        else:
            result.formattedData = "%i mins" % result.data

        return result

    return batteryState

def systemProcessCommand(command, afterState):
    if afterState.errorMessage == None:
        if command == "state":
            return afterState
        elif command == "off":
            afterState.data.power_off = 1
            return systemSendCommand(afterState.data.encode())
    else:
        return afterState

    return None

def systemGetState():
    result = RequestResult()
    readAttempt = 1
    while result.data == None and readAttempt <= PI_TOP_MAX_READ_ATTEMPTS:
        if readAttempt > 1:
            sleep(0.1)
        rawData = spiWriteData([PI_TOP_HUB_COMMAND_GET_STATUS])
        if len(rawData) >= 1:
            result.data = HubState(rawData[0])
            readAttempt += 1

    if readAttempt > PI_TOP_MAX_READ_ATTEMPTS:
        result.errorMessage = "Bus read failed %i times in a row." % readAttempt
    else:
        result.formattedData = "%s" % result.data

    return result

def systemSendCommand(command):
    result = RequestResult()
    readAttempt = 1
    while result.data == None and readAttempt <= PI_TOP_MAX_READ_ATTEMPTS:
        if readAttempt > 1:
            sleep(0.1)
        rawData = spiWriteData([command])
        if len(rawData) >= 1:
            result.data = rawData
            readAttempt += 1

    if readAttempt > PI_TOP_MAX_READ_ATTEMPTS:
        result.errorMessage = "Bus read failed %i times in a row." % readAttempt
    else:
        result.formattedData = "%s" % result.data

    return result

def lidProcessCommand(command, afterState):
    if afterState.errorMessage == None:
        if command == "state":
            lidState = "Open" if afterState.data.lid_open == 1 else "Closed"
            return RequestResult(lidState, lidState)
    else:
        return afterState

    return None

def backlightProcessCommand(command, afterState):
    if afterState.errorMessage == None:
        # NOTE: Valid brightness values are between 1 and 10
        if command == "state":
            if (afterState.data.screen_off == 0):
                return RequestResult(afterState.data.brightness, "On: %s" % afterState.data.brightness)
            else:
                return RequestResult("Off", "Off")
        elif command == "increase":
            afterState.data.screen_off = 0
            if afterState.data.brightness < 10:
                afterState.data.brightness += 1
                return systemSendCommand(afterState.data.encode())
        elif command == "decrease":
            afterState.data.screen_off = 0
            if afterState.data.brightness > 1:
                afterState.data.brightness -= 1
                return systemSendCommand(afterState.data.encode())
        elif command == "on":
            # NOTE: Turning the backlight on doesnt set brightness above 0 which leaves the screen off, so we set it to 5 at the same time
            afterState.data.screen_off = 0
            afterState.data.brightness = 5
            return systemSendCommand(afterState.data.encode())
        elif command == "off":
            # NOTE: Turning off backlight sets brightness to 0 automatically
            afterState.data.screen_off = 1
            return systemSendCommand(afterState.data.encode())
        else:
            afterState.data.screen_off = 0
            afterState.data.brightness = int(command)
            return systemSendCommand(afterState.data.encode())
    else:
        return afterState

    return None

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

if (device == "speaker") and (len(sys.argv) <= 3):
    print("Error: Speaker commands require a 3rd param with the address of the device", file=sys.stderr)
    quit(1)

result = None

beforeState = None
afterState = None
if device in DEVICES_REQUIRING_STATE:
    # Do it twice to ensure we get the current system state back
    beforeState = systemGetState()
    afterState = systemGetState()

if device == "battery":
    result = batteryProcessCommand(command)
elif device == "system":
    result = systemProcessCommand(command, afterState)
elif device == "lid":
    result = lidProcessCommand(command, afterState)
elif device == "backlight":
    result = backlightProcessCommand(command, afterState)
elif device == "speaker":
    result = speakerProcessCommand(command, int(sys.argv[3], 16))

if result != None:
    if device in DEVICES_REQUIRING_STATE and command != "state" and result.errorMessage == None:
        #Do it twice to ensure we get the current system state back
        beforeState = systemGetState()
        result = afterState = systemGetState()

    if result.errorMessage == None:
        print(result.formattedData)
        exit(0)
    else:
        print("Error: %s" % result.errorMessage, file=sys.stderr)
        exit(1)
else:
    print("Error: Nothing happened. This is probably the result of a boneheaded bug.", file=sys.stderr)
    exit(1)