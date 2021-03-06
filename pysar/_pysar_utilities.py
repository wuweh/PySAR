#! /usr/bin/env python
############################################################
# Program is part of PySAR v1.0                            #
# Copyright(c) 2013, Heresh Fattahi                        #
# Author:  Heresh Fattahi                                  #
############################################################

# timeseries_inversion and Remove_plaane are modified 
# from a software originally written by Scott Baker with 
# the following licence:

###############################################################################
#  Copyright (c) 2011, Scott Baker 
# 
#  Permission is hereby granted, free of charge, to any person obtaining a
#  copy of this software and associated documentation files (the "Software"),
#  to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense,
#  and/or sell copies of the Software, and to permit persons to whom the
#  Software is furnished to do so, subject to the following conditions:
# 
#  The above copyright notice and this permission notice shall be included
#  in all copies or substantial portions of the Software.
# 
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
#  OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
#  THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#  DEALINGS IN THE SOFTWARE.
############################################################################### 
#
# Yunjun, Oct 2015: Add radar_or_geo() (modifed from pysarApp.py written by Heresh)
#                   Add glob2radar() and radar2glob() (modified from radar2geo.py written by Heresh)



import sys
import os
import re
import time
import datetime
import glob

import numpy as np
import h5py

import pysar._readfile as readfile
import pdb



#########################################################################
############### Convertion from Geo to Radar coordinate #################
def glob2radar(lat,lon,rdrRefFile='radar*.hgt',igramNum=1):
  ## Convert geo coordinates into radar coordinates.
  ##     If geomap*.trans file exists, use it for precise conversion;
  ##     If not, use radar*.hgt or input reference file's 4 corners' lat/lon
  ##          info for a simple 2D linear transformation.
  ##
  ## Usage: x,y,x_res,y_res = glob2radar(lat,lon [,rdrRefFile] [,igramNum])
  ##
  ##     lat (np.array) : Array of latitude
  ##     lon (np.array) : Array of longitude
  ##     rdrRefFile     : radar coded file (not subseted), optional.
  ##                      radar*.hgt by default, support all PySAR / ROI_PAC format
  ##     igramNum       : used interferogram number, i.e. 1 or 56, optional
  ##
  ##     x/y            : Array of radar coordinate - range/azimuth
  ##     x_res/y_res    : residul/uncertainty of coordinate conversion
  ##
  ## Exmaple: x,y,x_res,y_res = glob2radar(np.array([31.1,31.2,...]), np.array([130.1,130.2,...]))
  ##          x,y,x_res,y_res = glob2radar(np.array([31.1,31.2,...]), np.array([130.1,130.2,...]),'Mask.h5')
  ##          x,y,x_res,y_res = glob2radar(np.array([31.1,31.2,...]), np.array([130.1,130.2,...]),'LoadedData.h5',1)

  ########## Precise conversion using geomap.trans file, if it exists.
  try:
    geomapFile = glob.glob('geomap*.trans')[0]
    atr = readfile.read_rsc_file(geomapFile+'.rsc')
    print 'finding precise radar coordinate from '+geomapFile+' file.'

    width  = int(atr['WIDTH'])
    row = (lat - float(atr['Y_FIRST'])) / float(atr['Y_STEP']);  row = (row+0.5).astype(int)
    col = (lon - float(atr['X_FIRST'])) / float(atr['X_STEP']);  col = (col+0.5).astype(int)
    row_read = np.max(row)+1
    data = np.fromfile(geomapFile,np.float32,row_read*2*width).reshape(row_read,2*width)
    x = data[row, col];       x = (x+0.5).astype(int)
    y = data[row, col+width]; y = (y+0.5).astype(int)
    x_res = 2
    y_res = 2

  ########## Simple conversion using 2D linear transformation, with 4 corners' lalo info
  except:
    rdrRefFile = check_variable_name(rdrRefFile)
    rdrRefFile = glob.glob(rdrRefFile)[0]
    print 'finding approximate radar coordinate with 2D linear transformation estimation.'
    print '    using four corner lat/lon info from '+rdrRefFile+' file.'

    ext = os.path.splitext(rdrRefFile)[1]
    if ext == '.h5':
       h5file=h5py.File(rdrRefFile,'r')
       k=h5file.keys()
       if   k[0] in ('interferograms','coherence','wrapped'):
          atr = h5file[k[0]][h5file[k[0]].keys()[igramNum-1]].attrs
       elif k[0] in ('dem','velocity','mask','temporal_coherence','rmse','timeseries'):
          atr = h5file[k[0]].attrs
    elif ext in ['.unw','.cor','.int','.hgt','.dem']:
       atr = readfile.read_rsc_file(rdrRefFile + '.rsc')
    else: print 'Unrecognized reference file extention: '+ext; return

    LAT_REF1=float(atr['LAT_REF1'])
    LAT_REF2=float(atr['LAT_REF2'])
    LAT_REF3=float(atr['LAT_REF3'])
    LAT_REF4=float(atr['LAT_REF4'])
    LON_REF1=float(atr['LON_REF1'])
    LON_REF2=float(atr['LON_REF2'])
    LON_REF3=float(atr['LON_REF3'])
    LON_REF4=float(atr['LON_REF4'])
    W =      float(atr['WIDTH'])
    L =      float(atr['FILE_LENGTH'])
    if ext == '.h5':  h5file.close()

    ## subset radar image has different WIDTH and FILE_LENGTH info
    try:
       atr['subset_x0']
       print 'WARNING: Cannot use subset file as input! No coordinate converted.'
       return
    except: pass

    LAT_REF = np.array([LAT_REF1,LAT_REF2,LAT_REF3,LAT_REF4]).reshape(4,1)
    LON_REF = np.array([LON_REF1,LON_REF2,LON_REF3,LON_REF4]).reshape(4,1)
    X = np.array([1,W,1,W]).reshape(4,1)
    Y = np.array([1,1,L,L]).reshape(4,1)

    ### estimate 2D tranformation from Lease Square
    A = np.hstack([LAT_REF,LON_REF,np.ones((4,1))])
    B = np.hstack([X,Y])
    affine_par = np.linalg.lstsq(A,B)[0]
    res = B - np.dot(A,affine_par)
    res_mean = np.mean(np.abs(res),0)
    x_res = (res_mean[0]+0.5).astype(int)
    y_res = (res_mean[1]+0.5).astype(int)
    print 'Residul - x: '+str(x_res)+', y: '+str(y_res)

    ### calculate radar coordinate of inputs
    N = len(lat)
    A = np.hstack([lat.reshape(N,1), lon.reshape(N,1), np.ones((N,1))])
    x = np.dot(A, affine_par[:,0]);   x = (x+0.5).astype(int)
    y = np.dot(A, affine_par[:,1]);   y = (y+0.5).astype(int)


  return x, y, x_res, y_res



