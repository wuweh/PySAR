#! /usr/bin/env python
############################################################
# Program is part of PySAR v1.0                            #
# Copyright(c) 2013, Heresh Fattahi                        #
# Author:  Heresh Fattahi                                  #
############################################################
#
# Add check_num/check_size to .int/.cor file, Yunjun, Jul 2015
#

import os
import sys
import glob
import time

import numpy as np
import h5py

import _readfile as readfile
from pysar._pysar_utilities import check_variable_name


def mode (thelist):
  counts = {}
  for item in thelist:
    counts [item] = counts.get (item, 0) + 1
  maxcount = 0
  maxitem  = None
  for k, v in counts.items ():
    if v > maxcount:
      maxitem  = k
      maxcount = v
  if maxcount == 1:                           print "All values only appear once"
  elif counts.values().count (maxcount) > 1:  print "List has multiple modes"
  else:                                       return maxitem

def check_number(k,epochList):
  numEpoch=len(epochList)
  if numEpoch>0:
    print '\nNumber of '+k+' found: ' +str(numEpoch)
  else:
    print "\n*********************************"
    print 'WARNING: No '+k+' found!'
    print '  Check the path of '+k+' in the template file'
    print '  Check the inputdataopt.interf option in the template file'
    print "*********************************"
    sys.exit(1)

def check_size(k,epochList):
  width_list =[]
  length_list=[]
  epoch_list =[]
  for epoch in epochList:
    rscFile = readfile.read_rsc_file(epoch+'.rsc')
    width   = rscFile['WIDTH']
    length  = rscFile['FILE_LENGTH']
    width_list.append(width)
    length_list.append(length)
    epoch_list.append(epoch)

  mode_width  = mode(width_list)
  mode_length = mode(length_list)

  if width_list.count(mode_width)!=len(width_list) or length_list.count(mode_length)!=len(length_list):
     print '%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n'
     print 'WARNING: Some '+k+' may have the wrong dimensions!\n'
     print 'All '+k+' should have the same size.\n'
     print 'The width and length of the majority of '+k+' are: ' + str(mode_width)+', '+str(mode_length)+'\n'
     print 'But the following '+k+' have different dimensions and thus not considered in the time-series: \n'
     for epoch in epoch_list:
        rscFile=readfile.read_rsc_file(epoch+'.rsc')
        width  = rscFile['WIDTH']
        length = rscFile['FILE_LENGTH']
        if width != mode_width or length != mode_length:
           print '  '+ epoch + '    width: '+width+'  length: '+length
           epochList.remove(epoch)
     print '\nNumber of '+k+' to be loaded: '+str(len(epochList))
     print '%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%'
  return epochList, mode_width, mode_length


def main(argv):
  try:
    templateFile = argv[1]
  except:
    print '''
    *******************************************

       loading the processed data for PySAR:
	   interferograms (unwrapped and wrapped)
	   coherence files
           geomap.trans file
           DEM (radar and geo coordinate)
       
       Usage: load_data.py TEMPLATEFILE  

    *******************************************         
    '''
    sys.exit(1)

  templateContents = readfile.read_template(templateFile)
  projectName = os.path.basename(templateFile).partition('.')[0]

############# Assign workubf directory ##############################
  try:     tssarProjectDir = os.getenv('TSSARDIR') +'/'+projectName                     # use TSSARDIR if environment variable exist
  except:  tssarProjectDir = os.getenv('SCRATCHDIR') + '/' + projectName + "/TSSAR"     # FA 7/2015: adopted for new directory structure
 
  print "QQ " + tssarProjectDir
  if not os.path.isdir(tssarProjectDir): os.mkdir(tssarProjectDir)

########### Use defaults if paths not given in template file #########
  try:    igramPath = templateContents['pysar.inputFiles'];  igramPath = check_variable_name(igramPath)
  except: igramPath = os.getenv('SCRATCHDIR') + '/' + projectName + '/PROCESS/DONE/IFGRAM*/filt_*.unw'

  try:    corPath   = templateContents['pysar.corFiles'];      corPath = check_variable_name(corPath)
  except: corPath   = os.getenv('SCRATCHDIR') + '/' + projectName + '/PROCESS/DONE/IFGRAM*/filt_*.cor'

  try:    wrapPath  = templateContents['pysar.wrappedFiles']; wrapPath = check_variable_name(wrapPath)
  except: wrapPath  = os.getenv('SCRATCHDIR') + '/' + projectName + '/PROCESS/DONE/IFGRAM*/filt_*.int'

  #try:    demRdrPath = templateContents['pysar.dem.radarCoord'];  demRdrPath = check_variable_name(demRdrPath)
  #except: 
  #  demRdrList=glob.glob(demRdrPath)
  


