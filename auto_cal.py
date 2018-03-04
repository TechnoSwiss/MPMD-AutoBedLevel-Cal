#!/usr/bin/python

import serial
import sys
import argparse

check_max = True
max_runs = 15
runs = 0
axis = 0

trial_z = 0.0
trial_x = 0.0
trial_y = 0.0
r_value = 63.2
step_mm = 57.14

parser = argparse.ArgumentParser(description='Auto-Bed Cal. for Monoprice Mini Delta')
parser.add_argument('-p','--port',help='Serial port',required=True)
parser.add_argument('-r','--r-value',type=float,default=r_value,help='Starting r-value')
parser.add_argument('-s','--step-mm',type=float,default=step_mm,help='Set steps-/mm')
args = parser.parse_args()

#if sys.platform != 'win32': 
temp = serial.Serial(args.port, 115200, timeout=10, writeTimeout=10000, parity=serial.PARITY_ODD)
if sys.platform == 'win32':
    temp.close()
port = serial.Serial(args.port, 115200, timeout=10, writeTimeout=10000, parity=serial.PARITY_NONE)
if sys.platform != 'win32':
    temp.close()

r_value = args.r_value
step_mm = args.step_mm

port.write(('M92 X' + str(step_mm) + ' Y' + str(step_mm) + ' Z' + str(step_mm) + '\n').encode())
port.write(('M666 X0.0 Y0.0 Z0.0\n').encode())
port.write(('M665 R' + str(r_value) + '\n').encode())

while True:
    settled = 0
    runs += 1

    if runs > max_runs:
        break
    print('Calibration run : ' + str(runs) + '\n')

    port.write(('G28\n').encode())
    port.write(('G29 P2 V4\n').encode())

    while True:
        out = port.readline().decode()
        if 'G29 Auto Bed Leveling' in out:
            break

    print('Z-Axis :')
    out = port.readline().decode()
    z_axis_1 = out.split(' ')
    print(z_axis_1[6].rstrip())
    out = port.readline().decode()
    z_axis_2 = out.split(' ')
    print(z_axis_2[6].rstrip())
    z_ave = float("{0:.3f}".format((float(z_axis_1[6]) + float(z_axis_2[6])) / 2))
    print(str(z_ave) + '\n')
    if check_max:
        max = z_ave
        axis = 0

    print('X-Axis :')
    out = port.readline().decode()
    x_axis_1 = out.split(' ')
    print(x_axis_1[6].rstrip())
    out = port.readline().decode()
    x_axis_2 = out.split(' ')
    print(x_axis_2[6].rstrip())
    x_ave = float("{0:.3f}".format((float(x_axis_1[6]) + float(x_axis_2[6])) / 2))
    print(str(x_ave) + '\n')
    if check_max:
        if x_ave > max:
            max = x_ave
            axis = 1

    print('Y-Axis :')
    out = port.readline().decode()
    y_axis_1 = out.split(' ')
    print(y_axis_1[6].rstrip())
    out = port.readline().decode()
    y_axis_2 = out.split(' ')
    print(y_axis_2[6].rstrip())
    y_ave = float("{0:.3f}".format((float(y_axis_1[6]) + float(y_axis_2[6])) / 2))
    print(str(y_ave) + '\n')
    if check_max:
        if y_ave > max:
            max = y_ave
            axis = 2
        check_max = False

    print('Center :')
    out = port.readline().decode()
    center_1 = out.split(' ')
    print(center_1[6].rstrip())
    out = port.readline().decode()
    center_2 = out.split(' ')
    print(center_2[6].rstrip())
    c_ave = float("{0:.3f}".format((float(center_1[6]) + float(center_2[6])) / 2))
    print(str(c_ave) + '\n')

    #target = [max, max, max]
    target = [z_ave, x_ave, y_ave]

    z_error = float("{0:.4f}".format(z_ave - target[axis]))
    x_error = float("{0:.4f}".format(x_ave - target[axis]))
    y_error = float("{0:.4f}".format(y_ave - target[axis]))
    c_error = float("{0:.4f}".format(c_ave - ((z_ave + x_ave + y_ave) / 3)))
    print('Z-Error: ' + str(z_error) + ' X-Error: ' + str(x_error) + ' Y-Error: ' + str(y_error) + ' C-Error: ' + str(c_error) + '\n')

    if abs(z_error) >= 0.02 and axis != 0:
        trial_z = z_error + trial_z if runs < (max_runs / 2) else (z_error / 2) + trial_z
        print('M666 Z' + str(trial_z) + '\n')
        port.write(('M666 Z' + str(trial_z) + '\n').encode())
        out = port.readline().decode()
    else:
        settled += 1

    if abs(x_error) >= 0.02 and axis != 1:
        trial_x = x_error + trial_x if runs < (max_runs / 2) else (x_error / 2) + trial_x
        print('M666 X' + str(trial_x) + '\n')
        port.write(('M666 X' + str(trial_x) + '\n').encode())
        out = port.readline().decode()
    else:
        settled += 1

    if abs(y_error) >= 0.02 and axis != 2:
        trial_y = y_error + trial_y if runs < (max_runs / 2) else (y_error / 2) + trial_y
        print('M666 Y' + str(trial_y) + '\n')
        port.write(('M666 Y' + str(trial_y) + '\n').encode())
        out = port.readline().decode()
    else:
        settled += 1

    if abs(c_error) >= 0.02:
        r_value = float("{0:.4f}".format(r_value + c_error / -0.5))
        print('M665 R' + str(r_value) + '\n')
        port.write(('M665 R' + str(r_value) + '\n').encode())
        out = port.readline().decode()
    else:
        settled += 1

    if settled > 3:
        break

port.write(('M503\n').encode())

while True:
    out = port.readline().decode()
    if 'M92' in out or 'M666' in out or 'M665' in out:
        print(out.strip())
        if 'M665' in out:
            break

port.close()