#########################################################################
############### Convertion from Radar to Geo coordinate #################
def radar2glob(x,y,rdrRefFile='radar*.hgt',igramNum=1):
  ## Convert radar coordinates into geo coordinates.
  ##     This function use radar*.hgt or input reference file's 4 corners'
  ##     lat/lon info for a simple 2D linear transformation.
  ##
  ## Usage: lat,lon,lat_res,lon_res = glob2radar(x, y [,rdrRefFile] [,igramNum])
  ##
  ##     x (np.array)     : Array of x/range pixel number
  ##     y (np.array)     : Array of y/azimuth pixel number
  ##     rdrRefFile       : radar coded file (not subseted), optional.
  ##                        radar*.hgt by default, support all PySAR / ROI_PAC format
  ##     igramNum         : used interferogram number, i.e. 1 or 56, optional
  ##
  ##     lat/lon          : Array of geo coordinate
  ##     lat_res/lon_res  : residul/uncertainty of coordinate conversion
  ##
  ## Exmaple: lat,lon,lat_res,lon_res = glob2radar(np.array([202,808,...]), np.array([404,303,...]))
  ##          lat,lon,lat_res,lon_res = glob2radar(np.array([202,808,...]), np.array([404,303,...]),'Mask.h5')
  ##          lat,lon,lat_res,lon_res = glob2radar(np.array([202,808,...]), np.array([404,303,...]),'LoadedData.h5',1)

  ### find and read radar coded reference file
  rdrRefFile = check_variable_name(rdrRefFile)  
  rdrRefFile = glob.glob(rdrRefFile)[0]
  ext = os.path.splitext(rdrRefFile)[1]
  if ext == '.h5':
     h5file=h5py.File(rdrRefFile,'r')
     k=h5file.keys()
     if   k[0] in ('interferograms','coherence','wrapped'):
        atr = h5file[k[0]][h5file[k[0]].keys()[igramNum-1]].attrs
     elif k[0] in ('dem','velocity','mask','temporal_coherence','rmse','timeseries'):
        atr = h5file[k[0]].attrs
  elif ext in ['.unw','.cor','.int','.hgt','.dem']:
     atr = readfile.read_rsc_file(rdrRefFile + '.rsc')
  else: print 'Unrecognized file extention: '+ext; return

  LAT_REF1=float(atr['LAT_REF1'])
  LAT_REF2=float(atr['LAT_REF2'])
  LAT_REF3=float(atr['LAT_REF3'])
  LAT_REF4=float(atr['LAT_REF4'])
  LON_REF1=float(atr['LON_REF1'])
  LON_REF2=float(atr['LON_REF2'])
  LON_REF3=float(atr['LON_REF3'])
  LON_REF4=float(atr['LON_REF4'])
  W =      float(atr['WIDTH'])
  L =      float(atr['FILE_LENGTH'])
  if ext == '.h5':  h5file.close()

  try:
     atr['subset_x0']
     print 'WARNING: Cannot use subset file as input! No coordinate converted.'
     return
  except: pass

  LAT_REF = np.array([LAT_REF1,LAT_REF2,LAT_REF3,LAT_REF4]).reshape(4,1)
  LON_REF = np.array([LON_REF1,LON_REF2,LON_REF3,LON_REF4]).reshape(4,1)
  X = np.array([1,W,1,W]).reshape(4,1)
  Y = np.array([1,1,L,L]).reshape(4,1)

  ### estimate 2D tranformation from Lease Square
  A = np.hstack([X,Y,np.ones((4,1))])
  B = np.hstack([LAT_REF,LON_REF])
  affine_par = np.linalg.lstsq(A,B)[0]
  res = B - np.dot(A,affine_par)
  res_mean = np.mean(np.abs(res),0)
  lat_res = res_mean[0]
  lon_res = res_mean[1]
  print 'Residul - lat: '+str(lat_res)+', lon: '+str(lon_res)

  ### calculate geo coordinate of inputs
  N = len(x)
  A = np.hstack([x.reshape(N,1), y.reshape(N,1), np.ones((N,1))])
  lat = np.dot(A, affine_par[:,0])
  lon = np.dot(A, affine_par[:,1])

  return lat, lon, lat_res, lon_res



#########################################################################
############### Check File is in Radar or Geo coordinate ################
def radar_or_geo(File):
  ext = os.path.splitext(File)[1]
  if ext == '.h5':
     h5file=h5py.File(File,'r')
     k=h5file.keys()
     if   k[0] in ('interferograms','coherence','wrapped'):
        atrKey = h5file[k[0]][h5file[k[0]].keys()[0]].attrs.keys()
     elif k[0] in ('dem','velocity','mask','temporal_coherence','rmse','timeseries'):
        atrKey = h5file[k[0]].attrs.keys()
     h5file.close()
  elif ext in ['.unw','.cor','.int','.hgt','.dem','.trans']:
     atrKey = readfile.read_rsc_file(File + '.rsc').keys()
  else: print 'Unrecognized extention: '+ext; return

  if 'X_FIRST' in atrKey:  rdr_geo='geo'
  else:                    rdr_geo='radar'
  return rdr_geo



#########################################################################
def check_variable_name(path):
  s=path.split("/")[0]
  
  if len(s)>0 and s[0]=="$":
     p0=os.getenv(s[1:])
     path=path.replace(path.split("/")[0],p0)
  return path



#########################################################################
def hillshade(data,scale):
  #from scott baker, ptisk library 
  azdeg=315.0
  altdeg=45.0
  az = azdeg*np.pi/180.0
  alt = altdeg*np.pi/180.0
  dx, dy = np.gradient(data/scale)
  slope = 0.5*np.pi - np.arctan(np.hypot(dx, dy))
  aspect = np.arctan2(dx, dy)
  data = np.sin(alt)*np.sin(slope) + np.cos(alt)*np.cos(slope)*np.cos(-az - aspect - 0.5*np.pi)
  return data

def remove_plane_igrams(h5file,h5flat):
  start = time.time()
  ifgramList = h5file['interferograms'].keys()
  gg = h5flat.create_group('interferograms')

  for ifgram in ifgramList:
    if not ifgram in h5flat['interferograms'].keys():
        group = gg.create_group(ifgram)
        for key,value in h5file['interferograms'][ifgram].attrs.iteritems():
           group.attrs[key] = value
        print "Removing plane from " + ifgram
        dset1 = h5file['interferograms'][ifgram].get(ifgram)
        data = dset1[0:dset1.shape[0],0:dset1.shape[1]]
        z = data.flatten(1)
        ndx = z != 0.
        x = range(0,np.shape(data)[1])
        y = range(0,np.shape(data)[0])
        x1,y1 = np.meshgrid(x,y)
        points = np.vstack((y1.flatten(1),x1.flatten(1))).T
        G = np.array([points[:,0]**2,points[:,1]**2,points[:,0],points[:,1],points[:,0]*points[:,1],np.ones(np.shape(points)[0])],np.float32).T
        z = z[ndx]
        G = G[ndx]
        print np.shape(G)
        print np.shape(z)
        plane = np.linalg.lstsq(G,z)
        originalG = G.copy()
        originalZ = z.copy()
        for ni in range(3):
          tmp_plane = np.dot(originalG,plane[0])
          G = originalG[abs(originalZ-tmp_plane) < np.std(originalZ-tmp_plane)*3]
          z = originalZ[abs(originalZ-tmp_plane) < np.std(originalZ-tmp_plane)*3]
          plane = np.linalg.lstsq(G,z)
        zplane=plane[0][0]*y1**2 + plane[0][1]*x1**2 + plane[0][2]*y1 + plane[0][3]*x1 + plane[0][4]*y1*x1 + plane[0][5]
        data_n = data - zplane
        data_n[data == 0.] = 0.
        data_n = np.array(data_n,np.float32)
        dset = group.create_dataset(ifgram, data=data_n, compression='gzip')
    else:
      print ifgram + " is already in " + h5flat
  print 'Remove Plane took ' + str(time.time()-start) +' secs'
