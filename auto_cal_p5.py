#!/usr/bin/python

# Updated version of the original script
# Most of the changes are just to restructure code
# Main functionality additions are handling of serial errors and support for additional arguments
# Tested on Ubuntu 16.02 with Python2.7, Windows 2016 Server with Python3.6 and MacOS High Sierra with Python2.7

# Original Project Found here:
# https://github.com/TechnoSwiss/MPMD-AutoBedLevel-Cal
# This version was made to be compatible with Dennis Brown's G29 P5 Spreadsheet:
# https://www.facebook.com/groups/mpminideltaowners/permalink/2186865287995612/
# G29 P5 V4 Converted to manual probes for cross-firmware compatibility:
# https://github.com/mcheah/Marlin4MPMD/wiki/Calibration#user-content-m665m666-delta-parameter-calibrations

from serial import Serial, SerialException, PARITY_ODD, PARITY_NONE
import sys
import argparse
import traceback
import json
import statistics
import numpy as np
from scipy.interpolate import griddata



def establish_serial_connection(port, speed=115200, timeout=10, writeTimeout=10000):
    # Hack for USB connection
    # There must be a way to do it cleaner, but I can't seem to find it
    try:
        temp = Serial(port, speed, timeout=timeout, writeTimeout=writeTimeout, parity=PARITY_ODD)
        if sys.platform == 'win32':
            temp.close()
        conn = Serial(port, speed, timeout=timeout, writeTimeout=writeTimeout, parity=PARITY_NONE)
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

def get_points(port):
    while True:
        out = port.readline().decode()
        if 'Bed ' in out:
            break

    return out.split(' ')

def get_current_values(port, firmFlag):
    # Replacing G29 P5 with manual probe points for cross-firmware compatibility
    # G28 ; home
    # G1 Z15 F6000; go to safe distance
    # Start Loop
    #     G1 X## Y##; go to specified location
    #     G30 ;probe bed for z values
    #     G30 ;probe bed again for z values
    # End Loop
    # G28 ; return home
    
    # Initialize G29 P5 V4 Table
    number_cols = 7 
    number_rows = 21
    x_list = [None]*number_rows
    y_list = [None]*number_rows
    z1_list = [None]*number_rows
    z2_list = [None]*number_rows
    z_avg_list = [None]*number_rows
    dtap_list = [None]*number_rows
    dz_list = [None]*number_rows
    dz_test = [None]*number_rows
    
    # Define Table Indices
    ix = 0
    iy = 1
    iz1 = 2
    iz2 = 3
    izavg = 4 
    idtap = 5
    idz = 6
    
    # Assign X Coordinates (G29 P5)
    x_list[0] = -25
    x_list[1] = 0
    x_list[2] = 25
    x_list[3] = 50
    x_list[4] = 25
    x_list[5] = 0
    x_list[6] = -25
    x_list[7] = -50
    x_list[8] = -50
    x_list[9] = -25
    x_list[10] = 0
    x_list[11] = 25
    x_list[12] = 50
    x_list[13] = 50
    x_list[14] = 25
    x_list[15] = 0
    x_list[16] = -25
    x_list[17] = -50
    x_list[18] = -25
    x_list[19] = 0
    x_list[20] = 25
    
    # Assign Y Coordinates (G29 P5)
    y_list[0] = -50
    y_list[1] = -50
    y_list[2] = -50
    y_list[3] = -25
    y_list[4] = -25
    y_list[5] = -25
    y_list[6] = -25
    y_list[7] = -25
    y_list[8] = 0
    y_list[9] = 0
    y_list[10] = 0
    y_list[11] = 0
    y_list[12] = 0
    y_list[13] = 25
    y_list[14] = 25
    y_list[15] = 25
    y_list[16] = 25
    y_list[17] = 25
    y_list[18] = 50
    y_list[19] = 50
    y_list[20] = 50

    # Send Gcodes
    port.write(('G28\n').encode()) # Home
    
    if firmFlag == 1: 
        # Marlin
        port.write(('G1 Z15 F6000\n').encode()) # Move to safe distance
    else:
        # Stock Firmware
        port.write(('G29 P5 V4\n').encode())

        while True:
            out = port.readline().decode()
            #print("{0}\n".format(out))
            if 'G29 Auto Bed Leveling' in out:
                break
        
    # Loop through all 
    for ii in range(len(x_list)):
        
        if firmFlag == 1: 
            # Marlin
            
            # Move to desired position
            port.write(('G1 X{0} Y{1}\n'.format(x_list[ii], y_list[ii])).encode()) 
            #print('Sending G1 X{0} Y{1}\n'.format(x_list[ii], y_list[ii]))
            
            # Probe Z values
            port.write(('G30\n').encode())
            z_axis_1 = get_points(port)
            port.write(('G30\n').encode())
            z_axis_2 = get_points(port)
        else:
            # Stock Firmware
            z_axis_1 = get_points(port)
            z_axis_2 = get_points(port)
        
        # Populate most of the table values
        z1_list[ii] = float(z_axis_1[6])
        z2_list[ii] = float(z_axis_2[6])
        z_avg_list[ii] = float("{0:.4f}".format((z1_list[ii] + z2_list[ii]) / 2.0))
        dtap_list[ii] = z2_list[ii] - z1_list[ii]
        #print('Received: X:{0} X:{1} Y:{2} Y:{3} Z1:{4} Z2:{5}\n\n'.format(str(x_list[ii]), str(z_axis_1[2]), str(y_list[ii]), str(z_axis_1[4]), z1_list[ii], z2_list[ii]))
    
    # Find the Median Reference
    z_med = statistics.median(z_avg_list)
    
    # Calculate z diff
    for ii in range(len(x_list)):
        dz_list[ii] = z_avg_list[ii] - z_med
        
    # Empty out remaining lines for stock firmware
    if firmFlag == 0: 
        for ii in range(6):
            out = port.readline().decode()
    
    return x_list, y_list, z1_list, z2_list, z_avg_list, dtap_list, dz_list