###########################################################################
######################### Unwrapped Interferograms ########################

  try:
    if os.path.isfile(tssarProjectDir+'/LoadedData.h5'):
      print '\nLoadedData.h5'+ '  already exists.'
      sys.exit(1)
    igramList = glob.glob(igramPath)    
    k = 'interferograms'
    check_number(k,igramList)	# number check 
    print 'loading interferograms ...'
    igramList,mode_width,mode_length = check_size(k,igramList)	# size check

    h5file = tssarProjectDir+'/LoadedData.h5'
    f = h5py.File(h5file)
    gg = f.create_group('interferograms')
    MaskZero=np.ones([int(mode_length),int(mode_width)])
    for igram in igramList:
      if not os.path.basename(igram) in f:
        print 'Adding ' + igram
        group = gg.create_group(os.path.basename(igram))
        amp,unw,unwrsc = readfile.read_float32(igram)
        MaskZero=amp*MaskZero
 
        dset = group.create_dataset(os.path.basename(igram), data=unw, compression='gzip')
        for key,value in unwrsc.iteritems():
          group.attrs[key] = value

        d1,d2=unwrsc['DATE12'].split('-')
        baseline_file=os.path.dirname(igram)+'/'+d1+'_'+d2+'_baseline.rsc'
        baseline=readfile.read_rsc_file(baseline_file)
        for key,value in baseline.iteritems():
          group.attrs[key] = value
      else:
        print os.path.basename(h5file) + " already contains " + os.path.basename(igram)

    Mask=np.ones([int(mode_length),int(mode_width)])
    Mask[MaskZero==0]=0
    gm = f.create_group('mask')
    dset = gm.create_dataset('mask', data=Mask, compression='gzip')
    f.close()

    ############## Mask file ###############
    print 'writing to Mask.h5\n'
    Mask=np.ones([int(mode_length),int(mode_width)])
    Mask[MaskZero==0]=0
    h5file = tssarProjectDir+'/Mask.h5'
    h5mask = h5py.File(h5file,'w')
    group=h5mask.create_group('mask')
    dset = group.create_dataset(os.path.basename('mask'), data=Mask, compression='gzip')
    for key,value in unwrsc.iteritems():
       group.attrs[key] = value
    h5mask.close()

  except:
    print 'No unwrapped interferogram is loaded.\n'


########################################################################
############################# Coherence ################################
  try:
    if os.path.isfile(tssarProjectDir+'/Coherence.h5'):
      print '\nCoherence.h5'+ '  already exists.'
      sys.exit(1)
    corList = glob.glob(corPath)
    k = 'coherence'
    check_number(k,corList)   # number check 
    print 'loading coherence files ...'
    corList,mode_width,mode_length = check_size(k,corList)     # size check

    h5file = tssarProjectDir+'/Coherence.h5'
    fcor = h5py.File(h5file)
    gg = fcor.create_group('coherence')
    meanCoherence=np.zeros([int(mode_length),int(mode_width)])
    for cor in corList:
      if not os.path.basename(cor) in fcor:
        print 'Adding ' + cor
        group = gg.create_group(os.path.basename(cor))
        amp,unw,unwrsc = readfile.read_float32(cor)

        meanCoherence=meanCoherence+unw
        dset = group.create_dataset(os.path.basename(cor), data=unw, compression='gzip')
        for key,value in unwrsc.iteritems():
           group.attrs[key] = value

        d1,d2=unwrsc['DATE12'].split('-')
        baseline_file=os.path.dirname(cor)+'/'+d1+'_'+d2+'_baseline.rsc'
        baseline=readfile.read_rsc_file(baseline_file)
        for key,value in baseline.iteritems():
           group.attrs[key] = value
      else:
        print os.path.basename(h5file) + " already contains " + os.path.basename(cor)
    #fcor.close()

    ########### mean coherence file ###############
    meanCoherence=meanCoherence/(len(corList))
    print 'writing meanCoherence group to the coherence h5 file'
    gc = fcor.create_group('meanCoherence')
    dset = gc.create_dataset('meanCoherence', data=meanCoherence, compression='gzip')

    print 'writing average_spatial_coherence.h5\n'
    h5file_CorMean = tssarProjectDir+'/average_spatial_coherence.h5'
    fcor_mean = h5py.File(h5file_CorMean,'w')
    group=fcor_mean.create_group('mask')
    dset = group.create_dataset(os.path.basename('mask'), data=meanCoherence, compression='gzip')
    for key,value in unwrsc.iteritems():
       group.attrs[key] = value
    fcor_mean.close()

    fcor.close()

  except:
    print 'No correlation file is loaded.\n'


