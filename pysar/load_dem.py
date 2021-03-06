#! /usr/bin/env python
import h5py
import _readfile as readfile
import sys
import os

try:
  demFile = sys.argv[1]
except:

  print '''

  ********************************
  ********************************
  convert .dem or .hgt file to .h5 file

  load_dem.py input output

  load_dem.py SanAndreas.dem 
  
  load_dem.py SanAndreas.dem SanAndreas.h5

  load_dem.py  radar_8rlks.hgt radar_8rlks.h5

  ********************************
  ********************************
'''
  
  sys.exit(1)


ext = os.path.splitext(demFile)[1]

if ext == '.hgt':

   amp,dem,demRsc = readfile.read_float32(demFile)

elif ext == '.dem':
   dem,demRsc =readfile.read_dem(demFile)


try:
  outName=sys.argv[2]
except:
  outName='dem.h5'


h5=h5py.File(outName,'w')
group=h5.create_group('dem')

dset = group.create_dataset('dem', data=dem, compression='gzip')

for key , value in demRsc.iteritems():
     group.attrs[key]=value

group.attrs['ref_y']=0
group.attrs['ref_x']=0
h5.close()