def xyz_list2array(xl,yl,zl):
    # Create Contour Lookup/Interpolation Function
    coord_xy_list = []
    coord_z_list = []
    for ii in range(len(xl)):
        coord_xy_list.append([float(xl[ii]),float(yl[ii])])
        coord_z_list.append(float(zl[ii]))
        
    # Convert to Array
    xy_array = np.array(coord_xy_list)
    z_array = np.array(coord_z_list)
    
    return xy_array, z_array

def linear_interp(x0, x1, z0, z1, xq):
    zq = z0 + (xq-x0)*(z1-z0)/(x1-x0)
    return zq
    
def calculate_contour(x_list, y_list, dz_list, runs, xhigh, yhigh, zhigh, minterp):
    
    # Redefine Lists
    x_list_new = x_list.copy()
    y_list_new = y_list.copy()
    dz_list_new = dz_list.copy()
    
    # Define contour boundaries and steps
    xmin = min(x_list_new)
    xmax = max(x_list_new)
    ymin = min(y_list_new)
    ymax = max(y_list_new)
    dprobe = 25.0; # Distance Betqeen Probe Points
    ngrid = 3.0 # Grid Cell Spacing for the Contour
    dx = dprobe/ngrid
    dy = dx
    nmax = int(round((ymax-ymin)/dy))
    
    # Create Contour Lookup/Interpolation Function
    coord_xy, coord_z = xyz_list2array(x_list_new,y_list_new,dz_list_new)
    
    # Copy Equations from Dennis's Spreadsheet and put them in the lookup grid
    # Put inside if statement incase we want to try other interpolation methods
    # Anything other than 1 simply uses Python's griddata with the probed points.
    if minterp == 1: 
    
        # Fill in based on known values across the horizontal
        iside = -1
        nknown = int(round((ymax-ymin)/dprobe))
        for iy in range(nknown):
            # Current Fixed Value
            ytmp = ymin + float(iy)*dprobe
            y0 = ytmp
            y1 = ytmp
            yq = ytmp
            # Set Start/End indices for circular base
            if ytmp == ymin or ytmp == ymax:
                iStart = int(round(ngrid))
                iEnd = nmax-int(round(ngrid))
            else:
                iStart = 0
                iEnd = nmax-1
            # Loop through all x-values
            for ix in range(nmax): 
                xq = xmin + float(ix)*dx
                #print("x={0} y={1} ix={2} iy={3} mod={4} iStart = {5} iEnd = {6}\n\n".format(str(xq),str(yq),str(ix),str(iy),str(ix%ngrid),str(iStart),str(iEnd)))
                if ix >= iStart and ix <= iEnd:
                    if int(round(ix%ngrid)) == 0: # Set Known Values
                        if ix == iStart:
                            x0 = xmin + dx*float(ix)
                            x1 = x0 + dprobe
                            #print("iStart={0}\n".format(str(iStart)))
                            #print("Known Point x0 = {0}".format(str(x0)))
                        else:
                            x0 = x1
                            x1 = x0 + dprobe
                            #print("Known Point\n")
                            #print("Known Point x0 = {0}".format(str(x0)))
                        z0 = float(griddata(coord_xy, coord_z, (x0   , y0)))
                        z1 = float(griddata(coord_xy, coord_z, (x1   , y1)))
                    else: #  Interpolate Between Known Values
                        zq = linear_interp(x0, x1, z0, z1, xq)
                        x_list_new.append(xq)
                        y_list_new.append(yq)
                        dz_list_new.append(zq)
                        #print("Interp Test: {0} {1} {2}\n".format(str(xq),str(yq),str(zq)))
                        #print("z0={0} z1={1}".format(str(z0),str(z1)))
                #else:
                    #print("Outside of grid\n")
            
        # Fill in based on known values across the vertical
        nknown = int(round((xmax-xmin)/dprobe))
        for ix in range(nknown):
            # Current Fixed Value
            xtmp = xmin + float(ix)*dprobe
            x0 = xtmp
            x1 = xtmp
            xq = xtmp
            # Set Start/End indices for circular base
            if xtmp == xmin or xtmp == xmax:
                iStart = int(round(ngrid))
                iEnd = nmax-int(round(ngrid))
            else:
                iStart = 0
                iEnd = nmax-1
            # Loop through all y-values
            for iy in range(nmax): 
                yq = ymin + float(iy)*dy
                #print("x={0} y={1} ix={2} iy={3} mod={4} iStart = {5} iEnd = {6}\n\n".format(str(xq),str(yq),str(ix),str(iy),str(ix%ngrid),str(iStart),str(iEnd)))
                if iy >= iStart and iy <= iEnd:
                    if int(round(iy%ngrid)) == 0: # Set Known Values
                        if iy == iStart:
                            y0 = ymin + dy*float(iy)
                            y1 = y0 + dprobe
                            #print("iStart={0}\n".format(str(iStart)))
                            #print("Known Point y0 = {0} y1 = {1} yq = {2}".format(str(y0), str(y1), str(yq)))
                        else:
                            y0 = y1
                            y1 = y0 + dprobe
                            #print("Known Point\n")
                            #print("Known Point y0 = {0} y1 = {1} yq = {2}".format(str(y0), str(y1), str(yq)))
                        z0 = float(griddata(coord_xy, coord_z, (x0   , y0)))
                        #print("x0={0} y0={1} z0={2}".format(str(x0), str(y0), str(z0)))
                        z1 = float(griddata(coord_xy, coord_z, (x1   , y1)))
                        #print("x1={0} y1={1} z1={2}".format(str(x1), str(y1), str(z1)))
                    else: #  Interpolate Between Known Values
                        zq = linear_interp(y0, y1, z0, z1, yq)
                        x_list_new.append(xq)
                        y_list_new.append(yq)
                        dz_list_new.append(zq)
                        #if xtmp == 0.0:
                            #print("Interp Test: {0} {1} {2}".format(str(xq),str(yq),str(zq)))
                            #print("z0={0} z1={1}\n".format(str(z0),str(z1)))
                #else:
                    #print("Outside of grid\n")
            
  
        # Manually set corner points
        # Top Left
        L6 = float(griddata(coord_xy, coord_z, (-50.0, 25.0)))
        O3 = float(griddata(coord_xy, coord_z, (-25.0, 50.0)))
        x_list_new.append(-50.0+dx)
        y_list_new.append(25.0+dy)
        dz_list_new.append((O3-L6)/3.0+L6)
        x_list_new.append(-50.0+2.0*dx)
        y_list_new.append(25.0+2.0*dy)
        dz_list_new.append((L6-O3)/3+O3)
        # Top Right
        X6 = float(griddata(coord_xy, coord_z, (50.0, 25.0)))
        U3 = float(griddata(coord_xy, coord_z, (25.0, 50.0)))
        x_list_new.append(50.0-dx)
        y_list_new.append(25.0+dy)
        dz_list_new.append((U3-X6)/3+X6)
        x_list_new.append(50.0-2.0*dx)
        y_list_new.append(25.0+2.0*dy)
        dz_list_new.append((X6-U3)/3+U3)
        # Bottom Right
        X12 = float(griddata(coord_xy, coord_z, (50.0, -25.0)))
        U15 = float(griddata(coord_xy, coord_z, (25.0, -50.0)))
        x_list_new.append(50.0-dx)
        y_list_new.append(-25.0-dy)
        dz_list_new.append((U15-X12)/3+X12)
        x_list_new.append(50.0-2.0*dx)
        y_list_new.append(-25.0-2.0*dy)
        dz_list_new.append((X12-U15)/3+U15)
        # Bottom Left
        L12 = float(griddata(coord_xy, coord_z, (-50.0, -25.0)))
        O15 = float(griddata(coord_xy, coord_z, (-25.0, -50.0)))
        x_list_new.append(-50.0+dx)
        y_list_new.append(-25.0-dy)
        dz_list_new.append((O15-L12)/3+L12)
        x_list_new.append(-50.0+2.0*dx)
        y_list_new.append(-25.0-2.0*dy)
        dz_list_new.append((L12-O15)/3+O15)
        
        # Reset gridddata arrays now that we're using calculated values
        coord_xy, coord_z = xyz_list2array(x_list_new,y_list_new,dz_list_new)
        
        # Fill in remaining points used in actual calculations
        
        # Tower X
        M9 = float(griddata(coord_xy, coord_z, (-50.0+dx, 0.0)))
        M12 = float(griddata(coord_xy, coord_z, (-50.0+dx, -25.0)))
        x_list_new.append(-50.0+dx)
        y_list_new.append(-25.0+dy)
        dz_list_new.append((M9-M12)/3.0+M12)
        #print("M9={0} M12={1} x={2} y={3} z={4}".format(str(M9),str(M12),str(-50.0+dx),str(-25.0+dy),str((M9-M12)/3.0+M12)))
        
        # Tower Y
        W9 = float(griddata(coord_xy, coord_z, (50.0-dx, 0.0)))
        W12 = float(griddata(coord_xy, coord_z, (50.0-dx, -25.0)))
        x_list_new.append(50.0-dx)
        y_list_new.append(-25.0+dy)
        dz_list_new.append((W9-W12)/3.0+W12)
        #print("W9={0} W12={1} x={2} y={3} z={4}".format(str(W9),str(W12),str(50.0-dx),str(-25.0+dy),str((W9-W12)/3.0+W12)))
        
        # Tower Z
        Q3 = float(griddata(coord_xy, coord_z, (0.0-dx, 50.0)))
        Q6 = float(griddata(coord_xy, coord_z, (0.0-dx, 25.0)))
        x_list_new.append(0.0-dx)
        y_list_new.append(50.0-dy)
        dz_list_new.append((Q6-Q3)/3.0+Q3)
        #print("Q3={0} Q6={1} x={2} y={3} z={4}".format(str(Q3),str(Q6),str(0.0-dx),str(50.0-dy),str((Q6-Q3)/3.0+Q3)))
        S3 = float(griddata(coord_xy, coord_z, (0.0+dx, 50.0)))
        S6 = float(griddata(coord_xy, coord_z, (0.0+dx, 25.0)))
        x_list_new.append(0.0+dx)
        y_list_new.append(50.0-dy)
        dz_list_new.append((S6-S3)/3.0+S3)
        #print("S3={0} S6={1} x={2} y={3} z={4}".format(str(Q3),str(Q6),str(0.0+dx),str(50.0-dy),str((S6-S3)/3.0+S3)))
        
        # Outside Ring
        # No additional points
        
        # Center
        Q9 = float(griddata(coord_xy, coord_z, (0.0-dx, 0.0)))
        S9 = float(griddata(coord_xy, coord_z, (0.0+dx, 0.0)))
        Q7 = (Q9-Q6)/3.0+Q6
        S7 = (S9-S6)/3.0+S6
        Q12 = float(griddata(coord_xy, coord_z, (0.0-dx, -25.0)))
        S12 = float(griddata(coord_xy, coord_z, (0.0+dx, -25.0)))
        x_list_new.append(0.0-dx)
        y_list_new.append(0.0+dy)
        dz_list_new.append((Q7-Q9)/2.0+Q9)
        x_list_new.append(0.0+dx)
        y_list_new.append(0.0+dy)
        dz_list_new.append((S7-S9)/2.0+S9)
        x_list_new.append(0.0-dx)
        y_list_new.append(0.0-dy)
        dz_list_new.append((Q12-Q9)/3.0+Q9)
        x_list_new.append(0.0+dx)
        y_list_new.append(0.0-dy)
        dz_list_new.append((S12-S9)/3+S9)
        
        # Convert final values to Array
        coord_xy, coord_z = xyz_list2array(x_list_new,y_list_new,dz_list_new)

    
    # X Tilt
    x0 = xmin
    y0 = ymin/2
    TX_list = [None]*5
    TX_list[0] = float(griddata(coord_xy, coord_z, (x0   , y0)))
    TX_list[1] = float(griddata(coord_xy, coord_z, (x0   , y0+dy)))
    TX_list[2] = float(griddata(coord_xy, coord_z, (x0+dx, y0)))
    TX_list[3] = float(griddata(coord_xy, coord_z, (x0+dx, y0+dy)))
    TX_list[4] = float(griddata(coord_xy, coord_z, (x0+dx, y0-dy)))
    #print("TX Values\n")
    #print(*TX_list, sep='\n\n')
    #print("\n")
    TX = float(statistics.mean(TX_list))
    
    # Y Tilt
    x0 = xmax
    y0 = ymin/2
    TY_list = [None]*5
    TY_list[0] = float(griddata(coord_xy, coord_z, (x0   , y0)))
    TY_list[1] = float(griddata(coord_xy, coord_z, (x0   , y0+dy)))
    TY_list[2] = float(griddata(coord_xy, coord_z, (x0-dx, y0))) # problem
    TY_list[3] = float(griddata(coord_xy, coord_z, (x0-dx, y0+dy)))
    TY_list[4] = float(griddata(coord_xy, coord_z, (x0-dx, y0-dy)))
    #print("TY Values\n")
    #print(*TY_list, sep='\n\n')
    #print("\n")
    TY = float(statistics.mean(TY_list))
    
    # Z Tilt
    x0 = 0.0
    y0 = ymax
    TZ_list = [None]*6
    TZ_list[0] = float(griddata(coord_xy, coord_z, (x0-dx, y0)))
    TZ_list[1] = float(griddata(coord_xy, coord_z, (x0   , y0)))
    TZ_list[2] = float(griddata(coord_xy, coord_z, (x0+dx, y0)))
    TZ_list[3] = float(griddata(coord_xy, coord_z, (x0-dx, y0-dy)))
    TZ_list[4] = float(griddata(coord_xy, coord_z, (x0   , y0-dy)))
    TZ_list[5] = float(griddata(coord_xy, coord_z, (x0+dx, y0-dy)))
    #print("TZ Values\n")
    #print(*TZ_list, sep='\n\n')
    #print("\n")
    TZ = float(statistics.mean(TZ_list))
    
    # Bowl Stats - Center
    x0 = 0.0
    y0 = 0.0
    BC_list = [None]*9
    BC_list[0] = float(griddata(coord_xy, coord_z, (x0-dx, y0+dy)))
    BC_list[1] = float(griddata(coord_xy, coord_z, (x0   , y0+dy)))
    BC_list[2] = float(griddata(coord_xy, coord_z, (x0+dx, y0+dy)))
    BC_list[3] = float(griddata(coord_xy, coord_z, (x0-dx, y0)))
    BC_list[4] = float(griddata(coord_xy, coord_z, (x0   , y0)))
    BC_list[5] = float(griddata(coord_xy, coord_z, (x0+dx, y0)))
    BC_list[6] = float(griddata(coord_xy, coord_z, (x0-dx, y0-dy)))
    BC_list[7] = float(griddata(coord_xy, coord_z, (x0   , y0-dy)))
    BC_list[8] = float(griddata(coord_xy, coord_z, (x0+dx, y0-dy)))
    #print("Bowl Center: \n")
    #print(*BC_list, sep='\n\n')
    #print("\n")
    BowlCenter = float(statistics.mean(BC_list))
    
    # Bowl Stats - Outside Ring
    OR_list = [None]*12
    # Left
    OR_list[0]  = float(griddata(coord_xy, coord_z, (xmin, ymin/2.0)))
    OR_list[1]  = float(griddata(coord_xy, coord_z, (xmin,   0.0)))
    OR_list[2]  = float(griddata(coord_xy, coord_z, (xmin,  ymax/2.0)))
    # Right
    OR_list[3]  = float(griddata(coord_xy, coord_z, (xmax, ymin/2.0)))
    OR_list[4]  = float(griddata(coord_xy, coord_z, (xmax,   0.0)))
    OR_list[5]  = float(griddata(coord_xy, coord_z, (xmax,  ymax/2.0)))
    # Top
    OR_list[6]  = float(griddata(coord_xy, coord_z, (xmin/2.0,  ymax)))
    OR_list[7]  = float(griddata(coord_xy, coord_z, (   0.0,  ymax)))
    OR_list[8]  = float(griddata(coord_xy, coord_z, (xmax/2.0,  ymax)))
    # Bottom
    OR_list[9]  = float(griddata(coord_xy, coord_z, (xmin/2.0, ymin)))
    OR_list[10] = float(griddata(coord_xy, coord_z, (   0.0, ymin)))
    OR_list[11] = float(griddata(coord_xy, coord_z, (xmax/2.0, ymin)))
    BowlOR = float(statistics.median(OR_list))
    #print("Outer Ring Values: \n")
    #print(*OR_list, sep='\n\n')
    #print("\n")
    #print("BowlOR = {0:.4f}".format(BowlOR))
    
    # Define Pass # according to the spreadsheet
    pass_num = runs - 1
    
    if pass_num == 0:
        # Define Tower Points
        xtower = float(griddata(coord_xy, coord_z, (xmin, ymin/2.0)))
        ytower = float(griddata(coord_xy, coord_z, (xmax, ymin/2.0)))
        ztower = float(griddata(coord_xy, coord_z, ( 0.0, ymax)))
    
        # Check X Tower
        if xtower > ytower and xtower > ztower:
            xhigh[1] = 1
            
        # Check Y Tower
        if ytower > xtower and ytower > ztower:
            yhigh[1] = 1
            
        # Check Z Tower
        if ztower > xtower and ztower > ytower:
            zhigh[1] = 1
            
        # Save Values
        xhigh[0] = xhigh[1]
        yhigh[0] = yhigh[1]
        zhigh[0] = zhigh[1]
    else: 
        xhigh[1] = 0
        yhigh[1] = 0
        zhigh[1] = 0

    # Calculate High Parameter
    iHighTower = -1
    if xhigh[0] == 1:
        THigh = TX
        iHighTower = 0
    elif yhigh[0] == 1:
        THigh = TY
        iHighTower = 1
    else:
        THigh = TZ
        iHighTower = 2

    # Return Results
    return TX, TY, TZ, THigh, BowlCenter, BowlOR, xhigh, yhigh, zhigh, iHighTower
    
    
