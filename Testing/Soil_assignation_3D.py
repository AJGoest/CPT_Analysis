


# Soil assignation for the 3D model
from plxscripting.easy import *
import subprocess, time
import pandas as pd

# --- 1. PLAXIS INITIALIZATION ---
PLAXIS_PATH = r'C:\Program Files\Seequent\PLAXIS 3D 2025\Plaxis3DInput.exe'
PORT_i = 10000
PASSWORD = 'SxDBR<TYKRAX834~'

subprocess.Popen([PLAXIS_PATH, f'--AppServerPassword={PASSWORD}', f'--AppServerPort={PORT_i}'], shell=False)
time.sleep(5) 

s_i, g_i = new_server('localhost', PORT_i, password=PASSWORD)
s_i.new()

# Give soil contour in the case you want to the negative spectrum
g_i.SoilContour.initializerectangular(-5, 0, 15, 10) # 1st is x-min, 2nd is y-min, 3rd is x-max, 4th is y-max. Adjust according to your model size and location.

# --- 2. DATA LOADING ---


### The different directories have the different soil models.
# file = r"C:\AA_Thesis\Results\PLAXIS_runs_0.3m\Linear_elastic\S1022749_CPTU1-2\plaxis_soil_input.xlsx"
# file = r"C:\AA_Thesis\Results\PLAXIS_runs_0.3m\MC\S1022749_CPTU1-2\plaxis_soil_input.xlsx"
# file = r"C:\AA_Thesis\Results\PLAXIS_runs_0.3m\SANISAND\S1022749_CPTU1-2\plaxis_soil_input.xlsx"


file = r"C:\AA_Thesis\Results\PLAXIS_runs_0.3m\Linear_elastic\S1022749_CPTU1-2\plaxis_soil_input.xlsx"
soilsheet = "OHE Ground Profile"
df_soil = pd.read_excel(file, sheet_name=soilsheet, engine='openpyxl')

# --- 3. BOREHOLE & LAYER SKELETON ---
# Create first borehole at (x, y) from row 0 and row 1
g_i.borehole(df_soil.iloc[0,1], df_soil.iloc[1,1])
g_i.soillayer(0) 

# Set Top elevation of 1st Borehole (Now in row 2 due to Y-coord addition)
g_i.Soillayers[0].Zones[0].Top.set(df_soil.iloc[2,1]) 

# Loop through remaining borehole columns to create them
for j in range(len(df_soil.columns)-2):
    # .borehole(x, y)
    g_i.borehole(df_soil.iloc[0,j+2], df_soil.iloc[1,j+2]) 
    # Set Top elevation for other Boreholes
    g_i.Soillayers[0].Zones[j+1].Top.set(df_soil.iloc[2,j+2])

# Loop to create the required number of soil layers
# We subtract 3 now: X-row, Y-row, and Top-elevation-row
for i in range(len(df_soil)-3): 
    if i == len(df_soil)-4: 
        # Set bottom for 1st Borehole
        g_i.Soillayers[i].Zones[0].Bottom.set(df_soil.iloc[i+3,1]) 
    else:
        g_i.soillayer(0) 
        g_i.Soillayers[i].Zones[0].Bottom.set(df_soil.iloc[i+3,1])

# Loop through all Boreholes and set Bottom elevations
for j in range(len(df_soil.columns)-2):
    for i in range(len(df_soil)-3):
        g_i.Soillayers[i].Zones[j+1].Bottom.set(df_soil.iloc[i+3,j+2])

# --- 4. MATERIAL CREATION ---
soilmatsheet = "Soil Properties"
df_soilmat = pd.read_excel(file, sheet_name=soilmatsheet, engine="openpyxl")

for i in range(len(df_soilmat)):

    mat_name = (
        str(df_soilmat.iloc[i, 1]).replace(" ", "_").replace("/", "_").replace("-", "_"))

    soil_model = str(df_soilmat.iloc[i, 2]).strip()

    new_mat = g_i.soilmat()

    # Common properties for all material models
    properties = [
        "Identification", mat_name,
        "gammaUnsat", df_soilmat.iloc[i, 3],
        "gammaSat", df_soilmat.iloc[i, 3],
        "Eref", df_soilmat.iloc[i, 4],
        "nu", df_soilmat.iloc[i, 5],
        "K0Determination", 1,
        "K0Primary", 0.5
    ]

    if soil_model == "MC":
        # Mohr-Coulomb
        properties += [
            "SoilModel", 2,
            "cref", df_soilmat.iloc[i, 6],
            "phi", df_soilmat.iloc[i, 7],
            "psi", df_soilmat.iloc[i, 8]
        ]

    else:
        # Linear Elastic
        properties += [
            "SoilModel", 1
        ]

    # print(f"Soil model {soil_model} for {mat_name}")

    new_mat.setproperties(*properties)


# --- 5. MATERIAL ASSIGNMENT ---
all_materials = [m for m in g_i.Materials[:] if m.TypeName.value == 'SoilMat']

for j in range(len(df_soil) - 3):
    # Match names with Excel (skipping the 3 header rows)
    target_name = str(df_soil.iloc[j + 3, 0]).replace(" ", "_").replace("/", "_").replace("-", "_")
    
    for mat in all_materials:
        if mat.Identification == target_name:
            g_i.Soillayers[j].Soil.setmaterial(mat)
            # print(f"Assigned {target_name} to Soillayer_{j+1}")
            break