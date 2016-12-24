#!/usr/bin/python

import sys
import smbus

# Pi-Top Battery Address & Registers
PI_BUS = 1
PI_TOP_MAX_READ_ATTEMPTS = 20
PI_TOP_BATTERY_ADDRESS = 0x0b
PI_TOP_BATTERY_REGISTER_STATE = 0x0a
PI_TOP_BATTERY_REGISTER_DISCHARGE_TIME = 0x12
PI_TOP_BATTERY_REGISTER_CHARGING_TIME = 0x13
PI_TOP_BATTERY_REGISTER_CAPACITY = 0x0d
PI_TOP_BATTERY_STATE_MASK = int('1000000000000000', 2)

# Valid Devices and Command lists
ARG_DEVICE_LIST = ["battery"]
ARG_COMMAND_LIST = {
    "battery": ["state","capacity","time"]
}

bus = smbus.SMBus(PI_BUS)

def busGetData(address, register, length = 2):
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

def batteryGetState(printFlag = True):
    result = "Unknown"
    readAttempt = 1
    while result == "Unknown" and readAttempt <= PI_TOP_MAX_READ_ATTEMPTS:
        rawData = busGetData(PI_TOP_BATTERY_ADDRESS, PI_TOP_BATTERY_REGISTER_STATE)

        # TODO Research zen buddhism and acquire a better understanding of the logic below
        if (rawData & PI_TOP_BATTERY_STATE_MASK == 0):
            data = rawData
        else:
            data = -1 * ((~rawData) + 1 + 65536)

        if (data >= -4000) and (data <= 4000):
            if data >= -10:
                result = "Charging"
            else:
                result = "Discharging"

        readAttempt = readAttempt + 1

    if readAttempt > PI_TOP_MAX_READ_ATTEMPTS:
        print("Bus read failed %i times in a row." % readAttempt, file=sys.stderr)
        exit(1)

    if printFlag:
        print("%s" % result)

    return result

def batteryGetCapacity(printFlag = True):
    result = None
    readAttempt = 1
    while result == None and readAttempt <= PI_TOP_MAX_READ_ATTEMPTS:
        rawData = busGetData(PI_TOP_BATTERY_ADDRESS, PI_TOP_BATTERY_REGISTER_CAPACITY)
        if rawData <= 100:
            result = rawData

        readAttempt = readAttempt + 1

    if readAttempt > PI_TOP_MAX_READ_ATTEMPTS:
        print("Bus read failed %i times in a row." % readAttempt, file=sys.stderr)
        exit(1)

    if printFlag:
        print("%s%%" % result)

    return result

def batteryGetTime(printFlag = True):
    batteryState = batteryGetState(False)

    result = None
    readAttempt = 1
    while result == None and readAttempt <= PI_TOP_MAX_READ_ATTEMPTS:
        if (batteryState == "Charging"):
            rawData = busGetData(PI_TOP_BATTERY_ADDRESS, PI_TOP_BATTERY_REGISTER_CHARGING_TIME)
            if (rawData <= 2400):
                result = rawData
        elif (batteryState == "Discharging"):
            rawData = busGetData(PI_TOP_BATTERY_ADDRESS, PI_TOP_BATTERY_REGISTER_DISCHARGE_TIME)
            if (rawData <= 1800):
                result = rawData

        readAttempt = readAttempt + 1

    if readAttempt > PI_TOP_MAX_READ_ATTEMPTS:
        print("Bus read failed %i times in a row." % readAttempt, file=sys.stderr)
        exit(1)

    if printFlag:
        print("%i mins" % result)

    return result

# Check to see that minimum required number of arguments have been provided (script name is sys.argv[0])
if len(sys.argv) <= 2:
    print("Error: Device and Command are both required arguments", file=sys.stderr)
    quit(1)

device = sys.argv[1].lower()
command = sys.argv[2].lower()

if device not in ["battery"]:
    print("Error: Device must be one of the following: %s" % ARG_DEVICE_LIST, file=sys.stderr)
    quit(1)

if command not in ARG_COMMAND_LIST.get(device):
    print("Error: Command must be one of the following: %s" % ARG_COMMAND_LIST.get(device), file=sys.stderr)
    quit(1)

if device == "battery":
    if command == "state":
        batteryGetState()
    if command == "capacity":
        batteryGetCapacity()
    if command == "time":
        batteryGetTime()
