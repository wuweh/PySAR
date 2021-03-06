#! /usr/bin/env python
############################################################
# Program is part of PySAR v1.0                            #
# Copyright(c) 2013, Heresh Fattahi                        #
# Author:  Heresh Fattahi                                  #
############################################################

import sys
import os
import numpy as np
import h5py
from scipy.linalg import pinv as pinv
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib
import _readfile as readfile

def to_percent(y, position):
    # Ignore the passed in position. This has the effect of scaling the default
    # tick locations.
    s = str(100 * y)

    # The percent symbol needs escaping in latex
    if matplotlib.rcParams['text.usetex'] == True:
        return s + r'$\%$'
    else:
        return s + '%'

def Usage():
  print '''
******************************************************************************************************
******************************************************************************************************

  Simultaneously correcting the baseline error and stratified tropospheric delay correlated with DEM.

  Usage:

  baseline_trop.py  time-series  dem polynomial_order  mask baseline_error_direction
  
  Example:
      baseline_trop.py  timeseries.h5 radar.hgt 1
      baseline_trop.py  timeseries.h5 radar.hgt 1 range
      baseline_trop.py  timeseries.h5 radar.hgt 1 range_and_azimuth mask.h5

******************************************************************************************************
******************************************************************************************************
  '''

def main(argv):
  
  try:
    File = argv[0]
    demFile=argv[1]
    p=int(argv[2])
  except:
    Usage() ; sys.exit(1)

  try:
    baseline_error=argv[3]
  except:
    baseline_error='range_and_azimuth'
  ##################################
  h5file = h5py.File(File)
  dateList = h5file['timeseries'].keys()
  ##################################

  try:
    maskFile=argv[4]
    h5Mask = h5py.File(maskFile,'r')
    kMask=h5Mask.keys()
    dset1 = h5Mask[kMask[0]].get(kMask[0])
    Mask = dset1[0:dset1.shape[0],0:dset1.shape[1]]
  except:
    dset1 = h5file['mask'].get('mask')
    Mask = dset1[0:dset1.shape[0],0:dset1.shape[1]]
  

 # try:
 #   maskFile=argv[3]
 # except:
 #   maskFile='Mask.h5'

#  try:
#    baseline_error=argv[4]
#  except:
#    baseline_error='range_and_azimuth'
  
  print baseline_error  
  ##################################
 # h5Mask = h5py.File(maskFile)
 # kMask=h5Mask.keys()
 # dset1 = h5Mask[kMask[0]].get(kMask[0])
 # Mask = dset1[0:dset1.shape[0],0:dset1.shape[1]]
  Mask=Mask.flatten(1)
  ndx= Mask !=0
  ##################################
 # h5file = h5py.File(File)
 # dateList = h5file['timeseries'].keys() 
  ##################################
  nt=float(h5file['timeseries'].attrs['LOOK_REF1'])
  ft=float(h5file['timeseries'].attrs['LOOK_REF2'])
  sy,sx=np.shape(dset1)
  npixel=sx*sy
  lookangle=np.tile(np.linspace(nt,ft,sx),[sy,1])
  lookangle=lookangle.flatten(1)*np.pi/180.0
  Fh=-np.sin(lookangle)
  Fv=-np.cos(lookangle)  

  print 'Looking for azimuth pixel size'
  try:
     daz=float(h5file['timeseries'].attrs['AZIMUTH_PIXEL_SIZE'])
  except:
     print'''
     ERROR!
     The attribute AZIMUTH_PIXEL_SIZE was not found!
     Possible cause of error: Geo coordinate.
     This function works only in radar coordinate system.
  '''   
     sys.exit(1)

  lines=np.tile(np.arange(0,sy,1),[1,sx])
  lines=lines.flatten(1)
  rs=lines*daz
 
  if baseline_error=='range_and_azimuth': 
     A = np.zeros([npixel,4])

     A[:,0]=Fh
     A[:,1]=Fh*rs
     A[:,2]=Fv
     A[:,3]=Fv*rs 
     num_base_par=4
  elif baseline_error=='range':
     A = np.zeros([npixel,2])

     A[:,0]=Fh
     A[:,1]=Fv
     num_base_par=2

  ###########################################
  yref=int(h5file['timeseries'].attrs['ref_y'])
  xref=int(h5file['timeseries'].attrs['ref_x'])
  ###########################################
  if os.path.basename(demFile).split('.')[1]=='hgt':
       amp,dem,demRsc = readfile.read_float32(demFile)
  elif os.path.basename(demFile).split('.')[1]=='dem':
       dem,demRsc = readfile.read_dem(demFile)

  dem=dem-dem[yref][xref]
  dem=dem.flatten(1)