def determine_error(TX, TY, TZ, THigh, BowlCenter, BowlOR):
    z_error = float("{0:.4f}".format(TZ - THigh))
    x_error = float("{0:.4f}".format(TX - THigh))
    y_error = float("{0:.4f}".format(TY - THigh))
    c_error = float("{0:.4f}".format(BowlCenter - BowlOR))
    print('Z-Error: ' + str(z_error) + ' X-Error: ' + str(x_error) + ' Y-Error: ' + str(y_error) + ' C-Error: ' + str(c_error) + '\n')

    return z_error, x_error, y_error, c_error
    

def calibrate(port, z_error, x_error, y_error, c_error, trial_x, trial_y, trial_z, l_value, r_value, iHighTower, max_runs, runs):
    calibrated = True
    if abs(z_error) >= 0.02:
        if iHighTower == 2:
            new_z = float("{0:.4f}".format(0.0))
        else:
            new_z = float("{0:.4f}".format(z_error + trial_z))
        calibrated = False
    else:
        new_z = trial_z

    if abs(x_error) >= 0.02:
        if iHighTower == 0:
            new_x = float("{0:.4f}".format(0.0))
        else:
            new_x = float("{0:.4f}".format(x_error + trial_x))
        calibrated = False
    else:
        new_x = trial_x

    if abs(y_error) >= 0.02:
        if iHighTower == 1:
            new_y = float("{0:.4f}".format(0.0))
        else:
            new_y = float("{0:.4f}".format(y_error + trial_y))
        calibrated = False
    else:
        new_y = trial_y

    if abs(c_error) >= 0.02:
        new_r = float("{0:.4f}".format(r_value - 4.0*c_error))
        calibrated = False
    else:
        new_r = r_value
        
    new_l = float("{0:.4f}".format(1.5*(new_r-r_value) + l_value))

    # making sure I am sending the lowest adjustment value
    #diff = 100
    #for i in [new_z, new_x ,new_y]:
    #    if abs(0-i) < diff:
    #        diff = 0-i
    #new_z += diff
    #new_x += diff
    #new_y += diff

    if calibrated:
        print ("Final values\nM666 Z{0} X{1} Y{2} \nM665 L{3} R{4}".format(str(new_z),str(new_x),str(new_y),str(new_l),str(new_r)))
    else:
        set_M_values(port, new_z, new_x, new_y, new_l, new_r)

    return calibrated, new_z, new_x, new_y, new_l, new_r

