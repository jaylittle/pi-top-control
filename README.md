# Pi-Top Control
Are you interested in running a non-Raspbian based distribution on your pi-top device? If so, then this
is the repository for you.  After running into various difficulties when it came to making the existing
pi-top package scripts working on Arch Linux.

As a result of this I decided to roll my own script in python that provides an easy interface for managing
various aspects of the pi-top within non-Raspbian operating systems.

This script supports controlling/querying the following aspects of the Pi-Top Hub controller:

1. Backlight
2. Battery
3. Speaker

# Requirements

### 1. Pi-Top and rpi3
 
This script has been written and tested on a Pi-Top system using a Raspberry Pi 3.
It may work with a Pi-Top Ceed and it may work with an Raspberry Pi 2, but I have
neither device in my possession and am unable to adequately test as a result.

### 2. Linux

In theory this script will work on Raspbian provided the appropriate system mods are made.
However it is primarily designed to facilitate making Pi-Top work on non Raspbian based
distributions.  To that end, this script has been primarily tested using Arch Linux.

### 3. Python 3 and modules

Python 3 and the smbus and spidev modules are required to run this script.

### 4. Access to the /dev/i2c-* and /dev/spidev* devices

You can either run these scripts as root or install an appropriate udev rule which provides access to non-root
users.  An example of a possible udev rule is included as part of this repository.

# Commands

Each call to ptctl.py requires at least two arguments: A device and a command.

Calls to the speaker device require a third parameter which represents the bus address of the specific speaker.
For example on my pi-top which only has a single speaker connected to the hub, the address is 0x72.  The
device of your speaker can be narrowed down by running the following command:

i2cdetect -y 1

Speaker addresses typically range from 0x71 and up.

The available devices and commands are:

<ol>
    <li>
        battery
        <ul>
            <li>state</li>
            <li>capacity (returns percentage of battery remaining)</li>
            <li>time (returns estimated time for discharing/charging)</li>
        </ul>
    </li>
    <li>
        backlight
        <ul>
            <li>state</li>
            <li>increase (increases brightness unless its already 10)</li>
            <li>decrease (decreases brightness unless its already 1)</li>
            <li>off</li>
            <li>on (turns on the backlight and sets brightness to 5)</li>
            <li>1 thru 10 (represents tbe absolute brightness value)</li>
        </ul>
    </li>
    <li>
        speaker
        <ul>
            <li>mono [hex address of speaker]</li>
            <li>left [hex address of speaker]</li>
            <li>right [hex address of speaker]</li>
        </ul>
    </li>
    <li>
        system
        <ul>
            <li>state</li>
            <li>off (turns off the hub - should be executed only during shutdown)</li>
        </ul>
    </li>
    <li>
        lid
        <ul>
            <li>state</li>
        </ul>
    </li>
</ol>
