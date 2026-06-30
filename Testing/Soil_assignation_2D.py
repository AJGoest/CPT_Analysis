

# https://www.viktor.ai/blog/95/automate-soil-profiles-in-plaxis-using-python
# https://lms.seequentlearning.com/enrollments/319465776/page/1194800658

from plxscripting.easy import *
import subprocess, time
import pandas as pd

# --- 2. PLAXIS INITIALIZATION ---
PLAXIS_PATH = r"C:\Program Files\Bentley\Geotechnical\PLAXIS 2D CONNECT Edition V21\Plaxis2DXInput.exe"
PORT_i = 10000
PASSWORD = 'SxDBR<TYKRAX834~'

subprocess.Popen([PLAXIS_PATH, f'--AppServerPassword={PASSWORD}', f'--AppServerPort={PORT_i}'], shell=False)
time.sleep(5) 

s_i, g_i = new_server('localhost', PORT_i, password=PASSWORD)
s_i.new()

# give contour of your PLAXIS model if it goes to negative coordinates!
#g_i.SoilContour.initializerectangular(-15, -10, 15, 10)  # give the size of your soil block

# Start reading the excel file

file = r"C:\AA_Thesis\VSCode\Testing\Soil_input.xlsx"
soilsheet = "OHE Ground Profile"

# Soil
df_soil = pd.read_excel(file, sheet_name=soilsheet, engine='openpyxl')

# create first borehole
g_i.borehole(df_soil.iloc[0,1]) # create borehole at x coord 
g_i.soillayer(0) # Create first layer in 1st borehole

# soillayers[0] stands for the frist soil layer 1 would be the next
# zones[0] stands for the 1st borehole
# Top.set sets the top y coordinate of the layer
g_i.Soillayers[0].Zones[0].Top.set(df_soil.iloc[1,1]) # Set top y coord of 1st Bh

#loop through borehole columns and create boreholes
for j in range(len(df_soil.columns)-2):
    g_i.borehole(df_soil.iloc[0,j+2]) # skip first 2 columns
    g_i.Soillayers[0].Zones[j+1].Top.set(df_soil.iloc[1,j+2]) #Top y coord for other Bhs


# loop through soil layers and set bottom y coord
for i in range(len(df_soil)-2): # Loop through the number of layers
    if i == len(df_soil)-3: # Don't create new layer if we are at last unit
        g_i.Soillayers[i].Zones[0].Bottom.set(df_soil.iloc[i+2,1]) #Set bottom y coord for 1st Bh
    else:
        g_i.soillayer(1) #Create new layer if we aren't at last unit
        g_i.Soillayers[i].Zones[0].Bottom.set(df_soil.iloc[i+2,1])

# loop through rest of boreholes and set bottom y coord
for j in range(len(df_soil.columns)-2):
    for i in range(len(df_soil)-2):
        g_i.Soillayers[i].Zones[j+1].Bottom.set(df_soil.iloc[i+2,j+2]) #Set bottom y coord for other Bhs

# -------- testing below

# --- 1. Create and apply soil properties ---
soilmatsheet = "Soil Properties"
df_soilmat = pd.read_excel(file, sheet_name=soilmatsheet, engine="openpyxl")

for i in range(len(df_soilmat)):
    name = df_soilmat.iloc[i, 1].replace(" ", "_").replace("/", "_").replace("-", "_") # Clean material name for PLAXIS
    if df_soilmat.iloc[i, 2] == 'MC':
        materialmodel = 2 

    gammaUnsat = df_soilmat.iloc[i, 3]
    gammaSat = df_soilmat.iloc[i, 3]
    Eref = df_soilmat.iloc[i, 4]
    nu = df_soilmat.iloc[i, 5]
    cref = df_soilmat.iloc[i, 6]
    phi = df_soilmat.iloc[i, 7]
    TensileStrength = df_soilmat.iloc[i, 8]
    K0Primary = 0.5 # Default
    K0Determination = "Manual"

    material1 = g_i.soilmat() # this loop everytime creates soilmat_1 in command line 

    material1.setproperties(
        "MaterialName", name,
        "SoilModel", materialmodel,
        "gammaUnsat", gammaUnsat,
        "gammaSat", gammaSat,
        "Eref", Eref,
        "nu", nu,
        "K0Determination", K0Determination,
        "K0Primary", K0Primary
    )


# Assigning correct soil material to the soil layer
# 1. Get a fresh list of all soil materials currently in PLAXIS
all_materials = [mat for mat in g_i.Materials[:] if mat.TypeName.value == 'SoilMat']

# 2. Loop through the number of layers defined in your soil profile
for j in range(len(df_soil) - 2):
    # Get the material name from the first column of your Excel sheet
    # We apply the same cleaning (underscores) used when creating the materials
    target_material_name = str(df_soil.iloc[j + 2, 0]).replace(" ", "_").replace("/", "_").replace("-", "_")
    
    # Find the material object in PLAXIS that matches this name
    match_found = False
    for mat in all_materials:
        if mat.MaterialName == target_material_name:
            # It sets the material for the Soil object within the Soillayer
            g_i.Soillayers[j].Soil.setmaterial(mat)
            print(f"Assigned {target_material_name} to Soillayer_{j+1}")
            match_found = True
            break
            
    if not match_found:
        print(f"Warning: Could not find a material named {target_material_name} in PLAXIS")