def set_M_values(port, z, x, y, l, r):

    print ("Setting values M666 X{0} Y{1} Z{2}, M665 L{3} R{4}".format(str(x),str(y),str(z),str(l),str(r)))

    port.write(('M666 X{0} Y{1} Z{2}\n'.format(str(x), str(y), str(z))).encode())
    out = port.readline().decode()
    port.write(('M665 L{0} R{1}\n'.format(str(l),str(r))).encode())
    out = port.readline().decode()
    
def output_pass_text(runs, trial_x, trial_y, trial_z, l_value, r_value, iHighTower, x_list, y_list, z1_list, z2_list): 

    # Get the pass number corresponding to Dennis's spreadsheet
    pass_num = int(runs-1)
    
    # Create the file
    file_object  = open("auto_cal_p5_pass{0}.txt".format(str(pass_num)), "w")
    
    # Output current pass values
    file_object.write("M666 X{0:.2f} Y{1:.2f} Z{2:.2f}\r\n".format(float(trial_x), float(trial_y), float(trial_z))) 
    file_object.write("M665 L{0:.4f} R{1:.4f}\r\n".format(float(l_value), float(r_value))) 
    file_object.write("\r\n") 
    
    # Highest Tower Value
    if int(iHighTower) == 0:
        file_object.write("Highest Tower: X\r\n") 
    elif int(iHighTower) == 1:
        file_object.write("Highest Tower: Y\r\n") 
    else: 
        file_object.write("Highest Tower: Z\r\n") 
    
    # Output Grid Points
    file_object.write("\r\n") 
    file_object.write("\r\n") 
    file_object.write("< 01:02:03 PM: G29 Auto Bed Leveling\r\n") 
    for ii in range(len(x_list)):
        file_object.write("< 01:02:03 PM: Bed X: {0:.3f} Y: {1:.3f} Z: {2:.3f}\r\n".format(float(x_list[ii]), float(y_list[ii]), float(z1_list[ii]))) 
        file_object.write("< 01:02:03 PM: Bed X: {0:.3f} Y: {1:.3f} Z: {2:.3f}\r\n".format(float(x_list[ii]), float(y_list[ii]), float(z2_list[ii]))) 
    
    # Close file stream
    file_object.close() 
    
    return


