#!/usr/bin/python

# Updated version of the original script
# Most of the changes are just to restructure code
# Main functionality additions are handling of serial errors and support for additional arguments
# Tested on Ubuntu 16.02 with Python2.7, Windows 2016 Server with Python3.6 and MacOS High Sierra with Python2.7

from serial import Serial, SerialException, PARITY_ODD, PARITY_NONE
import sys
import argparse
import sys

def establish_serial_connection(port, speed=115200, timeout=10, writeTimeout=10000):
    # Hack for USB connection
    # There must be a way to do it cleaner, but I can't seem to find it
    try:
        temp = Serial(port, 115200, timeout=10, writeTimeout=10000, parity=PARITY_ODD)
        if sys.platform == 'win32':
            temp.close()
        conn = Serial(port, 115200, timeout=10, writeTimeout=10000, parity=PARITY_NONE)
        conn.setRTS(False)#needed on mac
        if sys.platform != 'win32':
            temp.close()
        return conn
    except SerialException as e:
        print ("Could not connect to {0} at baudrate {1}\nSerial error: {2}".format(port, str(speed), e))
        return None
    except IOError as e:
        print ("Could not connect to {0} at baudrate {1}\nIO error: {2}".format(port, str(speed), e))
        return None

def get_current_values(port):

    # This function makes lots of assumptions about the output of the printer,
    # but I am not sure if writing it in regex or improving it any other way would make any difference
    # as this is unique for printer with this code and may not work for anything else

    port.write(('G28\n').encode())
    port.write(('G29 P2 V4\n').encode())

    while True:
        out = port.readline().decode()
        if 'G29 Auto Bed Leveling' in out:
            break

    out = port.readline().decode()
    z_axis_1 = out.split(' ')
    out = port.readline().decode()
    z_axis_2 = out.split(' ')
    z_ave = float("{0:.3f}".format((float(z_axis_1[6]) + float(z_axis_2[6])) / 2))
    print('Z-Axis :{0}, {1} Average:{2}'.format(z_axis_1[6].rstrip(),z_axis_2[6].rstrip(),str(z_ave)))

    out = port.readline().decode()
    x_axis_1 = out.split(' ')
    out = port.readline().decode()
    x_axis_2 = out.split(' ')
    x_ave = float("{0:.3f}".format((float(x_axis_1[6]) + float(x_axis_2[6])) / 2))
    print('X-Axis :{0}, {1} Average:{2}'.format(x_axis_1[6].rstrip(),x_axis_2[6].rstrip(),str(x_ave)))

    out = port.readline().decode()
    y_axis_1 = out.split(' ')
    out = port.readline().decode()
    y_axis_2 = out.split(' ')
    y_ave = float("{0:.3f}".format((float(y_axis_1[6]) + float(y_axis_2[6])) / 2))
    print('Y-Axis :{0}, {1} Average:{2}'.format(y_axis_1[6].rstrip(),y_axis_2[6].rstrip(),str(y_ave)))

    out = port.readline().decode()
    center_1 = out.split(' ')
    out = port.readline().decode()
    center_2 = out.split(' ')
    c_ave = float("{0:.3f}".format((float(center_1[6]) + float(center_2[6])) / 2))
    print('Center :{0}, {1} Average:{2}'.format(center_1[6].rstrip(),center_2[6].rstrip(),str(c_ave)))

    return z_ave, x_ave, y_ave, c_ave

def find_max_value(my_list):
    return max(my_list)

def determine_error(z_ave, x_ave, y_ave, c_ave, max_value):
    z_error = float("{0:.4f}".format(z_ave - max_value))
    x_error = float("{0:.4f}".format(x_ave - max_value))
    y_error = float("{0:.4f}".format(y_ave - max_value))
    c_error = float("{0:.4f}".format(c_ave - ((z_ave + x_ave + y_ave) / 3)))
    print('Z-Error: ' + str(z_error) + ' X-Error: ' + str(x_error) + ' Y-Error: ' + str(y_error) + ' C-Error: ' + str(c_error) + '\n')

    return z_error, x_error, y_error, c_error