##################################################################

def remove_surface_igrams(surf_type,h5file,h5flat,Mask):
  start = time.time()
  ifgramList = h5file['interferograms'].keys()
  gg = h5flat.create_group('interferograms')
  Mask=Mask.flatten(1)  
  for ifgram in ifgramList:
    if not ifgram in h5flat['interferograms'].keys():
        group = gg.create_group(ifgram)
        for key,value in h5file['interferograms'][ifgram].attrs.iteritems():
           group.attrs[key] = value
        print "Removing plane from " + ifgram
        dset1 = h5file['interferograms'][ifgram].get(ifgram)
        data = dset1[0:dset1.shape[0],0:dset1.shape[1]]
        z = data.flatten(1)
        ndx = Mask !=0
      #  ndx = z != 0.
        x = range(0,np.shape(data)[1])
        y = range(0,np.shape(data)[0])
        x1,y1 = np.meshgrid(x,y)
        points = np.vstack((y1.flatten(1),x1.flatten(1))).T
#        G = np.array([points[:,0]**2,points[:,1]**2,points[:,0],points[:,1],points[:,0]*points[:,1],np.ones(np.shape(points)[0])],np.float32).T
        if surf_type=='quadratic':
           G = np.array([points[:,0]**2,points[:,1]**2,points[:,0],points[:,1],points[:,0]*points[:,1],np.ones(np.shape(points)[0])],np.float32).T
        elif surf_type=='plane':
           G = np.array([points[:,0],points[:,1],np.ones(np.shape(points)[0])],np.float32).T
        elif surf_type == 'quadratic_range':
           G = np.array([points[:,1]**2,points[:,1],np.ones(np.shape(points)[0])],np.float32).T
        elif surf_type == 'quadratic_azimuth':
           G = np.array([points[:,0]**2,points[:,0],np.ones(np.shape(points)[0])],np.float32).T
        elif surf_type=='plane_range':
           G = np.array([points[:,1],np.ones(np.shape(points)[0])],np.float32).T
        elif surf_type=='plane_azimuth':
           G = np.array([points[:,0],np.ones(np.shape(points)[0])],np.float32).T

        z = z[ndx]
        G = G[ndx]
       # print np.shape(G)
       # print np.shape(z)
        plane = np.linalg.lstsq(G,z)
        originalG = G.copy()
        originalZ = z.copy()
      #  for ni in range(3):
      #    tmp_plane = np.dot(originalG,plane[0])
      #    G = originalG[abs(originalZ-tmp_plane) < np.std(originalZ-tmp_plane)*3]
      #    z = originalZ[abs(originalZ-tmp_plane) < np.std(originalZ-tmp_plane)*3]
      #    plane = np.linalg.lstsq(G,z)
#        zplane=plane[0][0]*y1**2 + plane[0][1]*x1**2 + plane[0][2]*y1 + plane[0][3]*x1 + plane[0][4]*y1*x1 + plane[0][5]
        if surf_type=='quadratic':
           zplane=plane[0][0]*y1**2 + plane[0][1]*x1**2 + plane[0][2]*y1 + plane[0][3]*x1 + plane[0][4]*y1*x1 + plane[0][5]
        elif surf_type=='plane':
           zplane= plane[0][0]*y1 + plane[0][1]*x1 + plane[0][2]
        elif surf_type == 'quadratic_range':
           zplane= plane[0][0]*x1**2  + plane[0][1]*x1 + plane[0][2]
        elif surf_type == 'quadratic_azimuth':
           zplane= plane[0][0]*y1**2  + plane[0][1]*y1 + plane[0][2]
        elif surf_type == 'plane_range':
           zplane=  plane[0][0]*x1 + plane[0][1]
        elif surf_type == 'plane_azimuth':
           zplane= plane[0][0]*y1 + plane[0][1]

        data_n = data - zplane
        data_n[data == 0.] = 0.
        data_n = np.array(data_n,np.float32)
        dset = group.create_dataset(ifgram, data=data_n, compression='gzip')
    else:
      print ifgram + " is already in " + h5flat
  print 'Remove Plane took ' + str(time.time()-start) +' secs'

##################################################################
def remove_surface_timeseries(surf_type,h5file,h5flat,Mask):
  Mask=Mask.flatten(1)
  start = time.time()
  ifgramList = h5file['timeseries'].keys()
  group = h5flat.create_group('timeseries')
  for key,value in h5file['timeseries'].attrs.iteritems():
         group.attrs[key] = value

  ifgram = ifgramList[0]
  dset1 = h5file['timeseries'].get(ifgram)
  data = dset1[0:dset1.shape[0],0:dset1.shape[1]]
  dset = group.create_dataset(ifgram, data=data, compression='gzip')

  for ifgram in ifgramList[1:]:
    if not ifgram in h5flat['timeseries'].keys():
        print "Removing plane from " + ifgram
        dset1 = h5file['timeseries'].get(ifgram)
        data = dset1[0:dset1.shape[0],0:dset1.shape[1]]
        z = data.flatten(1)
        ndx= Mask !=0
        x = range(0,np.shape(data)[1])
        y = range(0,np.shape(data)[0])
        x1,y1 = np.meshgrid(x,y)
        points = np.vstack((y1.flatten(1),x1.flatten(1))).T
        if surf_type=='quadratic':
           G = np.array([points[:,0]**2,points[:,1]**2,points[:,0],points[:,1],points[:,0]*points[:,1],np.ones(np.shape(points)[0])],np.float32).T
        elif surf_type=='plane':
           G = np.array([points[:,0],points[:,1],np.ones(np.shape(points)[0])],np.float32).T
        elif surf_type == 'quadratic_range':
           G = np.array([points[:,1]**2,points[:,1],np.ones(np.shape(points)[0])],np.float32).T        
        elif surf_type == 'quadratic_azimuth':
           G = np.array([points[:,0]**2,points[:,0],np.ones(np.shape(points)[0])],np.float32).T 
        elif surf_type=='plane_range':
           G = np.array([points[:,1],np.ones(np.shape(points)[0])],np.float32).T
        elif surf_type=='plane_azimuth':
           G = np.array([points[:,0],np.ones(np.shape(points)[0])],np.float32).T
        
        z = z[ndx]
        G = G[ndx]

        plane = np.linalg.lstsq(G,z)
      #  originalG = G.copy()
      #  originalZ = z.copy()
      #  for ni in range(3):
      #    tmp_plane = np.dot(originalG,plane[0])
      #    G = originalG[abs(originalZ-tmp_plane) < np.std(originalZ-tmp_plane)*3]
      #    z = originalZ[abs(originalZ-tmp_plane) < np.std(originalZ-tmp_plane)*3]
      #    plane = np.linalg.lstsq(G,z)
        if surf_type=='quadratic':
           zplane=plane[0][0]*y1**2 + plane[0][1]*x1**2 + plane[0][2]*y1 + plane[0][3]*x1 + plane[0][4]*y1*x1 + plane[0][5]
        elif surf_type=='plane':
           zplane= plane[0][0]*y1 + plane[0][1]*x1 + plane[0][2]
        elif surf_type == 'quadratic_range':
           zplane= plane[0][0]*x1**2  + plane[0][1]*x1 + plane[0][2]        
        elif surf_type == 'quadratic_azimuth':        
           zplane= plane[0][0]*y1**2  + plane[0][1]*y1 + plane[0][2]           
        elif surf_type == 'plane_range':
           zplane=  plane[0][0]*x1 + plane[0][1]
        elif surf_type == 'plane_azimuth':
           zplane= plane[0][0]*y1 + plane[0][1]        

        data_n = data - zplane
        data_n[data == 0.] = 0.
        data_n = np.array(data_n,np.float32)
      #  print np.shape(data_n)
        dset = group.create_dataset(ifgram, data=data_n, compression='gzip')

    else:
      print ifgram + "  already exists "
  print 'Remove Plane took ' + str(time.time()-start) +' secs'

