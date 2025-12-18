# read_sentinel2_force_image.py

import rasterio
import numpy
import os
from tools import read_sentinel2_safe_image # Accesses the original XML parser
from skimage.transform import resize # For robust upscaling/downsampling

# NOTE: read_sentinel2_safe_image must now also import 'resize' from skimage.transform

# ====================================================================
# HELPER FUNCTIONS (Band Mapping)
# ====================================================================

# *** CHANGE: Added this function to handle the multi-band TIF structure ***
def map_single_tif_bands(index):
    """Maps the 1-based index of the custom TIF (Level2_BOA) to SL2P band names."""
    if index == 1: return 'B02' 
    if index == 2: return 'B03' 
    if index == 3: return 'B04' 
    if index == 7: return 'B08' # BroadNIR (Required for 10m network)
    # The following are present but not used by the 10m network (B02, B03, B04, B08)
    if index == 4: return 'B05' 
    if index == 5: return 'B06' 
    if index == 6: return 'B07' 
    if index == 8: return 'B8A' 
    if index == 9: return 'B11' 
    if index == 10: return 'B12'
    return None

def map_force_band_name(fn):
    """Map FORCE naming convention to SL2P expected band names."""
    if 'BLU' in fn: return 'B02'
    if 'GRN' in fn: return 'B03'
    if 'RED' in fn: return 'B04'
    if 'BNR' in fn: return 'B08'
    if 'NIR' in fn: return 'B8A'
    if 'RE1' in fn: return 'B05'
    if 'RE2' in fn: return 'B06'
    if 'RE3' in fn: return 'B07'
    if 'SW1' in fn: return 'B11'
    if 'SW2' in fn: return 'B12'
    return fn.split('_')[0] 


# ====================================================================
# READER 1: SINGLE TIF + XML ANGLES (Hybrid Zero Offset Mode)
# ====================================================================

