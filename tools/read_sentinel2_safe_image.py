# read_sentinel2_safe_image.py

import numpy, os
import rasterio
from skimage.transform import resize # *** CRITICAL: Used for robust resizing ***
import xml.etree.ElementTree as ET
from tqdm import tqdm
import scipy.ndimage
# NOTE: scipy.ndimage is kept but now ONLY used for the small-factor resampling in the old flow.

# read Sentinel-2 image in SAFE format and return it as a dictionarry
def read_s2(safe, res, target_size=None):
    """
    Reads SAFE spectral data, extracts angles from XMLs, and applies resizing.
    The target_size (H, W) is used to force the angle grid resize, avoiding MemoryError.
    """
    inpath=safe+'/GRANULE/'+os.listdir(safe+'/GRANULE/')[0]+'/IMG_DATA/R%sm/'%(str(res))
    MTD_TL=safe+'/GRANULE/%s/MTD_TL.xml'%(os.listdir(safe+'/GRANULE/')[0])
    
    s2={}
    print('Reading Sentinel-2 image')
    for fn in tqdm([os.path.join(inpath,f) for f in os.listdir(inpath) if f.endswith('.jp2')]): 
        with rasterio.open(fn) as src:
            s2.update({'profile':src.profile})
            s2.update({fn.split('_')[-2]:src.read(1)}) 
            
    # Add geometry of acquisition, passing the target size for robust resizing
    (SZA, SAA, colstep,rowstep)=extract_sun_angles(MTD_TL, target_size)
    (VZA, VAA, colstep,rowstep)=extract_sensor_angles(MTD_TL, target_size)
    s2.update({'SZA':SZA,'SAA':SAA,'VZA':VZA,'VAA':VAA})
    s2['profile'].update({'count':len(s2)-1})
    return s2

# extract sun view and azimuth angles from xml file saved in Sentinel-2 SAFE data
def extract_sun_angles(xml, target_size=None):
    """Extract Sentinel-2 solar angle bands values from MTD_TL.xml and resize to target_size."""
    
    # --- FIX 1: Initialize all variables in function's local scope ---
    solar_zenith_values = numpy.empty((23,23,)) * numpy.nan 
    solar_azimuth_values = numpy.empty((23,23,)) * numpy.nan
    colstep = 0.0 
    rowstep = 0.0 
    zenith = None; azimuth = None # Initialized for logic flow

    # Parse the XML file
    tree = ET.parse(xml)
    root = tree.getroot()

    # Find the angles (parsing logic)
    for child in root:
        if child.tag[-14:] == 'Geometric_Info':
            geoinfo = child

    for segment in geoinfo:
        if segment.tag == 'Tile_Angles':
            angles = segment

    for angle in angles:
        if angle.tag == 'Sun_Angles_Grid':
            for bset in angle:
                if bset.tag == 'Zenith':
                    zenith = bset
                if bset.tag == 'Azimuth':
                    azimuth = bset

            if zenith and azimuth: # Check if Zenith and Azimuth were found
                # Get Values_List and steps (simplified flow control)
                zvallist = next((field for field in zenith if field.tag == 'Values_List'), None)
                avallist = next((field for field in azimuth if field.tag == 'Values_List'), None)
                
                # NOTE: Simplified reading of colstep/rowstep could be here if XML structure requires it

                if zvallist and avallist:
                    for rindex in range(len(zvallist)):
                        zvalrow = zvallist[rindex]
                        avalrow = avallist[rindex]
                        zvalues = zvalrow.text.split(' ')
                        avalues = avalrow.text.split(' ')
                        values = list(zip(zvalues, avalues))
                        
                        for cindex in range(len(values)):
                            if ( values[cindex][0] != 'NaN' and values[cindex][1] != 'NaN'):
                                zen = float(values[cindex][0])
                                az = float(values[cindex][1])
                                solar_zenith_values[rindex,cindex] = zen
                                solar_azimuth_values[rindex,cindex] = az

    # --- FINAL RESIZING LOGIC (Uses target_size for robustness) ---
    final_shape = target_size if target_size is not None else (22, 22)
        
    # CRITICAL FIX: Using skimage.resize to perform high-factor upscaling safely
    solar_zenith_values = resize(solar_zenith_values, final_shape, preserve_range=True) 
    solar_azimuth_values = resize(solar_azimuth_values, final_shape, preserve_range=True)
    
    return (solar_zenith_values, solar_azimuth_values,colstep,rowstep)