##################################################################
##################################################################
def remove_surface_velocity(surf_type,h5file,h5flat,Mask):
  Mask2=Mask.flatten(1)
  start = time.time()
 # ifgramList = h5file['timeseries'].keys()
  group = h5flat.create_group('velocity')
  for key,value in h5file['velocity'].attrs.iteritems():
         group.attrs[key] = value

  
  dset1 = h5file['velocity'].get('velocity')
  data = dset1[0:dset1.shape[0],0:dset1.shape[1]]
#  dset = group.create_dataset(ifgram, data=data, compression='gzip')

 # for ifgram in ifgramList[1:]:
  #  if not ifgram in h5flat['timeseries'].keys():
  print "Removing surface"
  z = data.flatten(1)
  ndx= Mask2 !=0.
  #ndx = z != 0.
  x = range(0,np.shape(data)[1])
  y = range(0,np.shape(data)[0])
  x1,y1 = np.meshgrid(x,y)
  points = np.vstack((y1.flatten(1),x1.flatten(1))).T
  if surf_type=='quadratic':
      G = np.array([points[:,0]**2,points[:,1]**2,points[:,0],points[:,1],points[:,0]*points[:,1],np.ones(np.shape(points)[0])],np.float32).T
  elif surf_type=='plane':
      G = np.array([points[:,0],points[:,1],np.ones(np.shape(points)[0])],np.float32).T
  elif surf_type == 'quadratic_range':
      G = np.array([points[:,1]**2,points[:,1],np.ones(np.shape(points)[0])],np.float32).T
  elif surf_type == 'quadratic_azimuth':
      G = np.array([points[:,0]**2,points[:,0],np.ones(np.shape(points)[0])],np.float32).T
  elif surf_type=='plane_range':
      G = np.array([points[:,1],np.ones(np.shape(points)[0])],np.float32).T
  elif surf_type=='plane_azimuth':
      G = np.array([points[:,0],np.ones(np.shape(points)[0])],np.float32).T

  print '************************'
  print z.shape
  print z[ndx].shape
  print G.shape
  print G[ndx].shape
  print '************************'

  z = z[ndx]
  G = G[ndx]

  plane = np.linalg.lstsq(G,z)
  G1 = np.linalg.pinv(G)
  G1 = np.array(G1,np.float32)
  plane2 = np.dot(G1,z)
  print plane
  print plane2
  print plane[0]
  print plane[1]

  originalG = G.copy()
  originalZ = z.copy()
#  for ni in range(3):
#          tmp_plane = np.dot(originalG,plane[0])
#          G = originalG[abs(originalZ-tmp_plane) < np.std(originalZ-tmp_plane)*3]
#          z = originalZ[abs(originalZ-tmp_plane) < np.std(originalZ-tmp_plane)*3]
#          plane = np.linalg.lstsq(G,z)
  if surf_type=='quadratic':
           zplane=plane[0][0]*y1**2 + plane[0][1]*x1**2 + plane[0][2]*y1 + plane[0][3]*x1 + plane[0][4]*y1*x1 + plane[0][5]
  elif surf_type=='plane':
           zplane= plane[0][0]*y1 + plane[0][1]*x1 + plane[0][2]
  elif surf_type == 'quadratic_range':
           zplane= plane[0][0]*x1**2  + plane[0][1]*x1 + plane[0][2]
  elif surf_type == 'quadratic_azimuth':
           zplane= plane[0][0]*y1**2  + plane[0][1]*y1 + plane[0][2]
  elif surf_type == 'plane_range':
           zplane=  plane[0][0]*x1 + plane[0][1]
  elif surf_type == 'plane_azimuth':
           zplane= plane[0][0]*y1 + plane[0][1]
         #  zplane= plane2[0]*y1 + plane2[1]
  print '%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%'
 # print 'Plane parameters:'
 # print plane
  print ''
  if surf_type == 'plane_range':
     print 'range gradient = ' + str(1000*plane[0][0]) + ' mm/yr/pixel'
     width= float(h5file['velocity'].attrs['WIDTH'])
     MaxRamp=width*1000*plane[0][0]
     print 'Maximum ramp in range direction = ' + str(MaxRamp) + ' mm/yr'
     h5flat['velocity'].attrs['Range_Gradient'] = str(1000*plane[0][0]) + '   mm/yr/pixel'
     h5flat['velocity'].attrs['Range_Ramp'] = str(MaxRamp) + '   mm/yr'
  elif surf_type == 'plane_azimuth':
     print 'azimuth gradient = ' + str(1000*plane[0][0]) + ' mm/yr/pixel'
     length= float(h5file['velocity'].attrs['FILE_LENGTH'])
     MaxRamp=length*1000*plane[0][0]
     h5flat['velocity'].attrs['Azimuth_Gradient'] = str(1000*plane[0][0]) + '   mm/yr/pixel'
     h5flat['velocity'].attrs['Azimuth_Ramp'] = str(MaxRamp) +'   mm/yr'
     print 'Maximum ramp in azimuth direction = '+ str(MaxRamp) + ' mm/yr'
  print ''
  print '%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%'
  data_n = data - zplane
  data_n[data == 0.] = 0.
  data_n = np.array(data_n,np.float32)
  dset = group.create_dataset('velocity', data=data_n, compression='gzip')
  print 'writing velocity'
 # for key,value in h5file['velocity'].attrs.iteritems():
 #        group.attrs[key] = value

 # print 'Remove Plane took ' + str(time.time()-start) +' secs'