def read_single_tif_xml_angles(tif_path, safe_dir):
    """
    Reads spectral data from TIF and angles from SAFE XML, performing a simple
    pixel-based subsetting to ensure alignment. FINAL output resolution is 20m.
    """
    s2 = {}
    
    # --- 1. Get Spectral Data and Target Metadata (3000x3000, 10m) ---
    with rasterio.open(tif_path) as src:
        s2['profile'] = src.profile
        
        # Dimensions of the 10m input image
        tif_res_10m_height = src.height # 3000
        tif_res_10m_width = src.width   # 3000

        # *** CHANGE: Loop reads specific indices defined by the TIF structure ***
        for band_index in range(1, src.count + 1):
            sl2p_name = map_single_tif_bands(band_index)
            if sl2p_name in ['B02', 'B03', 'B04', 'B08']:
                 s2[sl2p_name] = src.read(band_index)
                 
    if 'B08' not in s2:
        raise FileNotFoundError("Missing B08 band in the single TIF. Check band mapping.")


    # --- 2. Get Angular Data from the SAFE XML (Full 10980x10980 S2 Tile) ---
    # *** CHANGE: We force the XML reader to create a FULL 10m tile (10980x10980) ***
    # This ensures that our 3000x3000px subset is clipped from a high-resolution grid.
    print("Reading and upscaling full 10m angle grid from SAFE XML...")
    
    # The XML is read and resized internally to the FULL 10m tile size (10980x10980).
    full_s2_10m_size = (10980, 10980) 
    safe_data = read_sentinel2_safe_image.read_s2(safe_dir, res=10, target_size=full_s2_10m_size) 
    
    
    # --- 3. PIXEL-BASED SUBSETTING (CRITICAL: Clipping the 10980x10980 array) ---
    # *** CHANGE: Switched from Geospatial to Pixel-based offsets (0,0) ***
    # This fixed NA artifacts by assuming the subset is at the start of the tile.    
    col_offset = 0
    row_offset = 0

    # Define the 3000x3000 slice window
    clip_slice_rows = slice(row_offset, row_offset + tif_res_10m_height) # 0 to 3000
    clip_slice_cols = slice(col_offset, col_offset + tif_res_10m_width)   # 0 to 3000
    
    print(f"Applying Pixel Clip: Row={row_offset}:{row_offset + tif_res_10m_height}, Col={col_offset}:{col_offset + tif_res_10m_width}")

    # *** CHANGE: Defined the 20m target dimensions (1500x1500px) ***
    final_20m_shape = (int(tif_res_10m_height / 2), int(tif_res_10m_width / 2)) 


    # --- 4. CLIPPING AND FINAL DOWNSAMPLING (10m -> 20m) ---
    # *** CHANGE: Integrated resize() for every layer to ensure uniform 20m output ***
    # Process Angles (VZA, VAA, SZA, SAA, SCL)
    for key in ['SZA', 'SAA', 'VZA', 'VAA', 'SCL']:
        if key in safe_data:
            # 4a. Clip the full 10980x10980 angle array to the 3000x3000 subset
            clipped_array = safe_data[key][clip_slice_rows, clip_slice_cols] 
            
            # 4b. Downsample the clipped 3000x3000 array to 1500x1500 (20m)
            order = 0 if key == 'SCL' else 1
            s2[key] = resize(clipped_array, final_20m_shape, order=order, preserve_range=True, anti_aliasing=True)

    # *** CHANGE: Downsampling spectral bands to match the 20m grid ***
    # Process Spectral Bands (B02, B03, B04, B08)
    for key in ['B02', 'B03', 'B04', 'B08']:
        if key in s2:
            # Downsample the 3000x3000 band array to 1500x1500 (20m)
            s2[key] = resize(s2[key], final_20m_shape, order=1, preserve_range=True, anti_aliasing=True)

    # --- 5. Angle Filling and Final Profile Update ---
    # *** CHANGE: Fills the remaining NaNs with the mean of valid pixels ***
    # This prevents the red "NA holes" in the final LAI/fAPAR product.
    for key in ['VZA', 'VAA']:
        if key in s2:
            mean_angle = numpy.nanmean(s2[key])
            s2[key] = numpy.nan_to_num(s2[key], nan=mean_angle if not numpy.isnan(mean_angle) else 0.0)

    # *** CHANGE: Updated profile transform for 20m georeferencing ***
    # tif_transform * scale(2) doubles the pixel size in the metadata.
    s2['profile'].update({
        'width': final_20m_shape[1], 
        'height': final_20m_shape[0],
        'transform': s2['profile']['transform'] * s2['profile']['transform'].from_scale(2, 2)
    })
    
    return s2    

# ====================================================================
# READER 2: FORCE ARD TIFFS (Original FORCE Mode)
# ====================================================================

def read_s2_force(tile_dir):
    """Read FORCE S2 tile TIFFs and sun/sensor angle files."""
    s2 = {}

    # 1. Read all spectral bands
    for fn in os.listdir(tile_dir):
        if fn.endswith(".tif") and not fn.startswith(("sun_", "sensor:")):
            band_name = map_force_band_name(fn)
            path = os.path.join(tile_dir, fn)
            with rasterio.open(path) as src:
                s2[band_name] = src.read(1)
                s2['profile'] = src.profile

    # 2. Read sun and sensor angles (Angle GeoTIFFs)
    angle_files = {
        'SZA': 'sun_zenith_degrees.tif', 'SAA': 'sun_azimuth_degrees.tif',
        'VZA': 'sensor_zenith_degrees.tif', 'VAA': 'sensor_azimuth_degrees.tif'
    }
    for key, fname in angle_files.items():
        path = os.path.join(tile_dir, fname)
        if os.path.exists(path):
            with rasterio.open(path) as src:
                 s2[key] = src.read(1)
        else:
            print(f"Warning: Missing required angle file {fname} for FORCE mode.")

    # 3. Add a dummy SCL if necessary (FORCE ARD usually includes QM, but using a dummy ensures compliance)
    if 'B02' in s2 and 'SCL' not in s2:
        s2['SCL'] = numpy.zeros_like(s2['B02'], dtype=numpy.uint8) 

    return s2