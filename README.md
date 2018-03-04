# MPMD-AutoBedLevel-Cal
This script builds on Dennis Browns Monoprice Mini Delta end-stop and delta radius calibration spreadsheet.

It builds on bborncr's gcodesender.py script https://github.com/bborncr/gcodesender.py/blob/master/gcodesender.py
and includes foosel's connection fix for OctoPrint https://github.com/OctoPrint/OctoPrint-MalyanConnectionFix/blob/master/octoprint_malyan_connection_fix/__init__.py

This script is provided as-is without ANY warranty, expressed or implied, including its sutability for the task for which it was designed.
If your printer tips up, throws up, blows up, burns up, or gets up and walks out the door, it's NOT my fault.
Use at your own risk.

Requirements:
    Python 2.7 or Python 3 (Tested with Python 2.7.9 and Python 3.6.4)
	pip install pyserial

OS:
    Linux (tested with Debian Jessie)
	Windows (tested with Win10)
	Mac (have not tested, but should work)


I'm currently running this from my OctoPrint machine (an eeePC 701 running Debian, not a RaspPi),
 if you're running this from your OctoPrint machine you'll need to run from an actual terminal (not the terminal tab on the web page).
Make sure no other process has the serial port open (if on your OctoPrint machine make sure to disconnect OctoPrint from the printer)

I wrote this script on too little sleep to save myself some time, it works, but it's not pretty and could be cleaned up quite a bit.
If I waited till I felt it was ready though, I'd probably never release it, so here it is, warts and all.

There is little error checking currently in the script (or rather none), so keep an eye on it while it's running.
The script starts by setting the defaults from Dennis Brown's calibration walkthough (these can be changed in the script):
    M92 X57.14 Y57.14 Z57.14
	M666 X0.0 Y0.0 Z0.0
	M665 R63.2

It will then walk through up to 15 cycles of bed leveling, reading out the values and calculating new M666 and M665 R values until
the error for all is less then 0.02. If it hasn't settled by the halfway point it will reduce the correction factor from just the
error value, to half the error value. On ave. it's settled on a value for me in 7 runs, if it gets all the way to 15 it just ends
leaving values were they were for the last run.

After finishing it will print out the final settings on the printer. It will not store these values. You can issue an M500 command
to save the to the EEPROM, or record them to use in a startup script. The delta radius value isn't restored on startup, so you'll
need to record at least that value and re-enter it each time the printer is powered up.
