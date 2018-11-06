#!/usr/bin/python

from serial import Serial, SerialException, PARITY_ODD, PARITY_NONE
import sys
import argparse
import traceback

# Most Commands from: https://reprap.org/wiki/G-code
# Some Commands from: https://www.mpminidelta.com/g29
class MpmdConnection:

    @staticmethod
    def establishSerialConnection(port, speed=115200, timeout=10, writeTimeout=10000):
        # Hack for USB connection
        # There must be a way to do it cleaner, but I can't seem to find it
        try:
            temp = Serial(port, speed, timeout=timeout, writeTimeout=writeTimeout, parity=PARITY_ODD)
            if sys.platform == 'win32':
                temp.close()
            conn = Serial(port, speed, timeout=timeout, writeTimeout=writeTimeout, parity=PARITY_NONE)
            conn.setRTS(False) #needed on mac
            if sys.platform != 'win32':
                temp.close()
            return conn
        except SerialException as e:
            print ("Could not connect to {0} at baudrate {1}\nSerial error: {2}".format(port, str(speed), e))
            raise e
        except IOError as e:
            print ("Could not connect to {0} at baudrate {1}\nIO error: {2}".format(port, str(speed), e))
            raise e

    def __init__(self, port):
        self.connection = MpmdConnection.establishSerialConnection(port=port)

    def write(self, command):
        command = command.strip();
        print("Send: " + command)
        self.connection.write((command + '\n').encode())

    def readline(self):
        line = self.connection.readline().decode().strip()
        print("MPMD: " + line)
        return line

    def readNonBlankLine(self):
        out = ''
        while out == '':
            out = self.readline()
        return out;

    def close(self):
        self.connection.close()

    # M92: Set axis_steps_per_unit
    # Xnnn Steps per unit for the X drive
    # Ynnn Steps per unit for the Y drive
    # Znnn Steps per unit for the Z drive
    # Ennn Steps per unit for the extruder drive(s)
    def setAxisStepsPerUnit(self, x=None, y=None, z=None, e=None):
        if (x == None and y == None and z == None and e == None):
            print("No arguments passed, not sending anything.")
            return

        print("Configuring Axis Steps Per Unit.")
        command = 'M92';
        if (x != None):
            command = command + ' X' + str(x)
        if (y != None):
            command = command + ' Y' + str(y)
        if (z != None):
            command = command + ' Z' + str(z)
        if (e != None):
            command = command + ' E' + str(e)
        self.write(command)

    # Xnnn X axis endstop adjustment
    # Ynnn Y axis endstop adjustment
    # Znnn Z axis endstop adjustment
    # Annn X bed tilt in percent*
    # Bnnn Y bed tilt in percent*
    # consumeOutput: Have this function read (and ignore) the output/response from the printer. Hence calling code can assume there is no response.
    def setDeltaEndstopAdjustment(self, x=None, y=None, z=None, a=None, b=None, consumeOutput=False):
        if (x == None and y == None and z == None and a == None and b == None):
            print("No arguments passed, not sending anything.")
            return

        print("Configuring Delta Endstop Adjustment")
        command = 'M666';
        if (x != None):
            command = command + ' X' + str(x)
        if (y != None):
            command = command + ' Y' + str(y)
        if (z != None):
            command = command + ' Z' + str(z)
        if (a != None):
            command = command + ' A' + str(a)
        if (b != None):
            command = command + ' B' + str(b)
        self.write(command)
        if consumeOutput:
            self.readline() # Read & Ignore the response

    # Lnnn Diagonal rod length
    # Rnnn Delta radius
    # Snnn Segments per second1
    # Bnnn Safe probing radius2,3
    # Hnnn Delta height defined as nozzle height above the bed when homed after allowing for endstop corrections 2
    # Xnnn X tower position correction2,4
    # Ynnn Y tower position correction2,4
    # Znnn Z tower position correction2,4
    # consumeOutput: Have this function read (and ignore) the output/response from the printer. Hence calling code can assume there is no response.
    def setDeltaConfiguration(self, l=None, r=None, s=None, b=None, h=None, x=None, y=None, z=None, consumeOutput=False):
        if (l == None and r == None and s == None and b == None and h == None and x == None and y == None and z == None):
            print("No arguments passed, not sending anything.")
            return

        print("Setting Delta Configuration")
        command = 'M665';

        if (l != None):
            command = command + ' L' + str(l)
        if (r != None):
            command = command + ' R' + str(r)
        if (s != None):
            command = command + ' S' + str(s)
        if (b != None):
            command = command + ' B' + str(b)
        if (h != None):
            command = command + ' H' + str(h)

        if (x != None):
            command = command + ' X' + str(x)
        if (y != None):
            command = command + ' Y' + str(y)
        if (z != None):
            command = command + ' Z' + str(z)
        self.write(command)
        if consumeOutput:
            self.readline() # Read & Ignore the response

    # G28: Move to Origin (Home)
    # Parameters
    # This command can be used without any additional parameters.
    # X Flag to go back to the X axis origin
    # Y Flag to go back to the Y axis origin
    # Z Flag to go back to the Z axis origin
    def moveToHome(self, x=False, y=False, z=False):
        print("Moving to Home/Origin")
        command = 'G28'
        if (x):
            command = command + ' X'
        if (y):
            command = command + ' Y'
        if (z):
            command = command + ' Z'
        self.write(command)

    # G29 - Automatic Bed Leveling
    # G29       ; 3 point = 3 corners (center point using calculation) - DOUBLE TAP
    # G29 P1 ; 3 point = 3 corners (center point using calculation) - DOUBLE TAP
    # G29 P2 ; 4 point = 3 corners + center (real center) - DOUBLE TAP
    # G29 P3 ; 3x3 matrix - DOUBLE TAP
    # G29 P4 ; 4x4 matrix - DOUBLE TAP
    # G29 P5 ; 5x5 matrix - DOUBLE TAP
    # G29 P6 ; 6x6 matrix - DOUBLE TAP
    # G29 C[offset] ; offset option to fine tune center height. Does not apply to P3, P4, P5, or P6
    # G29 Z[offset] ; matrix/mesh offset
    # G29 P[mesh] Z[offset] ; Parameters may be combined
    # G29 Z[offset] P[mesh] = G29 P[mesh] Z[offset] ; Parameter order does not matter
    def automaticBedLeveling(self, program=1, c=None, z=None, p=None, reportProbeValues=False):
        if (program < 1 or program > 6):
            print("Unknown program number, only 1-6 are supported. Found: " + str(program))
            return
        print("Starting Automatic Bed Leveling" + (", with probe value reporting." if reportProbeValues else "."))
        command = "G29 P" + str(program)
        if (c != None):
            command = command + ' C' + str(c)
        if (z != None):
            command = command + ' Z' + str(z)
        if (p != None):
            command = command + ' P' + str(p)
        if (reportProbeValues):
            command = command + ' V4'
        self.write(command)

    # M500: Store parameters in non-volatile storage
    def storeParametersInNonVolatileStorage(self):
        command = "M500"
        self.write(command)

    # M503: Print settings
    # M503 S0 ; Settings as G-code only (Marlin 1.1)
    def printSettings(self, settingsAsGCodeOnly=False):
        command = "M503"
        if (settingsAsGCodeOnly):
            command = command + ' S0'
        self.write(command)