# extract sensor view and azimuth angles from xml file saved in Sentinel-2 SAFE data
def extract_sensor_angles(xml, target_size=None):
    """Extract Sentinel-2 view (sensor) angle bands values from MTD_TL.xml and resize to target_size."""
    
    numband = 13
    
    # --- FIX 1: Initialize all variables in function's local scope ---
    sensor_zenith_values = numpy.empty((numband,23,23)) * numpy.nan 
    sensor_azimuth_values = numpy.empty((numband,23,23)) * numpy.nan
    colstep = 0.0 # Initializing scalars
    rowstep = 0.0 # Initializing scalars

    # Parse the XML file
    tree = ET.parse(xml)
    root = tree.getroot()

    # Find the angles
    for child in root:
        if child.tag[-14:] == 'Geometric_Info':
            geoinfo = child

    for segment in geoinfo:
        if segment.tag == 'Tile_Angles':
            angles = segment

    for angle in angles:
        if angle.tag == 'Viewing_Incidence_Angles_Grids':
            bandId = int(angle.attrib['bandId'])
            
            # FIX 2: Initialize local variables for inner blocks
            zenith = None 
            azimuth = None
            
            for bset in angle:
                if bset.tag == 'Zenith':
                    zenith = bset
                if bset.tag == 'Azimuth':
                    azimuth = bset
            
            # Get step sizes (which are siblings to Zenith/Azimuth blocks in the XML)
            for field in angle:
                if field.tag == 'COL_STEP':
                    colstep= float(field.text)
                if field.tag == 'ROW_STEP':
                    rowstep= float(field.text) 
                    
            if zenith and azimuth:
                zvallist = next((field for field in zenith if field.tag == 'Values_List'), None)
                avallist = next((field for field in azimuth if field.tag == 'Values_List'), None)
            
                if zvallist and avallist:
                    for rindex in range(len(zvallist)):
                        zvalrow = zvallist[rindex]
                        avalrow = avallist[rindex]
                        zvalues = zvalrow.text.split(' ')
                        avalues = avalrow.text.split(' ')
                        values = list(zip(zvalues, avalues ))
                        
                        for cindex in range(len(values)):
                            if (values[cindex][0] != 'NaN' and values[cindex][1] != 'NaN'):
                                zen = float(values[cindex][0])
                                az = float(values[cindex][1])
                                sensor_zenith_values[bandId, rindex,cindex] = zen
                                sensor_azimuth_values[bandId, rindex,cindex] = az

    # --- Final Resizing Logic (Robustly handles target_size) ---
    final_shape = target_size if target_size is not None else (22, 22)
        
    # Apply resize using the target_size (B8A angle grid, which is index 7)
    sensor_zenith_values = resize(sensor_zenith_values[7], final_shape, preserve_range=True)
    sensor_azimuth_values = resize(sensor_azimuth_values[7], final_shape, preserve_range=True)
    
    return(sensor_zenith_values, sensor_azimuth_values,colstep,rowstep)

# NOTE: The original resample_image function is intentionally removed or disabled in the final code.

#def extract_boa_add_offset_values(xml):
#     # Parse the XML file
#     tree = ET.parse(xml)
#     root = tree.getroot()
#     # Find the angles
#     for child in root:
#         if child.tag[-12:] == 'General_Info':
#             general_info = child       
#     for segment in general_info:
#         if segment.tag == 'Product_Image_Characteristics':
#             image_characteristics = segment
#     for sub_segment in image_characteristics: 
#         if sub_segment.tag == 'BOA_ADD_OFFSET_VALUES_LIST':  
#             BOA_ADD_OFFSET={'band_%s'%(value.attrib ['band_id']):float(value.text) for value in sub_segment if value.tag[:14]=='BOA_ADD_OFFSET'} 
#     return BOA_ADD_OFFSET

# def extract_quantification_values(xml):
#     # Parse the XML file
#     tree = ET.parse(xml)
#     root = tree.getroot()
#     # Find the angles
#     for child in root:
#         if child.tag[-12:] == 'General_Info':
#             general_info = child       
#     for segment in general_info:
#         if segment.tag == 'Product_Image_Characteristics':
#             image_characteristics = segment
#     for sub_segment in image_characteristics: 
#         if sub_segment.tag == 'QUANTIFICATION_VALUES_LIST':
#             QUANTIFICATION={value.tag:float(value.text) for value in sub_segment}
#     return QUANTIFICATION