def run_calibration(port, firmFlag, trial_x, trial_y, trial_z, l_value, r_value, xhigh, yhigh, zhigh, max_runs, max_error, bed_temp, minterp, runs=0):
    runs += 1

    if runs > max_runs:
        sys.exit("Too many calibration attempts")
    print('\nCalibration pass {1}, run {2} out of {0}'.format(str(max_runs), str(runs-1), str(runs)))
    
    # Make sure the bed doesn't go cold
    if bed_temp >= 0: 
        port.write('M140 S{0}\n'.format(str(bed_temp)).encode())
    
    # Read G30 values and calculate values in columns B through H
    x_list, y_list, z1_list, z2_list, z_avg_list, dtap_list, dz_list = get_current_values(port, firmFlag)
    
    # Generate the P5 contour map
    TX, TY, TZ, THigh, BowlCenter, BowlOR, xhigh, yhigh, zhigh, iHighTower = calculate_contour(x_list, y_list, dz_list, runs, xhigh, yhigh, zhigh, minterp)
    
    # Output current pass results
    output_pass_text(runs, trial_x, trial_y, trial_z, l_value, r_value, iHighTower, x_list, y_list, z1_list, z2_list)
    
    # Output Debugging Info
    #file_object  = open("debug_pass{0:d}.csv".format(int(runs-1)), "w")
    #file_object.write("X,Y,Z1,Z2,Z avg,Tap diff,Z diff,TX,TY,TZ,THigh,BowlCenter,BowlOR\r\n") 
    #z_med = statistics.median(z_avg_list)
    #for ii in range(len(x_list)):
    #    dz_list[ii] = z_avg_list[ii] - z_med
    #    file_object.write("{0:.4f},{1:.4f},{2:.4f},{3:.4f},".format(float(x_list[ii]),float(y_list[ii]),float(z1_list[ii]),float(z2_list[ii])))
    #    file_object.write("{0:.4f},{1:.4f},{2:.4f},".format(float(z_avg_list[ii]),float(dtap_list[ii]),float(dz_list[ii])))
    #    file_object.write("{0:.4f},{1:.4f},{2:.4f},{3:.4f},{4:.4f},{5:.4f}\r\n".format(float(TX),float(TY),float(TZ),float(THigh),float(BowlCenter),float(BowlOR)))
    #file_object.close() 
    
    # Calculate Error
    z_error, x_error, y_error, c_error = determine_error(TX, TY, TZ, THigh, BowlCenter, BowlOR)
    
    if abs(max([z_error, x_error, y_error, c_error], key=abs)) > max_error and runs > 1:
        sys.exit("Calibration error on non-first run exceeds set limit")

    calibrated, new_z, new_x, new_y, new_l, new_r = calibrate(port, z_error, x_error, y_error, c_error, trial_x, trial_y, trial_z, l_value, r_value, iHighTower, max_runs, runs)
    
    if calibrated:
        print ("Calibration complete")
    else:
        calibrated, new_z, new_x, new_y, new_l, new_r, xhigh, yhigh, zhigh = run_calibration(port, firmFlag, new_x, new_y, new_z, new_l, new_r, xhigh, yhigh, zhigh, max_runs, max_error, bed_temp, minterp, runs)

    return calibrated, new_z, new_x, new_y, new_l, new_r, xhigh, yhigh, zhigh

