# Welcome to SL2P-FORCE


SL2P-FORCE is a python implementation of the Simplified Level 2 Product Prototype Processor (SL2P) described in [Weiss and Baret (2016)](https://step.esa.int/docs/extra/ATBD_S2ToolBox_L2B_V1.1.pdf). It corresponds to the algorithm implemented in the [LEAf-Toolbox](https://github.com/rfernand387/LEAF-Toolbox) that corrects for bugs in the implemention of SL2P within the European Space Agency Sentinel 2 Toolbox as documented in [Fernandes et al. 2023](https://www.sciencedirect.com/science/article/pii/S0034425723001517?via%3Dihub).

SL2P-FORCE is designed to estimate vegetation biophysical variables (Table 1) at 10 or 20 meters spatial resolution from Sentinel-2 FORCE Tiles. 

Required inputs
---------------
-	Sentinel 2 FORCE Tile (Single TIF with needed bands or multiple TIFs for each band)
-	The needed vegetation variable (Table 1)
-	The needed spatial resolution: 10m or 20m (depending on input and desired output)
Outputs
-------
SL2P-FORCE is designed to estimate five vegetation variables (Table 1). 

Products are composed of 4-layers and exported in GeoTIFF format (Table 2). 



<p align="center"> Table 1: Vegetation variables supported by SL2P-PYTHON </p>

|Vegetation variable	|Description	|Unit	|Nominal variation range|
|---------------------|-------------|:-----:|:-----------------------:|
|LAI	|Half the total green foliage area per horizontal ground area.	|$m^{2} / m^{2}$ |0 - 8|
|fCOVER	|Fraction of nadir canopy cover	|Ratio	|0 – 1|
|fAPAR	|Fraction of absorbed clear sky PAR at 10:30 am local time	|Ratio	|0 – 1|
|CCC	|Canopy chlorophyll A+B content	|$g / m^{2}$	|0 - 600|
|CWC	|Canopy water content	|$g / m^{2}$	|0 – 1|
|Albedo	|Black sky shortwave albedo at 10:30am local time	|Ratio	|0 – 0.2|


<p align="center"> Table 2: SL2P-PYTHON output layers (for one needed vegetation variable) </p>

|Layer                                         |	Description                                              |
|----------------------------------------------|-----------------------------------------------------------|
|Vegetation variable estimate	                 |Map of vegetation variable                                 | 
|Uncertainty of vegetation variable estimates	 |Map of the uncertainty of vegetation variable              |
|SL2P input flag (Quality Code)	               |0: Valid, 1: SL2P input out of SL2P calibration domain     |
|SL2P output flag (Quality Code)               |	0: Valid, 1: estimates out of the nominal variation range|

![image](https://github.com/djamainajib/SL2P-PYTHON/assets/33295871/2c42dc0b-2256-4147-860c-48eac8c04813)

<p align="center"> Figure 1: SL2P-PYTHON principles </p>


For more details about the original SL2P-PYTHON please see [ATBD document](https://github.com/djamainajib/SL2P_python/blob/main/GEOMATICS%20CANADA%20xx%20-%20SL2P%20PYTHON_version_0.docx).


Dependencies:
------------
- rasterio 1.3.9
- matplotlib 3.7.2
- datetime 5.4
- skimage 0.20.0
- tqdm 4.65.0
- scipy 1.11.1
- pickle 0.0.12

How to contribute?
------------
See [CONTRIBUTING.md](https://github.com/djamainajib/SL2P_python/blob/main/CONTRIBUTING.md)


License:
------------
Unless otherwise noted, the source code of this project is covered under Crown Copyright, Government of Canada, and is distributed under the [MIT License](https://github.com/djamainajib/SL2P_python/blob/main/License).

The Canada wordmark and related graphics associated with this distribution are protected under trademark law and copyright law. No permission is granted to use them outside the parameters of the Government of Canada's corporate identity program. For more information, see [Federal identity requirements](https://www.canada.ca/en/treasury-board-secretariat/topics/government-communications/federal-identity-requirements.html).


