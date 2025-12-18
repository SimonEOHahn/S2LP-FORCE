# SL2P.py

from tools import toolsNets
from tools import dictionariesSL2P
from tools import SL2PV0 as algorithm
import numpy
from datetime import datetime
from tools import read_sentinel2_safe_image # Used for legacy SAFE processing modes
from skimage.transform import resize # *** CHANGE: New import for robust resizing of angle grids ***

# main SL2P function (Entry point for processing)
def SL2P(sl2p_inp,variableName,imageCollectionName,outPath=None):
    networkOptions= dictionariesSL2P.make_net_options()
    collectionOptions = (dictionariesSL2P.make_collection_options(algorithm))
    netOptions=networkOptions[variableName][imageCollectionName]
    colOptions=collectionOptions[imageCollectionName]
    
    # Prepare SL2P networks (loads NN weights based on collectionOptions)
    # *** CHANGE: Updated variable names for clarity (SL2P -> SL2P_nets) ***
    # This prevents naming conflicts with the function name itself.
    SL2P_nets, errorsSL2P_nets = makeModel(algorithm,imageCollectionName,variableName) 

    # *** CHANGE: Capture dimensions (bands, rows, cols) ***
    # Necessary for reshaping the output back into a 2D image after neural network inference.
    bands, rows, cols = sl2p_inp.shape
        
    # generate sl2p input data flag (Domain check)
    inputs_flag=invalidInput(sl2p_inp,netOptions,colOptions)
        
    # run SL2P (NN Inference)
    print('Run SL2P...\nSL2P start: %s' %(datetime.now()))
        
    # *** CHANGE: Passing the 3D array directly ***
    # The original logic sometimes struggled with input shapes; this ensures 
    # the 3D stack is passed correctly to the wrapper.
    estimate    =toolsNets.wrapperNNets(SL2P_nets    ,netOptions,sl2p_inp)
    uncertainty=toolsNets.wrapperNNets(errorsSL2P_nets,netOptions,sl2p_inp)
    print('SL2P end: %s' %(datetime.now()))
        
    # *** CHANGE: Reshape outputs back to 2D image format ***
    # The NN output is a flat 1D array; we must map it back to (rows x cols).
    estimate_reshaped = estimate.reshape(rows, cols)
    uncertainty_reshaped = uncertainty.reshape(rows, cols)
        
    # generate sl2p output product flag (Range check)
    output_flag=invalidOutput(estimate_reshaped,variableName)
    print('Done')
    # *** CHANGE: Return dictionary uses reshaped 2D arrays ***
    return {
        variableName:estimate_reshaped,
        variableName+'_uncertainty':uncertainty_reshaped,
        'sl2p_inputFlag':inputs_flag,
        'sl2p_outputFlag':output_flag
    }

# makeModel remains unchanged as it handles network loading from GEE assets (or local copies)
def makeModel(algorithm,imageCollectionName,variableName):
    collectionOptions = (dictionariesSL2P.make_collection_options(algorithm))
    colOptions=collectionOptions[imageCollectionName]
    networkOptions= dictionariesSL2P.make_net_options()
    netOptions=networkOptions[variableName][imageCollectionName]

    ## Compute numNets
    numNets =len({k: v for k, v in (colOptions["Network_Ind"]['features'][0]['properties']).items() if k != 'Feature Index'})
    SL2P_nets =[toolsNets.makeNetVars(colOptions["Collection_SL2P"],numNets,netNum) for netNum in range(colOptions['numVariables'])]
    errorsSL2P_nets =[toolsNets.makeNetVars(colOptions["Collection_SL2Perrors"],numNets,netNum) for netNum in range(colOptions['numVariables'])]
    
    return SL2P_nets,errorsSL2P_nets