##################################################################
def remove_plane_timeseries(h5file,h5flat):
  start = time.time()
  ifgramList = h5file['timeseries'].keys()
  group = h5flat.create_group('timeseries')
  for key,value in h5file['timeseries'].attrs.iteritems():
         group.attrs[key] = value

  ifgram = ifgramList[0]
  dset1 = h5file['timeseries'].get(ifgram)
  data = dset1[0:dset1.shape[0],0:dset1.shape[1]]
  dset = group.create_dataset(ifgram, data=data, compression='gzip')

  for ifgram in ifgramList[1:]:
    if not ifgram in h5flat['timeseries'].keys():
        print "Removing plane from " + ifgram
        dset1 = h5file['timeseries'].get(ifgram)
        data = dset1[0:dset1.shape[0],0:dset1.shape[1]]
        z = data.flatten(1)
#        ndx = z != 0.
        x = range(0,np.shape(data)[1])
        y = range(0,np.shape(data)[0])
        x1,y1 = np.meshgrid(x,y)
        points = np.vstack((y1.flatten(1),x1.flatten(1))).T
     #   G = np.array([points[:,0]**2,points[:,1]**2,points[:,0],points[:,1],points[:,0]*points[:,1],np.ones(np.shape(points)[0])],np.float32).T
        G = np.array([points[:,0],points[:,1],np.ones(np.shape(points)[0])],np.float32).T
        plane = np.linalg.lstsq(G,z)
        originalG = G.copy()
        originalZ = z.copy()
        for ni in range(3):
          tmp_plane = np.dot(originalG,plane[0])
          G = originalG[abs(originalZ-tmp_plane) < np.std(originalZ-tmp_plane)*3]
          z = originalZ[abs(originalZ-tmp_plane) < np.std(originalZ-tmp_plane)*3]
          plane = np.linalg.lstsq(G,z)
      #  zplane=plane[0][0]*y1**2 + plane[0][1]*x1**2 + plane[0][2]*y1 + plane[0][3]*x1 + plane[0][4]*y1*x1 + plane[0][5]
        zplane= plane[0][0]*y1 + plane[0][1]*x1 + plane[0][2]
        data_n = data - zplane
        data_n[data == 0.] = 0.
        data_n = np.array(data_n,np.float32)
        print np.shape(data_n)
        dset = group.create_dataset(ifgram, data=data_n, compression='gzip')

    else:
      print ifgram + "  already exists "
  print 'Remove Plane took ' + str(time.time()-start) +' secs'

##################################################################
def remove_quadratic_timeseries(h5file,h5flat):
  start = time.time()
  ifgramList = h5file['timeseries'].keys()
  group = h5flat.create_group('timeseries')
  for key,value in h5file['timeseries'].attrs.iteritems():
         group.attrs[key] = value

  ifgram = ifgramList[0]
  dset1 = h5file['timeseries'].get(ifgram)
  data = dset1[0:dset1.shape[0],0:dset1.shape[1]]
  dset = group.create_dataset(ifgram, data=data, compression='gzip')  

  for ifgram in ifgramList[1:]:
    if not ifgram in h5flat['timeseries'].keys():
        print "Removing plane from " + ifgram
        dset1 = h5file['timeseries'].get(ifgram)
        data = dset1[0:dset1.shape[0],0:dset1.shape[1]]
        z = data.flatten(1)
#        ndx = z != 0.
        x = range(0,np.shape(data)[1])
        y = range(0,np.shape(data)[0])
        x1,y1 = np.meshgrid(x,y)
        points = np.vstack((y1.flatten(1),x1.flatten(1))).T
        G = np.array([points[:,0]**2,points[:,1]**2,points[:,0],points[:,1],points[:,0]*points[:,1],np.ones(np.shape(points)[0])],np.float32).T
        plane = np.linalg.lstsq(G,z)
        originalG = G.copy()
        originalZ = z.copy()
        for ni in range(3):
          tmp_plane = np.dot(originalG,plane[0])
          G = originalG[abs(originalZ-tmp_plane) < np.std(originalZ-tmp_plane)*3]
          z = originalZ[abs(originalZ-tmp_plane) < np.std(originalZ-tmp_plane)*3]
          plane = np.linalg.lstsq(G,z)
        zplane=plane[0][0]*y1**2 + plane[0][1]*x1**2 + plane[0][2]*y1 + plane[0][3]*x1 + plane[0][4]*y1*x1 + plane[0][5]
        data_n = data - zplane
        data_n[data == 0.] = 0.
        data_n = np.array(data_n,np.float32)
        print np.shape(data_n)
        dset = group.create_dataset(ifgram, data=data_n, compression='gzip')

    else:
      print ifgram + "  already exists "
  print 'Remove Plane took ' + str(time.time()-start) +' secs'

#################################################################
def date_list(h5file):
  dateList = []
  tbase = []
  ifgramList = h5file['interferograms'].keys()
  for ifgram in  ifgramList:
    dates = h5file['interferograms'][ifgram].attrs['DATE12'].split('-')
    dates1= h5file['interferograms'][ifgram].attrs['DATE12'].split('-')
    if dates[0][0] == '9':
      dates[0] = '19'+dates[0]
    else:
      dates[0] = '20'+dates[0]
    if dates[1][0] == '9':
      dates[1] = '19'+dates[1]
    else:
      dates[1] = '20'+dates[1]
    if not dates[0] in dateList: dateList.append(dates[0])
    if not dates[1] in dateList: dateList.append(dates[1])
    
  dateList.sort()
  dateList1=[]
  for ni in range(len(dateList)):
    dateList1.append(dateList[ni][2:])

  d1 = datetime.datetime(*time.strptime(dateList[0],"%Y%m%d")[0:5])
  for ni in range(len(dateList)):
    d2 = datetime.datetime(*time.strptime(dateList[ni],"%Y%m%d")[0:5])
    diff = d2-d1
    tbase.append(diff.days)
  dateDict = {}
  for i in range(len(dateList)): dateDict[dateList[i]] = tbase[i]
  return tbase,dateList,dateDict,dateList1

#####################################

def YYYYMMDD2years(d):
  dy = datetime.datetime(*time.strptime(d,"%Y%m%d")[0:5])
  dyy=np.float(dy.year) + np.float(dy.month-1)/12 + np.float(dy.day-1)/365
  return dyy

######################################
def design_matrix(h5file):
  '''Make the design matrix for the inversion.  '''
  tbase,dateList,dateDict,dateList1 = date_list(h5file)
  ifgramList = h5file['interferograms'].keys()
  numDates = len(dateDict)
  numIfgrams = len(ifgramList)
  A = np.zeros((numIfgrams,numDates))
  B = np.zeros(np.shape(A))
  daysList = []
  for day in tbase:
    daysList.append(day)
  tbase = np.array(tbase)
  t = np.zeros((numIfgrams,2))
  for ni in range(numIfgrams):
    date = h5file['interferograms'][ifgramList[ni]].attrs['DATE12'].split('-')
    if date[0][0] == '9':
      date[0] = '19'+date[0]
    else:
      date[0] = '20'+date[0]
    if date[1][0] == '9':
      date[1] = '19'+date[1]
    else:
      date[1] = '20'+date[1]
    ndxt1 = daysList.index(dateDict[date[0]])
    ndxt2 = daysList.index(dateDict[date[1]])
    A[ni,ndxt1] = -1
    A[ni,ndxt2] = 1
    B[ni,ndxt1:ndxt2] = tbase[ndxt1+1:ndxt2+1]-tbase[ndxt1:ndxt2]
    t[ni,:] = [dateDict[date[0]],dateDict[date[1]]]
  A = A[:,1:]
  B = B[:,:-1]
  return A,B

