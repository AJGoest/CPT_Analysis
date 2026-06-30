

# PLAXIS 3D python script running

from plxscripting.easy import *
import subprocess, time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import xlsxwriter
import openpyxl
import os

# interpreter path 
#C:\ProgramData\Seequent\PLAXIS Python Distribution V3\python

PLAXIS_PATH = r'C:\Program Files\Seequent\PLAXIS 3D 2025\Plaxis3DInput.exe'  # Specify PLAXIS path on server.

PORT_i = 10000  # Define a port number.
PORT_o = 10001

PASSWORD = 'SxDBR<TYKRAX834~'  # Define a password (up to user choice).

subprocess.Popen([PLAXIS_PATH, f'--AppServerPassword={PASSWORD}', f'--AppServerPort={PORT_i}'], shell=False)  # Start the PLAXIS remote scripting service.

time.sleep(5)  # Wait for PLAXIS to boot before sending commands to the scripting service.

# Start the scripting server.

s_i, g_i = new_server('localhost', PORT_i, password=PASSWORD)
s_i.new()            # creating a brand new project

# End of the boilerplate code

# Domain dimensions
D1, D2, D3 = 2, 5, 10  # Mesh zone distance from borehole
D = 30 # [-] Domain size factor (external boundary in relation to R probably)
H = 10 # [m] Layer height
R = 0.25 # [m] Radius

# in situ stresses
z = 10 # [m] Vertical depth
gamma_s = 20 # [kN/m3] Saturated unit weight of soil
gamma_w = 10 # [kN/m3] Hydraulic gradient
K0 = 0.5 # [-] Coefficient of lateral earth pressure
sigv = z*(gamma_s-gamma_w) # [kPa] Effective in-situ vertical stress
sigh = K0*sigv # [kPa] Effective in-situ horizontal stress

# Soil Properties
gamma_unsat = gamma_s - gamma_w  # [kN/m3]. Model is fully running in effective stresses
K0_val = 0.5       # [-] e.g., 0.5 Coefficient of lateral earth pressure

#Elastic parameters
E_prime = 13E3      # [kN/m2] Young's Modulus
nu_prime = 0.3     # [-] Poisson's Ratio (dependent on soil type)

# Mohr-Coulomb parameters
phi = 35 # [deg] friction angle
M = 6*np.sin(phi/180*np.pi)/(3-np.sin(phi/180*np.pi))
psi = 10 # [deg] dilation angle

# SANISAND parameters
G0 = 105.00
nu =  0.27
Mc = 1.34
c = 0.70
e0 = 0.82
lambc = 0.01
xi = 0.73
A0 =  1.1 #0.9852774345126578
nb =  4.3
nd =  8 #4.271626389933624

m = 0.01
h0 = 15
ch = 1.1

eini = 0.7

# Load steps (from 100% to 0% to simulate excavation/unloading)
lf = np.arange(1, -0.1, -0.1) 

# --- INITIALIZATION ---
s_i.new()
g_i.setproperties("ModelType", "Full")

# --- MATERIAL DEFINITION ---
sand_material = g_i.soilmat(
    "Identification", "Sand_Layer",
    "SoilModel", "Linear Elastic",
    "DrainageType", "Drained",
    "gammaUnsat", gamma_unsat,
    "gammaSat", gamma_s,
    "ERef", E_prime,
    "nu", nu_prime,
    "K0Determination", "Manual",
    "K0Primary", K0_val
)

# g_i.soilmat("Identification", "MohrC", "SoilModel", "Mohr-Coulomb", \
#             "DrainageType", "Non-porous", \
#             "gammaUnsat", gamma_s - gamma_w, \
#             "nInit", n0, \
#             "ERef", E, \
#             "nu", nu, \
#             "phi", phi, \
#             "psi", psi, \
#             "K0Determination", "Manual", \
#             "K0Primary", K0 )

# g_i.soilmat("Identification", "SANISAND", "SoilModel", "User-defined", \
#             "DllFile", "sanisandms64.dll", \
#             "ModelInDll", "sanisandms", \
#             "DrainageType", "Non-porous", \
#             "gammaUnsat", gamma_s - gamma_w, \
#             "eInit", eini, \
#             "EoedInter", 100E03, \
#             "CInter", 0.001, \
#             "PhiInter", phi, \
#             "PsiInter", psi, \
#             "User1", G0, \
#             "User2", nu,\
#             "User3", Mc, \
#             "User4", c, \
#             "User5", lambc, \
#             "User6", e0, \
#             "User7", xi, \
#             "User8", m, \
#             "User9", h0, \
#             "User10", ch, \
#             "User11", nb, \
#             "User12", A0, \
#             "User13", nd, \
#             "User14", 260, \
#             "User15", 0.0005, \
#             "User16", 1, \
#             "User17", eini, \
#             "User18", 1, \
#             "User19", 0.6, \
#             "User20", 0, \
#             "User21", 0 )