def calibrate(port, z_error, x_error, y_error, c_error, trial_x, trial_y, trial_z,r_value, max_runs, runs):
    calibrated = True
    if abs(z_error) >= 0.02:
        new_z = z_error + trial_z if runs < (max_runs / 2) else (z_error / 2) + trial_z
        calibrated = False
    else:
        new_z = trial_z

    if abs(x_error) >= 0.02:
        new_x = x_error + trial_x if runs < (max_runs / 2) else (x_error / 2) + trial_x
        calibrated = False
    else:
        new_x = trial_x

    if abs(y_error) >= 0.02:
        new_y = y_error + trial_y if runs < (max_runs / 2) else (y_error / 2) + trial_y
        calibrated = False
    else:
        new_y = trial_y

    if abs(c_error) >= 0.02:
        new_r = float("{0:.4f}".format(r_value + c_error / -0.5))
        calibrated = False
    else:
        new_r = r_value

    if calibrated:
        print ("Final values\nM666 Z{0} X{1} Y{2} \nM665 R{3}".format(str(new_z),str(new_x),str(new_y),str(new_r)))
    else:
        set_M_values(port, new_z, new_x, new_y, new_r)

    return calibrated, new_z, new_x, new_y, new_r

def set_M_values(port, z, x, y, r):
    print ("Setting values M666 Z{0} X{1} Y{2}, M665 R{3}".format(str(z),str(x),str(y),str(r)))

    port.write(('M666 X{0} Y{1} Z{2}\n'.format(str(x), str(y), str(z))).encode())
    out = port.readline().decode()
    port.write(('M665 R{0}\n'.format(str(r))).encode())
    out = port.readline().decode()


def run_calibration(port, trial_x, trial_y, trial_z,r_value, max_runs, max_error, runs=0):
    runs += 1

    if runs > max_runs:
        sys.exit("Too many calibration attempts")
    print('\nCalibration run {1} out of {0}'.format(str(max_runs), str(runs)))

    z_ave, x_ave, y_ave, c_ave = get_current_values(port)

    max_value = find_max_value([z_ave, x_ave, y_ave])

    z_error, x_error, y_error, c_error = determine_error(z_ave, x_ave, y_ave, c_ave, max_value)

    if abs(max([z_error, x_error, y_error, c_error], key=abs)) > max_error and runs > 1:
        sys.exit("Calibration error on non-first run exceeds set limit")

    calibrated, new_z, new_x, new_y, new_r = calibrate(port, z_error, x_error, y_error, c_error, trial_x, trial_y, trial_z,r_value, max_runs, runs)

    if calibrated:
        print ("Calibration complete")
    else:
        run_calibration(port, new_x, new_y, new_z, new_r, max_runs, max_error, runs)


def main():
    max_runs = 14
    runs = 0
    axis = 0
    max_error = 1

    trial_z = 0.0
    trial_x = 0.0
    trial_y = 0.0
    r_value = 63.2
    step_mm = 57.14

    parser = argparse.ArgumentParser(description='Auto-Bed Cal. for Monoprice Mini Delta')
    parser.add_argument('-p','--port',help='Serial port',required=True)
    parser.add_argument('-r','--r-value',type=float,default=r_value,help='Starting r-value')
    parser.add_argument('-s','--step-mm',type=float,default=step_mm,help='Set steps-/mm')
    parser.add_argument('-me','--max-error',type=float,default=max_error,help='Maximum acceptable calibration error on non-first run')
    parser.add_argument('-mr','--max-runs',type=int,default=max_runs,help='Maximum attempts to calibrate printer')
    args = parser.parse_args()

    port = establish_serial_connection(args.port)

    if port:
        r_value = args.r_value
        step_mm = args.step_mm
        max_runs = args.max_runs

        print ('Setting up M92 value')
        #Shouldn't need it once firmware bug is fixed
        port.write(('M92 X{0} Y{0} Z{0}\n'.format(str(step_mm))).encode())
        out = port.readline().decode()

        set_M_values(port, trial_z, trial_x, trial_y, r_value)

        print ('\nStarting calibration')

        run_calibration(port, trial_x, trial_y, trial_z,r_value, max_runs, args.max_error)

        port.close()



if __name__ == '__main__':
    main()