######################################
def timeseries_inversion(h5flat,h5timeseries):
  #modified from sbas.py written by scott baker, 2012 
  '''Implementation of the SBAS algorithm.
  
  Usage:
  timeseries_inversion(h5flat,h5timeseries)
    h5flat: hdf5 file with the interferograms 
    h5timeseries: hdf5 file with the output from the inversion
  '''
  total = time.time()
  A,B = design_matrix(h5flat)
  tbase,dateList,dateDict,dateDict2 = date_list(h5flat)
  dt = np.diff(tbase)
  B1 = np.linalg.pinv(B)
  B1 = np.array(B1,np.float32)
  ifgramList = h5flat['interferograms'].keys()
  numIfgrams = len(ifgramList)
  #dset = h5flat[ifgramList[0]].get(h5flat[ifgramList[0]].keys()[0])
  #data = dset[0:dset.shape[0],0:dset.shape[1]]
  dset=h5flat['interferograms'][ifgramList[0]].get(ifgramList[0]) 
  data = dset[0:dset.shape[0],0:dset.shape[1]] 
  numPixels = np.shape(data)[0]*np.shape(data)[1]
  print 'Reading in the interferograms'
  print 'number of interferograms: '+str(numIfgrams)
  print 'number of pixels: '+str(numPixels)
  numPixels_step = int(numPixels/10)

  data = np.zeros((numIfgrams,numPixels),np.float32)
  for ni in range(numIfgrams):
    #dset = h5flat[ifgramList[ni]].get(h5flat[ifgramList[ni]].keys()[0])
    dset=h5flat['interferograms'][ifgramList[ni]].get(ifgramList[ni])
    d = dset[0:dset.shape[0],0:dset.shape[1]]
    #print np.shape(d)
    data[ni] = d.flatten(1)
  del d
  dataPoint = np.zeros((numIfgrams,1),np.float32)
  modelDimension = np.shape(B)[1]
  tempDeformation = np.zeros((modelDimension+1,numPixels),np.float32)
  for ni in range(numPixels):
    dataPoint = data[:,ni]
    nan_ndx = dataPoint == 0.
    fin_ndx = dataPoint != 0.
    nan_fin = dataPoint.copy()
    nan_fin[nan_ndx] = 1
    if not nan_fin.sum() == len(nan_fin):
      B1tmp = np.dot(B1,np.diag(fin_ndx))
      tmpe_ratea = np.dot(B1tmp,dataPoint)
      zero = np.array([0.],np.float32)
      defo = np.concatenate((zero,np.cumsum([tmpe_ratea*dt])))
      tempDeformation[:,ni] = defo
    #if not np.remainder(ni,10000): print 'Processing point: %7d of %7d ' % (ni,numPixels)
    if not np.remainder(ni,numPixels_step):
      print 'Processing point: %8d of %8d, %3d' % (ni,numPixels,(10*ni/numPixels_step))+'%'
  del data
  timeseries = np.zeros((modelDimension+1,np.shape(dset)[0],np.shape(dset)[1]),np.float32)
  factor = -1*float(h5flat['interferograms'][ifgramList[0]].attrs['WAVELENGTH'])/(4.*np.pi)
  for ni in range(modelDimension+1):
    timeseries[ni] = tempDeformation[ni].reshape(np.shape(dset)[1],np.shape(dset)[0]).T
    timeseries[ni] = timeseries[ni]*factor
  del tempDeformation
  timeseriesDict = {}
  for key, value in h5flat['interferograms'][ifgramList[0]].attrs.iteritems():
    timeseriesDict[key] = value 

  dateIndex={}
  for ni in range(len(dateList)):   dateIndex[dateList[ni]]=ni
  if not 'timeseries' in h5timeseries:
    group = h5timeseries.create_group('timeseries')
    for key,value in timeseriesDict.iteritems():   group.attrs[key] = value

  for date in dateList:
    if not date in h5timeseries['timeseries']:
      dset = group.create_dataset(date, data=timeseries[dateIndex[date]], compression='gzip')
  print 'Time series inversion took ' + str(time.time()-total) +' secs'
    
###################################################
######################################
def timeseries_inversion_FGLS(h5flat,h5timeseries):

  #modified from sbas.py written by scott baker, 2012 
  '''Implementation of the SBAS algorithm.
  
  Usage:
  timeseries_inversion(h5flat,h5timeseries)
    h5flat: hdf5 file with the interferograms 
    h5timeseries: hdf5 file with the output from the inversion
  ##################################################'''

  total = time.time()
  A,B = design_matrix(h5flat)
  tbase,dateList,dateDict,dateDict2 = date_list(h5flat)
  dt = np.diff(tbase)
  B1 = np.linalg.pinv(B)
  B1 = np.array(B1,np.float32)
  ifgramList = h5flat['interferograms'].keys()
  numIfgrams = len(ifgramList)
  #dset = h5flat[ifgramList[0]].get(h5flat[ifgramList[0]].keys()[0])
  #data = dset[0:dset.shape[0],0:dset.shape[1]]
  dset=h5flat['interferograms'][ifgramList[0]].get(ifgramList[0])
  data = dset[0:dset.shape[0],0:dset.shape[1]] 
  numPixels = np.shape(data)[0]*np.shape(data)[1]
  print 'Reading in the interferograms'
  #print numIfgrams,numPixels
  print 'number of interferograms: '+str(numIfgrams)
  print 'number of pixels: '+str(numPixels)
  numPixels_step = int(numPixels/10)

  data = np.zeros((numIfgrams,numPixels),np.float32)
  for ni in range(numIfgrams):
    dset=h5flat['interferograms'][ifgramList[ni]].get(ifgramList[ni])
    #dset = h5flat[ifgramList[ni]].get(h5flat[ifgramList[ni]].keys()[0])
    d = dset[0:dset.shape[0],0:dset.shape[1]]
    #print np.shape(d)

  del d
  dataPoint = np.zeros((numIfgrams,1),np.float32)
  modelDimension = np.shape(B)[1]
  tempDeformation = np.zeros((modelDimension+1,numPixels),np.float32)
  for ni in range(numPixels):
    dataPoint = data[:,ni]
    nan_ndx = dataPoint == 0.
    fin_ndx = dataPoint != 0.
    nan_fin = dataPoint.copy()
    nan_fin[nan_ndx] = 1
    if not nan_fin.sum() == len(nan_fin):
      B1tmp = np.dot(B1,np.diag(fin_ndx))
      tmpe_ratea = np.dot(B1tmp,dataPoint)
      zero = np.array([0.],np.float32)
      defo = np.concatenate((zero,np.cumsum([tmpe_ratea*dt])))
      tempDeformation[:,ni] = defo
    #if not np.remainder(ni,10000): print 'Processing point: %7d of %7d ' % (ni,numPixels)
    if not np.remainder(ni,numPixels_step):
      print 'Processing point: %8d of %8d, %3d' % (ni,numPixels,(10*ni/numPixels_step))+'%'
  del data
  timeseries = np.zeros((modelDimension+1,np.shape(dset)[0],np.shape(dset)[1]),np.float32)
  factor = -1*float(h5flat['interferograms'][ifgramList[0]].attrs['WAVELENGTH'])/(4.*np.pi)
  for ni in range(modelDimension+1):
    timeseries[ni] = tempDeformation[ni].reshape(np.shape(dset)[1],np.shape(dset)[0]).T
    timeseries[ni] = timeseries[ni]*factor
  del tempDeformation
  timeseriesDict = {}
  for key, value in h5flat['interferograms'][ifgramList[0]].attrs.iteritems():
    timeseriesDict[key] = value 

  dateIndex={}
  for ni in range(len(dateList)):    dateIndex[dateList[ni]]=ni
  if not 'timeseries' in h5timeseries:
    group = h5timeseries.create_group('timeseries')
    for key,value in timeseriesDict.iteritems():    group.attrs[key] = value
  
  for date in dateList:
    if not date in h5timeseries['timeseries']:
      dset = group.create_dataset(date, data=timeseries[dateIndex[date]], compression='gzip')
  print 'Time series inversion took ' + str(time.time()-total) +' secs'