# --- STRUCTURES MODE ---
g_i.gotostructures()

# Create the 4 concentric radial zones (from center to boundary)
# Zone 1 (Inner): The circle at the center
g_i.polycurve((R, 0, 0), (1, 0, 0), (0, 1, 0), "Arc", 90, 90, R, "Line", 90, R, "Line", 90, R)
g_i.surface(g_i.Polycurve_1)
g_i.delete(g_i.Polycurve_1)
g_i.extrude(g_i.Surface_1, (0, 0, -H))
g_i.delete(g_i.Surface_1)
g_i.soil_1.setmaterial(sand_material)

# Zone 2: First refinement ring (the volumes are squared around the borehole)
g_i.polycurve((R, 0, 0), (1, 0, 0), (0, 1, 0), "Arc", 90, 90, R, "Line", 270, D1, "Line", 270, D1+R, "Line", 270, D1+R, "Line", 270, D1)
g_i.surface(g_i.Polycurve_1)
g_i.delete(g_i.Polycurve_1)
g_i.extrude(g_i.Surface_1, (0, 0, -H))
g_i.delete(g_i.Surface_1)
g_i.soil_2.setmaterial(sand_material)

# # Zone 3: Second refinement ring
g_i.polycurve((D1+R, 0, 0), (1, 0, 0), (0, 1, 0), "Line", 0, D2, "Line", 90, D1+D2+R, "Line", 90, D1+D2+R, "Line", 90, D2, "Line", 90, D1+R, "Line", 270, D1+R)
g_i.surface(g_i.Polycurve_1)
g_i.delete(g_i.Polycurve_1)
g_i.extrude(g_i.Surface_1, (0, 0, -H))
g_i.delete(g_i.Surface_1)
g_i.soil_3.setmaterial(sand_material)

# # Zone 4 (Outer): The main soil body to the boundary
g_i.polycurve((D1+D2+R, 0, 0), (1, 0, 0), (0, 1, 0), "Line", 0, D3, "Line", 90, D1+D2+D3+R, "Line", 90, D1+D2+D3+R, "Line", 90, D3, "Line", 90, D1+D2+R, "Line", 270, D1+D2+R)
g_i.surface(g_i.Polycurve_1)
g_i.delete(g_i.Polycurve_1)
g_i.extrude(g_i.Surface_1, (0, 0, -H))
g_i.delete(g_i.Surface_1)
g_i.soil_4.setmaterial(sand_material)

# code so that you can interact with the borehole surface as well, for applying the overpressure load
g_i.decomposesrf(g_i.Volume_1)
g_i.decomposesrf(g_i.Volume_2)
g_i.decomposesrf(g_i.Volume_3)
g_i.decomposesrf(g_i.Volume_4)

# add this if you want to apply borehole overpressure
# Apply borehole overpressure
BH = g_i.Surface_Volume_1_2 # calling the surface wall (4_1 is the top face, 4_3 is the bottom)
BHload = g_i.surfload((BH), "Distribution", "Perpendicular, vertical increment", "sign_ref", 0, "Zref", 0, "sign_inc", K0*(gamma_s - gamma_w)) # changed to positive as it applies on the borehole walls

# BHvirtual = g_i.Surface_Volume_8_2
# BHloadvirtual = g_i.surfload((BHvirtual), "Distribution", "Perpendicular, vertical increment", "sign_ref", -K0*(gamma_s - gamma_w)*(z-H/2), "Zref", -1, "sign_inc", -K0*(gamma_s - gamma_w)*(z-H/2))
exit()
# --- MESH REFINEMENT ---
g_i.gotomesh()

# Mesh refinement, 4 areas
f1 = 0.05  # High refinement (Center)
f2 = 0.3   # Medium refinement
f3 = 1.0   # Standard
f  = 2   # Coarse (Boundary)
le =1   # Increase global element size slightly (default is often ~1.0)

g_i.Volume_1_1.CoarsenessFactor = f1
g_i.Volume_2_1.CoarsenessFactor = f2
g_i.Volume_3_1.CoarsenessFactor = f3
g_i.Volume_4_1.CoarsenessFactor = f

g_i.mesh("ElementDimension", le, "UseEnhancedRefinements", False)

# # --- STAGES ---
g_i.gotostages()

# Initial Phase (K0 Procedure)
g_i.set(g_i.InitialPhase.DeformCalcType,"K0 procedure")

g_i.Soil_1.activate(g_i.InitialPhase)
g_i.Soil_2.activate(g_i.InitialPhase)
g_i.Soil_3.activate(g_i.InitialPhase)
g_i.Soil_4.activate(g_i.InitialPhase)

# Model conditions
g_i.GroundwaterFlow.deactivate(g_i.InitialPhase)
g_i.Dynamics.deactivate(g_i.InitialPhase)
g_i.Water.deactivate(g_i.InitialPhase)