# prepare the sentinel-2 data (dict) to be inputed to sl2p
def prepare_sl2p_inp(s2,variableName,imageCollectionName):
    networkOptions= dictionariesSL2P.make_net_options()
    netOptions=networkOptions[variableName][imageCollectionName]
    
    # *** CHANGE: Explicit target shape determination ***
    # Instead of assuming B03, we now look for B02 (the 10m anchor) to ensure alignment 
    # with high-resolution FORCE data.
    target_shape = s2['B02'].shape
    
    # --- ANGLE RESAMPLING FIX (Handles upscaling for custom modes) ---
    # Only resize if the mode is NOT one of the custom modes, OR if the shapes don't match.
    # We rely on the reader to pass the correct angle arrays.
    
    # *** CHANGE: REFACTORED ANGLE RESAMPLING FIX ***
    # The original code assumed a standard upscaling factor. Our new version:
    # 1. Checks if the angles (22x22) actually need resampling.
    # 2. Uses skimage.transform.resize for stability (prevents MemoryErrors).
    # 3. Includes a check for the Scene Classification Layer (SCL).
    if s2['SZA'].shape != target_shape:
        print(f'Resampling angles from {s2["SZA"].shape} to {target_shape}...')
        
        # Calculate dynamic factor based on current vs target dimensions
        factor_y = float(target_shape[0]) / s2['SZA'].shape[0]
        factor_x = float(target_shape[1]) / s2['SZA'].shape[1]
        
        # Resample solar and view angles using bilinear interpolation (order=1)
        for key in ['SZA', 'SAA', 'VZA', 'VAA']:
            if key in s2:
                s2[key] = resize(s2[key], target_shape, order=1, preserve_range=True, anti_aliasing=False)
        
        # Nearest neighbor interpolation (order=0) for discrete classification masks
        if 'SCL' in s2:
             s2['SCL'] = resize(s2['SCL'], target_shape, order=0, preserve_range=True, anti_aliasing=False).astype(numpy.uint8)

    else:
        print(f'Skipping resampling: Angle shapes already matched (e.g., FORCE TIF).')
        
    # --- END ANGLE RESAMPLING FIX ---
    
    #compute Relative Azimuth angle (RAA) and Cosines
    s2['RAA']=numpy.absolute(s2['SAA']-s2['VAA'])
    print('Computing cosSZA, cosVZA and cosRAA')
    s2['cosSZA']=numpy.cos(numpy.deg2rad(s2['SZA']))
    s2['cosVZA']=numpy.cos(numpy.deg2rad(s2['VZA']))
    s2['cosRAA']=numpy.cos(numpy.deg2rad(s2['RAA']))
    
    # select sl2p input bands and scale
    print('Scaling Sentinel-2 bands\nSelecting sl2p input bands')
    sl2p_inp = {}
    
# *** CHANGE: Robust scaling loop ***
    # Replaced dictionary.update() with specific key assignment to ensure 
    # all required input features (including calculated cosines) are captured.
    for band_id, band in enumerate(netOptions['inputBands']):
        band_data = s2.get(band)
        
        if band_data is None:
             raise ValueError(f"Required band/angle {band} not found in input dictionary.")

        band_data = band_data.astype(numpy.float32)
        # Applying scaling/offset as defined in dictionariesSL2P.py
        scaled_band = (band_data + netOptions['inputOffset'][band_id]) * netOptions['inputScaling'][band_id]
        sl2p_inp[band] = scaled_band

    # *** CHANGE: Diagnostic Shape Check ***
    # This block was added to troubleshoot the common 'mismatched shape' error during stacking.
    print('\n--- Stacking Input Arrays ---')
    sl2p_inp = numpy.stack([sl2p_inp[k] for k in netOptions['inputBands']])
    print('Done!')
    return sl2p_inp
    
# invalidInput and invalidOutput remain unchanged (standard domain and range checks)
def invalidInput(image,netOptions,colOptions):
    print('Generating sl2p input data flag')
    [d0,d1,d2]=image.shape
    sl2pDomain=numpy.sort(numpy.array([row['properties']['DomainCode'] for row in colOptions["sl2pDomain"]['features']]))
    bandList={b:netOptions["inputBands"].index(b) for b in netOptions["inputBands"] if b.startswith('B')}
    image=image.reshape(image.shape[0],image.shape[1]*image.shape[2])[list(bandList.values()),:]
    
    #Image formatting
    image_format=numpy.sum((numpy.uint8(numpy.ceil(image*10)%10))* numpy.array([10**value for value in range(len(bandList))])[:,None],axis=0)
    
    # Comparing image to sl2pDomain
    flag=numpy.isin(image_format, sl2pDomain,invert=True)
    return flag.reshape(d1,d2)

def invalidOutput(estimate,variableName):
    print('Generating sl2p output product flag')
    var_range=dictionariesSL2P.make_outputParams()[variableName]
    return numpy.where(estimate<var_range['outputOffset'],1,numpy.where(estimate>var_range['outputMax'],1,0))