###################################################
  if p==1:
       # A=np.vstack((dem[ndx],np.ones(len(dem[ndx])))).T
        B = np.vstack((dem,np.ones(len(dem)))).T
  elif p==2:
       # A=np.vstack((dem[ndx]**2,dem[ndx],np.ones(len(dem[ndx])))).T
        B = np.vstack((dem**2,dem,np.ones(len(dem)))).T
  elif p==3:
      #  A = np.vstack((dem[ndx]**3,dem[ndx]**2,dem[ndx],np.ones(len(dem[ndx])))).T
        B = np.vstack((dem**3,dem**2,dem,np.ones(len(dem)))).T
  print np.shape(A)

  Ainv=np.linalg.pinv(A)
###################################################
 

  Bh=[]
  Bv=[]
  Bhrate=[]
  Bvrate=[]
  Be=np.zeros([len(dateList),num_base_par+p+1])  
  print '%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%'
  for i in range(1,len(dateList)):
      dset = h5file['timeseries'].get(dateList[i])
      data = dset[0:dset.shape[0],0:dset.shape[1]]
      L = data.flatten(1)
      M=np.hstack((A,B))
      Berror=np.dot(np.linalg.pinv(M[ndx]),L[ndx])
      Bh.append(Berror[0])
      Bhrate.append(Berror[1])
      Bv.append(Berror[2])
      Bvrate.append(Berror[3])
      Be[i,:]=Berror
      print Berror
  print '%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%' 
  print 'baseline error           mean                          std'   
  print '       bh     :  ' +str(np.mean(Bh)) + '     ,  '+str(np.std(Bh))
  print '     bh rate  :  ' +str(np.mean(Bhrate)) + '     ,  '+str(np.std(Bhrate))
  print '       bv     :  ' +str(np.mean(Bv)) + '     ,  '+str(np.std(Bv))
  print '     bv rate  :  ' +str(np.mean(Bvrate)) + '     ,  '+str(np.std(Bvrate))
  print '%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%'       
 # plt.hist(Bh,bins=8,normed=True)
 # formatter = FuncFormatter(to_percent)
  # Set the formatter
 # plt.gca().yaxis.set_major_formatter(formatter)    
#  plt.show()
  print '%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%'
 # print 'Estimating Baseline error from each differences ...'


 # print '%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%'


  orbEffect=np.zeros([len(dateList),sy,sx])
  for i in range(1,len(dateList)):
     effect=np.dot(M,Be[i,:])
     effect=np.reshape(effect,[sx,sy]).T
    # orbEffect[i,:,:]=orbEffect[i-1,:,:]+effect     
    # orbEffect[i,:,:]=orbEffect[i,:,:]-orbEffect[i,yref,xref]
     orbEffect[i,:,:]=effect - effect[yref,xref]
     del effect

  print 'Correctiing the time series '
  outName=File.replace('.h5','')+'_BaseTropCor.h5'
  h5orbCor=h5py.File(outName,'w')
  group = h5orbCor.create_group('timeseries')
  for i in range(len(dateList)):
      dset1 = h5file['timeseries'].get(dateList[i])
      data = dset1[0:dset1.shape[0],0:dset1.shape[1]] - orbEffect[i,:,:]
      dset = group.create_dataset(dateList[i], data=data, compression='gzip')      

  for key,value in h5file['timeseries'].attrs.iteritems():
      group.attrs[key] = value


  dset1 = h5file['mask'].get('mask')
  group=h5orbCor.create_group('mask')
  dset = group.create_dataset('mask', data=dset1, compression='gzip')

  h5file.close()
  h5orbCor.close()
if __name__ == '__main__':

  main(sys.argv[1:])  