# Loop to create stages for the load steps
previous_phase = g_i.InitialPhase
for i in range(len(lf)):
    # Create the phase (Phase_1, Phase_2, etc.)
    g_i.phase(g_i.phases[i])

    # 1. ACTIVATE THE OVERPRESSURE
    # Using the direct name Surfaceload_1_1 as in your guidance
    g_i.Surfaceload_1_1.activate(g_i.phases[i+1])

    # 2. DEACTIVATE THE SOIL (Borehole Excavation)
    # Using the direct name soil_1 as created in your Structures block
    g_i.soil_1.deactivate(g_i.phases[i+1])
    
    # 3. SET THE OVERPRESSURE VALUES
    # Scaling by the load factor (lf) as in your guidance
    g_i.Surfaceload_1_1.sign_ref.set(g_i.phases[i+1], 0)
    
    # Scaling the increment (the depth-dependent pressure)
    g_i.Surfaceload_1_1.sign_inc.set(g_i.phases[i+1], K0 * (gamma_s - gamma_w) * lf[i]) # positive as it is applied on the surface wall of the borehole 

    # Model conditions
    g_i.GroundwaterFlow.deactivate(g_i.phases[i+1])
    g_i.Dynamics.deactivate(g_i.phases[i+1])
    g_i.Water.deactivate(g_i.phases[i+1])

    # SET BOUNDARY CONDITIONS (Standard for 3D boxes)
    g_i.Deformations.BoundaryXMin.set(g_i.phases[i+1], "Normally fixed")
    g_i.Deformations.BoundaryXMax.set(g_i.phases[i+1], "Normally fixed")
    g_i.Deformations.BoundaryYMin.set(g_i.phases[i+1], "Normally fixed")
    g_i.Deformations.BoundaryYMax.set(g_i.phases[i+1], "Normally fixed")
    g_i.Deformations.BoundaryZMin.set(g_i.phases[i+1], "Normally fixed")
    g_i.Deformations.BoundaryZMax.set(g_i.phases[i+1], "Normally fixed")


g_i.calculate()

output_file = './ResultsLinearSimpleRun/ResultsLinearSimpleRun_LinearElastic.xlsx'

output_port = g_i.view(g_i.InitialPhase)
s_o, g_o = new_server('localhost', port=output_port, password=PASSWORD)



# exit()


x,y,z = [R*0.5*np.sqrt(2),R*0.5*np.sqrt(2),-(H/2+1)] # distance is indeed calculated from borehole wall
#x,y,z = [R,0,-(H/2+1)]

coords = np.zeros((19,3))
j = 0
for i in np.arange(1,10.5,0.5):
    coords[j,:] = [i*x,i*y,z]
    j += 1

nPhases = len(g_o.Phases)

for i in range(0,nPhases):
    column_names = ['x', 'y', 'z', 'sigx','sigy','sigz','sigxy','sigyz','sigzx','sig1','sig2','sig3','e','epsx','epsy','epsz','epsxy','epsyz','epszx']
    # Create an empty DataFrame with the specified column names and NaN values
    df = pd.DataFrame(np.full((len(coords), len(column_names)), np.nan, dtype=float),columns=column_names)
    

    for j in range(len(coords)): 
        x,y,z = coords[j,:]

        sigx = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.SigxxE, (x,y,z))
        sigy = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.SigyyE, (x,y,z))
        sigz = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.SigzzE, (x,y,z))
        sigxy = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.Sigxy, (x,y,z))
        sigyz = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.Sigyz, (x,y,z))
        sigzx = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.Sigzx, (x,y,z))
        sig1 = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.SigmaEffective1, (x,y,z))
        sig2 = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.SigmaEffective2, (x,y,z))
        sig3 = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.SigmaEffective3, (x,y,z))

        # ------ No result in the case of i = 0
        if i == 0: 
            e = np.nan
            epsx = np.nan
            epsy = np.nan
            epsz = np.nan
            epsxy = np.nan
            epsyz = np.nan
            epszx = np.nan
        
        else:
            e = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.VoidRatio, (x,y,z))
            epsx = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.Epsxx, (x,y,z))
            epsy = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.Epsyy, (x,y,z))
            epsz = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.Epszz, (x,y,z))
            epsxy = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.Gamxy, (x,y,z))
            epsyz = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.Gamyz, (x,y,z))
            epszx = g_o.getsingleresult(g_o.Phases[i], g_o.ResultTypes.Soil.Gamzx, (x,y,z))
    
        df.iloc[j] = [x, y, z, sigx, sigy, sigz, sigxy, sigyz, sigzx, sig1, sig2, sig3, e, epsx, epsy, epsz, epsxy, epsyz, epszx]

    if i == 0:
    # First phase → create new file
        with pd.ExcelWriter(output_file, mode='w', engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=f'phase{i}', index=False)
    else:
    # Subsequent phases → append & replace sheet if needed
        with pd.ExcelWriter(output_file, mode='a', engine='openpyxl', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name=f'phase{i}', index=False)