class MpmdAutomaticCalibration:
    # Arbitrary small tollerance, all axis must be correct to within this range for the calibration to finish early (i.e. to finish before max_runs have occured.)
    _defaultMaxError = 0.02
    _defaultMaxRuns = 15
    # Not sure where this comes from - would be good to udpate this comment if you know?
    # This is the default initial r-value, actual value will be calculated/calibrated by the script.
    _defaultRValue = 61.85
    # Found this value on https://www.reddit.com/r/mpminidelta/comments/8xhcy6/new_version_of_marlin4mpmd_v120_add_sd_and_lcd/
    # Not sure how it's found/calculated, but it seems to work for my MPMD. Would be good to update this comment if you know.
    # Value from old script (for old firmware?) was: 57.14, this appears to have doubled in firmware update.
    _defaultStepMm = 114.28
    # Not sure how it's found/calculated, but it seems to work for my MPMD. Would be good to update this comment if you know.
    _defaultLValue = 123.8

    def parseArgs (self):
        parser = argparse.ArgumentParser(description='Auto-Bed Calibration for Monoprice Mini Delta')
        parser.add_argument('-p', '--port', help='Serial port', required=True)
        parser.add_argument('-r', '--r-value', type=float, default=self._defaultRValue, help='Starting r-value')
        parser.add_argument('-s', '--step-mm', type=float, default=self._defaultStepMm, help='Set steps-/mm')
        parser.add_argument('-l','--l-value', type=float, default=self._defaultLValue, help='Starting l-value')
        parser.add_argument('-me','--max-error',type=float, default=self._defaultMaxError, help='Maximum acceptable calibration error on non-first run')
        parser.add_argument('-mr','--max-runs',type=int, default=self._defaultMaxRuns, help='Maximum attempts to calibrate printer')
        parser.add_argument('-lo', '--load-from-eeprom', type=bool, default=False, help='Loads the initial values for X,Y,Z and R from EEPROM, rather than starting from 0. This is especially useful if you have ever calibrated your printer before and just want a tune-up. This will override r-value arg.')
        parser.add_argument('-w', '--write-to-eeprom', type=bool, default=False, help="Write the values to the printer's non-volitile storage after finding them.")
        args = parser.parse_args()
        # self.logger.info(args)
        return args


    # This function makes lots of assumptions about the output of the printer,
    # but I am not sure if writing it in regex or improving it any other way would make any difference
    # as this is unique for printer with this code and may not work for anything else
    def getCurrentValues(self):
        self.printer.moveToHome()
        self.printer.automaticBedLeveling(program=2, reportProbeValues=True)

        while True:
            out = self.printer.readNonBlankLine()
            if 'G29 Auto Bed Leveling' in out:
                break

        x_avg = self.calibrateAxis('X-Axis')
        y_avg = self.calibrateAxis('Y-Axis')
        z_avg = self.calibrateAxis('Z-Axis')
        c_avg = self.calibrateAxis('Center')
        return x_avg, y_avg, z_avg, c_avg

    def calibrateAxis(self, axisName):
        out = self.printer.readNonBlankLine()
        touch1 = out.split(' ')
        out = self.printer.readNonBlankLine()
        touch2 = out.split(' ')
        avg = float("{0:.3f}".format((float(touch1[6]) + float(touch2[6])) / 2))
        print('{0} :{1}, {2} Average:{3}'.format(axisName, touch1[6].rstrip(), touch2[6].rstrip(), str(avg)))
        return avg

    def loadConfigFromEeprom(self):
        self.printer.printSettings(settingsAsGCodeOnly=True)
        out = self.printer.readline()
        x = 0.0
        y = 0.0
        z = 0.0
        r = 0.0
        while True:
            if 'echo: ' in out:
                # Skip over 'echo' lines, we want the PURE lines (so that our indexes are correct)
                continue
            if 'M666' in out:
                parts = out.split(' ')
                x = float(parts[1][1:])
                y = float(parts[2][1:])
                z = float(parts[3][1:])
            if 'M665' in out:
                parts = out.split(' ')
                r = float(parts[2][1:])
                # M665 is also the last line, so we can sto reading the config now.
                break
            out = self.printer.readline()
        return (x, y, z, r)

    def determineError(self, x_avg, y_avg, z_avg, c_avg):
        # Not sure why we compare each axis to the value of the axis with the largest historical difference, but the algorighm seems to work
        # Would be good if someone could explain that here if they know what's going on!
        max_average = max([x_avg, y_avg, z_avg])

        x_error = float("{0:.4f}".format(x_avg - max_average))
        y_error = float("{0:.4f}".format(y_avg - max_average))
        z_error = float("{0:.4f}".format(z_avg - max_average))
        c_error = float("{0:.4f}".format(c_avg - ((x_avg + y_avg + z_avg) / 3)))
        print('X-Error: ' + str(x_error) + ' Y-Error: ' + str(y_error) + ' Z-Error: ' + str(z_error) + ' C-Error: ' + str(c_error))

        return x_error, y_error, z_error, c_error

    def runCalibrationLoop(self, run_count, trial_x, trial_y, trial_z, trial_r):
        print('\nCalibration run : ' + str(run_count) + '\n')

        x_avg, y_avg, z_avg, c_avg = self.getCurrentValues()
        x_error, y_error, z_error, c_error = self.determineError(x_avg, y_avg, z_avg, c_avg)

        calibrated = True
        if abs(z_error) >= self._max_error:
            new_z = z_error + trial_z if run_count < (self._max_runs / 2) else (z_error / 2) + trial_z
            calibrated = False
        else:
            new_z = trial_z

        if abs(x_error) >= self._max_error:
            new_x = x_error + trial_x if run_count < (self._max_runs / 2) else (x_error / 2) + trial_x
            calibrated = False
        else:
            new_x = trial_x

        if abs(y_error) >= self._max_error:
            new_y = y_error + trial_y if run_count < (self._max_runs / 2) else (y_error / 2) + trial_y
            calibrated = False
        else:
            new_y = trial_y

        if abs(c_error) >= self._max_error:
            trial_r = float("{0:.4f}".format(trial_r + c_error / -0.5))
            calibrated = False
        else:
            new_r = trial_r

        self.printer.setDeltaEndstopAdjustment(x=new_x, y=new_y, z=new_z, consumeOutput=True)
        self.printer.setDeltaConfiguration(r=new_r, consumeOutput=True)

        return new_x, new_y, new_z, new_r, calibrated

    def calibrate(self):
        args = self.parseArgs()
        self.printer = MpmdConnection(args.port)

        self._max_error = args.max_error
        self._max_runs = args.max_runs
        step_mm = args.step_mm

        initial_x = 0.0
        initial_y = 0.0
        initial_z = 0.0
        initial_r = args.r_value
        if (args.load_from_eeprom):
            print("Loading initial values from printer EEPROM.")
            (initial_x, initial_y, initial_z, initial_r) = self.loadConfigFromEeprom()

        print("Initial values will be: x=" + str(initial_x) + ", y=" + str(initial_y) + ", z=" + str(initial_z) + ", r=" + str(initial_r))

        trial_x = initial_x
        trial_y = initial_y
        trial_z = initial_z
        trial_r = initial_r

        print("Initializing printer with default values.")
        # Shouldn't need 'setAxisStepsPerUnit' once firmware bug is fixed
        self.printer.setAxisStepsPerUnit(x=step_mm, y=step_mm, z=step_mm)
        self.printer.setDeltaEndstopAdjustment(x=trial_x, y=trial_y, z=trial_z)
        self.printer.setDeltaConfiguration(r=trial_r, l=args.l_value)
        print(' ')

        run_count = 0
        while True:
            run_count += 1
            if run_count > self._max_runs:
                print('Max-Runs(' + str(self._max_runs) + ') exceeded without settling on final values. Finishing.')
                break

            trial_x, trial_y, trial_z, trial_r, calibrated = self.runCalibrationLoop(run_count, trial_x, trial_y, trial_z, trial_r)

            if calibrated:
                break

        self.printer.printSettings()
        while True:
            out = self.printer.readline()
            if 'M665' in out:
                break

        if args.write_to_eeprom:
            self.printer.storeParametersInNonVolatileStorage()
            while True:
                out = self.printer.readline()
                if 'Settings Stored' in out:
                    break
        else:
            print("Did not store settings to printer EEPROM.")

        self.printer.moveToHome()

        print("\n")
        print("Finished calibration after " + str(run_count) + " runs.")
        print("Initial values were: x=" + str(initial_x) + ", y=" + str(initial_y) + ", z=" + str(initial_z) + ", r=" + str(initial_r))
        print("Final values are: x=" + str(trial_x) + ", y=" + str(trial_y) + ", z=" + str(trial_z) + ", r=" + str(trial_r))
        print("\n")
        self.printer.close()

def main():
    try:
        calibrator = MpmdAutomaticCalibration()
        calibrator.calibrate()
    except:
        sys.stderr.write("Exception occurred: " + traceback.format_exc())

if __name__ == '__main__':
    main()