def timeseries_inversion_L1(h5flat,h5timeseries):

  try:
    from l1 import l1
    from cvxopt import normal,matrix
  except:
    print '-----------------------------------------------------------------------'
    print 'cvxopt should be installed to be able to use the L1 norm minimization.'
    print '-----------------------------------------------------------------------'
    sys.exit(1)
    #modified from sbas.py written by scott baker, 2012 

  
  total = time.time()
  A,B = design_matrix(h5flat)
  tbase,dateList,dateDict,dateDict2 = date_list(h5flat)
  dt = np.diff(tbase)
  BL1 = matrix(B)
  B1 = np.linalg.pinv(B)
  B1 = np.array(B1,np.float32)
  ifgramList = h5flat['interferograms'].keys()
  numIfgrams = len(ifgramList)
  #dset = h5flat[ifgramList[0]].get(h5flat[ifgramList[0]].keys()[0])
  #data = dset[0:dset.shape[0],0:dset.shape[1]]
  dset=h5flat['interferograms'][ifgramList[0]].get(ifgramList[0]) 
  data = dset[0:dset.shape[0],0:dset.shape[1]] 
  numPixels = np.shape(data)[0]*np.shape(data)[1]
  print 'Reading in the interferograms'
  print numIfgrams,numPixels

  #data = np.zeros((numIfgrams,numPixels),np.float32)
  data = np.zeros((numIfgrams,numPixels))
  for ni in range(numIfgrams):
    dset=h5flat['interferograms'][ifgramList[ni]].get(ifgramList[ni])
    #dset = h5flat[ifgramList[ni]].get(h5flat[ifgramList[ni]].keys()[0])
    d = dset[0:dset.shape[0],0:dset.shape[1]]
    #print np.shape(d)

    data[ni] = d.flatten(1)
  del d
  dataPoint = np.zeros((numIfgrams,1),np.float32)
  modelDimension = np.shape(B)[1]
  tempDeformation = np.zeros((modelDimension+1,numPixels),np.float32)
  print data.shape
  DataL1=matrix(data)
  L1ORL2=np.ones((numPixels,1))
  for ni in range(numPixels):
    print ni
    dataPoint = data[:,ni]
    nan_ndx = dataPoint == 0.
    fin_ndx = dataPoint != 0.
    nan_fin = dataPoint.copy()
    nan_fin[nan_ndx] = 1
    if not nan_fin.sum() == len(nan_fin):
      
      B1tmp = np.dot(B1,np.diag(fin_ndx))
      #tmpe_ratea = np.dot(B1tmp,dataPoint)
      try:
          tmpe_ratea=np.array(l1(BL1,DataL1[:,ni]))
          zero = np.array([0.],np.float32)
          defo = np.concatenate((zero,np.cumsum([tmpe_ratea[:,0]*dt])))
      except:
          tmpe_ratea = np.dot(B1tmp,dataPoint)
          L1ORL2[ni]=0      
          zero = np.array([0.],np.float32)
          defo = np.concatenate((zero,np.cumsum([tmpe_ratea*dt])))

      tempDeformation[:,ni] = defo
    if not np.remainder(ni,10000): print 'Processing point: %7d of %7d ' % (ni,numPixels)
  del data
  timeseries = np.zeros((modelDimension+1,np.shape(dset)[0],np.shape(dset)[1]),np.float32)
  factor = -1*float(h5flat['interferograms'][ifgramList[0]].attrs['WAVELENGTH'])/(4.*np.pi)
  for ni in range(modelDimension+1):
    timeseries[ni] = tempDeformation[ni].reshape(np.shape(dset)[1],np.shape(dset)[0]).T
    timeseries[ni] = timeseries[ni]*factor
  del tempDeformation
  L1ORL2=np.reshape(L1ORL2,(np.shape(dset)[1],np.shape(dset)[0])).T
  
  timeseriesDict = {}
  for key, value in h5flat['interferograms'][ifgramList[0]].attrs.iteritems():
          timeseriesDict[key] = value

  dateIndex={}
  for ni in range(len(dateList)):
    dateIndex[dateList[ni]]=ni
  if not 'timeseries' in h5timeseries:
    group = h5timeseries.create_group('timeseries')
    for key,value in timeseriesDict.iteritems():
      group.attrs[key] = value

  for date in dateList:
    if not date in h5timeseries['timeseries']:
      dset = group.create_dataset(date, data=timeseries[dateIndex[date]], compression='gzip')
  print 'Time series inversion took ' + str(time.time()-total) +' secs'
  L1orL2h5=h5py.File('L1orL2.h5','w')
  gr=L1orL2h5.create_group('mask') 
  dset=gr.create_dataset('mask',data=L1ORL2,compression='gzip')
  L1orL2h5.close()

def Baseline_timeseries(igramsFile):
  h5file = h5py.File(igramsFile)
  igramList = h5file['interferograms'].keys()
  Bp_igram=[]
  for igram in igramList:
      Bp_igram.append((float(h5file['interferograms'][igram].attrs['P_BASELINE_BOTTOM_HDR'])+float(h5file['interferograms'][igram].attrs['P_BASELINE_TOP_HDR']))/2)


  A,B=design_matrix(h5file)
  tbase,dateList,dateDict,dateList1 = date_list(h5file)
  dt = np.diff(tbase)

  Bp_rate=np.dot(np.linalg.pinv(B),Bp_igram)
  zero = np.array([0.],np.float32)
  Bperp = np.concatenate((zero,np.cumsum([Bp_rate*dt])))
  h5file.close()
  
  return Bperp