##############################################################################
########################## Wrapped Interferograms ############################

  try:
    if os.path.isfile(tssarProjectDir+'/Wrapped.h5'):
      print '\nWrapped.h5'+ '  already exists.'
      sys.exit(1)
    wrapList = glob.glob(wrapPath)
    k = 'wrapped'
    check_number(k,wrapList)   # number check 
    print 'loading wrapped phase ...'
    wrapList,mode_width,mode_length = check_size(k,wrapList)     # size check

    h5file = tssarProjectDir+'/Wrapped.h5'
    fw = h5py.File(h5file)
    gg = fw.create_group('wrapped')
    for wrap in wrapList:
      if not os.path.basename(wrap) in fw:
        print 'Adding ' + wrap
        group = gg.create_group(os.path.basename(wrap))
        amp,unw,unwrsc = readfile.read_complex64(wrap)

        dset = group.create_dataset(os.path.basename(wrap), data=unw, compression='gzip')
        for key,value in unwrsc.iteritems():
           group.attrs[key] = value

        d1,d2=unwrsc['DATE12'].split('-')
        baseline_file=os.path.dirname(wrap)+'/'+d1+'_'+d2+'_baseline.rsc'
        baseline=readfile.read_rsc_file(baseline_file)
        for key,value in baseline.iteritems():
           group.attrs[key] = value
      else:
        print os.path.basename(h5file) + " already contains " + os.path.basename(wrap)
    fw.close()
    print 'Writed '+str(len(wrapList))+' wrapped interferograms to '+h5file+'\n'
  except:
    print 'No wrapped interferogram is loaded.\n'


##############################################################################
################################# geomap.trans ###############################

  try:
    geomapPath = tssarProjectDir+'/geomap*.trans'
    geomapList = glob.glob(geomapPath)
    if len(geomapList)>0:
      print '\ngeomap*.trans'+ '  already exists.'
      sys.exit(1)

    geomapPath=templateContents['pysar.geomap']
    geomapPath=check_variable_name(geomapPath)
    geomapList=glob.glob(geomapPath)

    cpCmd="cp " + geomapList[0] + " " + tssarProjectDir
    print cpCmd
    os.system(cpCmd)
    cpCmd="cp " + geomapList[0] + ".rsc " + tssarProjectDir
    print cpCmd+'\n'
    os.system(cpCmd)
  except:
    #print "*********************************"
    print "no geomap file is loaded.\n"
    #print "*********************************\n"


##############################################################################
##################################  DEM  #####################################

  try:
    demRdrPath = tssarProjectDir+'/radar*.hgt'
    demRdrList = glob.glob(demRdrPath)
    if len(demRdrList)>0:
      print '\nradar*.hgt'+ '  already exists.'
      sys.exit(1)

    demRdrPath=templateContents['pysar.dem.radarCoord']
    demRdrPath=check_variable_name(demRdrPath)
    demRdrList=glob.glob(demRdrPath)

    cpCmd="cp " + demRdrList[0] + " " + tssarProjectDir
    print cpCmd
    os.system(cpCmd)
    cpCmd="cp " + demRdrList[0] + ".rsc " + tssarProjectDir
    print cpCmd+'\n'
    os.system(cpCmd)
  except:
    #print "*********************************"
    print "no DEM (radar coordinate) file is loaded.\n"
    #print "*********************************"

  try:
    demGeoPath = tssarProjectDir+'/*.dem'
    demGeoList = glob.glob(demGeoPath)
    if len(demGeoList)>0:
      print '\n*.dem'+ '  already exists.'
      sys.exit(1)

    demGeoPath=templateContents['pysar.dem.geoCoord']
    demGeoPath=check_variable_name(demGeoPath)
    demGeoList=glob.glob(demGeoPath)

    cpCmd="cp " + demGeoList[0] + " " + tssarProjectDir
    print cpCmd
    os.system(cpCmd)
    cpCmd="cp " + demGeoList[0] + ".rsc " + tssarProjectDir
    print cpCmd+'\n'
    os.system(cpCmd)
  except:
    #print "*********************************"
    print "no DEM (geo coordinate) file is loaded.\n"
    #print "*********************************\n"
 

##############################################################################
##############################################################################

if __name__ == '__main__':
  main(sys.argv[:])