def main():
    # Default values
    max_runs = 14
    max_error = 1

    x0 = 0.0
    y0 = 0.0
    z0 = 0.0
    trial_z = x0
    trial_x = y0
    trial_y = z0
    r_value = 63.5
    step_mm = 57.14
    l_value = 123.0
    xhigh = [0]*2
    yhigh = [0]*2
    zhigh = [0]*2
    bed_temp = -1
    minterp = 0
    firmFlag = 0

    parser = argparse.ArgumentParser(description='Auto-Bed Cal. for Monoprice Mini Delta')
    parser.add_argument('-p','--port',help='Serial port',required=True)
    parser.add_argument('-r','--r-value',type=float,default=r_value,help='Starting r-value')
    parser.add_argument('-l','--l-value',type=float,default=l_value,help='Starting l-value')
    parser.add_argument('-s','--step-mm',type=float,default=step_mm,help='Set steps-/mm')
    parser.add_argument('-me','--max-error',type=float,default=max_error,help='Maximum acceptable calibration error on non-first run')
    parser.add_argument('-mr','--max-runs',type=int,default=max_runs,help='Maximum attempts to calibrate printer')
    parser.add_argument('-bt','--bed-temp',type=int,default=bed_temp,help='Bed Temperature')
    parser.add_argument('-im','--minterp',type=int,default=minterp,help='Intepolation Method')
    parser.add_argument('-ff','--firmFlag',type=int,default=firmFlag,help='Firmware Flag (0 = Stock; 1 = Marlin)')
    parser.add_argument('-f','--file',type=str,dest='file',default=None,
        help='File with settings, will be updated with latest settings at the end of the run')
    args = parser.parse_args()

    port = establish_serial_connection(args.port)        

    if args.file:
        try:
            with open(args.file) as data_file:
                settings = json.load(data_file)
            firmFlag = int(settings.get('firmFlag', firmFlag))
            minterp = int(settings.get('minterp', minterp))
            bed_temp = int(settings.get('bed_temp', bed_temp))
            max_runs = int(settings.get('max_runs', max_runs))
            max_error = float(settings.get('max_error', max_error))
            trial_z = float(settings.get('z', trial_z))
            trial_x = float(settings.get('x', trial_x))
            trial_y = float(settings.get('y', trial_y))
            r_value = float(settings.get('r', r_value))
            l_value = float(settings.get('l', l_value))
            step_mm = float(settings.get('step', step_mm))

        except:
            firmFlag = args.firmFlag
            minterp = args.minterp
            bed_temp = args.bed_temp
            max_error = args.max_error
            max_runs = args.max_runs
            r_value = args.r_value
            step_mm = args.step_mm
            max_runs = args.max_runs
            l_value = args.l_value
            pass
    else: 
        firmFlag = args.firmFlag
        minterp = args.minterp
        bed_temp = args.bed_temp
        max_error = args.max_error
        max_runs = args.max_runs
        r_value = args.r_value
        step_mm = args.step_mm
        max_runs = args.max_runs
        l_value = args.l_value
        
    if port:
    
        # Firmware
        if firmFlag == 0:
            print("Using Monoprice Firmware\n")
        elif firmFlag == 1:
            print("Using Marlin Firmware\n")
    
        #Set Bed Temperature
        if bed_temp >= 0:
            print ('Setting bed temperature to {0} C\n'.format(str(bed_temp)))
            port.write('M140 S{0}\n'.format(str(bed_temp)).encode())
            out = port.readline().decode()
            
        # Display interpolation methods
        if minterp == 1: 
            print("Interpolation Method: Dennis's Spreadsheet\n")
        else:
            print("Interpolation Method: python3 scipy.interpolate.griddata\n")
    
        # Set the proper step/mm
        print ('Setting up M92 X{0} Y{0} Z{0}\n'.format(str(step_mm)))
        port.write(('M92 X{0} Y{0} Z{0}\n'.format(str(step_mm))).encode())
        out = port.readline().decode()
        
        print ('Setting up M665 L{0} R{1}\n'.format(str(l_value),str(r_value)))
        port.write(('M665 L{0}\n'.format(str(l_value))).encode())
        out = port.readline().decode()

        if firmFlag == 1:
            print ('Setting up M206 X0 Y0 Z0\n')
            port.write('M206 X0 Y0 Z0\n'.encode())
            out = port.readline().decode()
        
            print ('Clearing mesh with M421 C\n')
            port.write('M421 C\n'.encode())
            out = port.readline().decode()

        set_M_values(port, trial_z, trial_x, trial_y, l_value, r_value)

        print ('\nStarting calibration')

        calibrated, new_z, new_x, new_y, new_l, new_r, xhigh, yhigh, zhigh = run_calibration(port, firmFlag, trial_x, trial_y, trial_z, l_value, r_value, xhigh, yhigh, zhigh, max_runs, args.max_error, bed_temp, minterp)

        port.close()

        if calibrated:
            if firmFlag == 1:
                print ('Run mesh bed leveling before printing: G29\n')
            if args.file:
                data = {'z':new_z, 'x':new_x, 'y':new_y, 'r':new_r, 'l': new_l, 'step':step_mm, 'max_runs':max_runs, 'max_error':max_error, 'bed_temp':bed_temp}
                with open(args.file, "w") as text_file:
                    text_file.write(json.dumps(data))


if __name__ == '__main__':
    main()