def dBh_dBv_timeseries(igramsFile):
  h5file = h5py.File(igramsFile)
  igramList = h5file['interferograms'].keys()
  dBh_igram=[]
  dBv_igram=[]
  for igram in igramList:
      dBh_igram.append(float(h5file['interferograms'][igram].attrs['H_BASELINE_RATE_HDR']))
      dBv_igram.append(float(h5file['interferograms'][igram].attrs['V_BASELINE_RATE_HDR']))
  

  A,B=design_matrix(h5file)
  tbase,dateList,dateDict,dateList1 = date_list(h5file)
  dt = np.diff(tbase)

  Bh_rate=np.dot(np.linalg.pinv(B),dBh_igram)
  zero = np.array([0.],np.float32)
  dBh = np.concatenate((zero,np.cumsum([Bh_rate*dt])))
  
  Bv_rate=np.dot(np.linalg.pinv(B),dBv_igram)
  zero = np.array([0.],np.float32)
  dBv = np.concatenate((zero,np.cumsum([Bv_rate*dt])))

  h5file.close()

  return dBh,dBv

def Bh_Bv_timeseries(igramsFile):
  h5file = h5py.File(igramsFile)
  igramList = h5file['interferograms'].keys()
  Bh_igram=[]
  Bv_igram=[]
  for igram in igramList:
      Bh_igram.append(float(h5file['interferograms'][igram].attrs['H_BASELINE_TOP_HDR']))
      Bv_igram.append(float(h5file['interferograms'][igram].attrs['V_BASELINE_TOP_HDR']))


  A,B=design_matrix(h5file)
  tbase,dateList,dateDict,dateList1 = date_list(h5file)
  dt = np.diff(tbase)

  Bh_rate=np.dot(np.linalg.pinv(B),Bh_igram)
  zero = np.array([0.],np.float32)
  Bh = np.concatenate((zero,np.cumsum([Bh_rate*dt])))

  Bv_rate=np.dot(np.linalg.pinv(B),Bv_igram)
  zero = np.array([0.],np.float32)
  Bv = np.concatenate((zero,np.cumsum([Bv_rate*dt])))

  h5file.close()

  return Bh,Bv

def stacking(h5file):

  # h5file = h5py.File(file)
   numIfgrams = len(h5file['interferograms'].keys())
   if numIfgrams == 0.:
      print "There is no data in the file"
      sys.exit(1)

   print numIfgrams

   igramList = h5file['interferograms'].keys()


   stack=np.zeros([int(h5file['interferograms'][igramList[0]].attrs['FILE_LENGTH']),int(h5file['interferograms'][igramList[0]].attrs['WIDTH'])])
   for igram in igramList:
      print igram
      dset = h5file['interferograms'][igram].get(igram)
      unw=dset[0:dset.shape[0],0:dset.shape[1]]
      stack=stack+unw
   return stack

def yymmdd2YYYYMMDD(date):
   if date[0] == '9':
      date = '19'+date
   else:
      date = '20'+date
   return date

def make_triangle(dates12,igram1,igram2,igram3):

  dates=[]
  dates.append(igram1.split('-')[0])
  dates.append(igram1.split('-')[1])
  dates.append(igram2.split('-')[1])
  datesyy=[]
  for d in dates:
     datesyy.append(yymmdd2YYYYMMDD(d))

  datesyy.sort()
  Igramtriangle=[]
  Igramtriangle.append(datesyy[0][2:]+'-'+datesyy[1][2:])
  Igramtriangle.append(datesyy[0][2:]+'-'+datesyy[2][2:])
  Igramtriangle.append(datesyy[1][2:]+'-'+datesyy[2][2:])

  IgramtriangleIndexes=[dates12.index(Igramtriangle[0]),dates12.index(Igramtriangle[1]),dates12.index(Igramtriangle[2])]
  return Igramtriangle,IgramtriangleIndexes

def get_triangles(h5file):
   
   k=h5file.keys()
   igramList=h5file[k[0]].keys()
  
   dates12=[]
   for igram in igramList:
       dates12.append(h5file[k[0]][igram].attrs['DATE12'])
   Triangles=[]
   Triangles_indexes=[]
   for igram1 in dates12:
      igram1_date1=igram1.split('-')[0]
      igram1_date2=igram1.split('-')[1]

      igram2=[]
      igram2_date2=[]
      for d in dates12:
        if igram1_date2==d.split('-')[0]:
           igram2.append(d)
           igram2_date2.append(d.split('-')[1])

      igram3=[]
      igram3_date2=[]
      for d in dates12:
        if igram1_date1==d.split('-')[0] and d != igram1:
           igram3.append(d)
           igram3_date2.append(d.split('-')[1])

      for date in  igram2_date2:
        if date in igram3_date2:
           Igramtriangle,IgramtriangleIndexes=make_triangle(dates12,igram1,igram2[igram2_date2.index(date)],igram3[igram3_date2.index(date)])
           if not Igramtriangle in Triangles:
              Triangles.append(Igramtriangle)
              Triangles_indexes.append(IgramtriangleIndexes)

   numTriangles = np.shape(Triangles_indexes)[0]
   curls=np.zeros([numTriangles,3],dtype=np.int)
   for i in range(numTriangles):
      curls[i][:]=Triangles_indexes[i]

   numIgrams=len(igramList)
   C=np.zeros([numTriangles,numIgrams])
   for ni in range(numTriangles):
      C[ni][curls[ni][0]]=1
      C[ni][curls[ni][1]]=-1
      C[ni][curls[ni][2]]=1

   return curls,Triangles,C


def generate_curls(curlfile,h5file,Triangles,curls):

   ifgramList = h5file['interferograms'].keys()
   h5curlfile=h5py.File(curlfile,'w')
   gg = h5curlfile.create_group('interferograms')
   lcurls=np.shape(curls)[0]
   for i in range(lcurls):
       d1=h5file['interferograms'][ifgramList[curls[i,0]]].get(ifgramList[curls[i,0]])
       d2=h5file['interferograms'][ifgramList[curls[i,1]]].get(ifgramList[curls[i,1]])
       d3=h5file['interferograms'][ifgramList[curls[i,2]]].get(ifgramList[curls[i,2]])
       data1=d1[0:d1.shape[0],0:d1.shape[1]]
       data2=d2[0:d2.shape[0],0:d2.shape[1]]
       data3=d3[0:d3.shape[0],0:d3.shape[1]]

       print i
       group = gg.create_group(Triangles[i][0]+'_'+Triangles[i][1]+'_'+Triangles[i][2])
       dset = group.create_dataset(Triangles[i][0]+'_'+Triangles[i][1]+'_'+Triangles[i][2], data=data1+data3-data2, compression='gzip')
       for key, value in h5file['interferograms'][ifgramList[curls[i,0]]].attrs.iteritems():
          group.attrs[key] = value

   h5curlfile.close()


