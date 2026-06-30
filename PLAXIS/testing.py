# =============================================================================
# testing_structures_mesh_only.py
#
# Purpose:
#   Build the PLAXIS 3D model up to and including Structures + Mesh only.
#   The script then saves the model and stops before Stages/calculation.
#
# Use this as a direct replacement for testing.py when you want to inspect:
#   - created soil volumes;
#   - borehole volume;
#   - borehole wall surfaces;
#   - radial refinement zones;
#   - generated mesh.
#
# Important:
#   PLAXIS is intentionally NOT closed at the end, so you can inspect the model.
# =============================================================================

from plxscripting.easy import *
import subprocess
import time
import pandas as pd
import numpy as np
import os


# =============================================================================
# GLOBAL SETTINGS
# =============================================================================

PLAXIS_PATH = r"C:\Program Files\Seequent\PLAXIS 3D 2025\Plaxis3DInput.exe"
PORT_i = 10000
PASSWORD = "SxDBR<TYKRAX834~"

OUTPUT_ROOT_DIR = r"C:\Users\caupi\OneDrive - Delft University of Technology\Thesis\PLAXIS_runs\SANISAND"

# Select one input file for inspection.
INPUT_FILE = r"C:\AA_Thesis\Results\0.3m_lengkeek_output\latest_nu\CPT1-2_Linear.xlsx"

# Optional SANISAND initial void-ratio override.
# Leave as None for Linear/MC or default SANISAND value.
EINI_OVERRIDE = None
RUN_SUFFIX = None

# Borehole radius.
RADIUS = 0.45

# If True, save the model after mesh generation.
SAVE_INSPECTION_MODEL = False

# Leave PLAXIS in this mode after stopping: "Structures" or "Mesh".
INSPECTION_MODE_AFTER_STOP = "Structures"


# =============================================================================
# SMALL HELPERS
# =============================================================================

def radius_folder_name(radius):
    """Return a filesystem-safe radius folder name, e.g. 0.45 -> Radius_0p45m."""
    return f"Radius_{radius:.2f}m".replace(".", "p")


def excel_result_stem(input_file):
    """Result name: loaded Excel file name followed by PLAXIS_results."""
    return os.path.splitext(os.path.basename(input_file))[0] + "_PLAXIS_results"


def clean_name(value):
    """Clean Excel material/layer names so they match PLAXIS object names."""
    return (
        str(value)
        .strip()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
    )


def extraction_mode_from_filename(input_file):
    """
    Decide extraction mode from the input Excel filename.
    This is retained only for consistency with the main script.
    No output extraction is performed in this testing script.
    """
    filename = os.path.basename(input_file).lower()

    if "mc" in filename:
        return "last_layer_only"

    if "sanisand" in filename:
        return "last_layer_only"

    if "linear" in filename:
        return "all_layers"

    raise ValueError(
        f"Could not determine extraction mode from filename: {filename}. "
        "Expected filename to contain 'MC', 'SANISAND', or 'Linear'."
    )


def get_mesh_volume_from_structure_volume_name(g_i, structure_volume_name):
    """
    PLAXIS usually exposes a structure volume called Volume_61
    in mesh mode as Volume_61_1.
    """
    mesh_volume_name = structure_volume_name + "_1"

    try:
        return getattr(g_i, mesh_volume_name)
    except AttributeError:
        raise RuntimeError(
            f"Could not find mesh volume '{mesh_volume_name}' "
            f"for structure volume '{structure_volume_name}'. "
            "Check the volume name in PLAXIS after switching to Mesh mode."
        )


def create_surface_from_polycurve(g_i):
    """Convert Polycurve_1 to Surface_1 and delete the polycurve."""
    g_i.surface(g_i.Polycurve_1)
    g_i.delete(g_i.Polycurve_1)


def extrude_surface_to_volume(g_i, dz):
    """Extrude Surface_1 over dz and delete the source surface."""
    g_i.extrude(g_i.Surface_1, (0, 0, dz))
    g_i.delete(g_i.Surface_1)


def assign_latest_soil_material(g_i, material, volume_list, volume_name_list, soil_list=None):
    """Assign a material to the latest PLAXIS soil/volume object and store it."""
    created_soil = g_i.Soils[-1]
    created_volume = g_i.Volumes[-1]

    created_soil.setmaterial(material)

    volume_list.append(created_volume)
    volume_name_list.append(created_volume.Name.value)

    if soil_list is not None:
        soil_list.append(created_soil)

    return created_soil, created_volume


# =============================================================================
# PROJECT NAMING
# =============================================================================

radius_str = radius_folder_name(RADIUS)
radius_dir = os.path.join(OUTPUT_ROOT_DIR, radius_str)
os.makedirs(radius_dir, exist_ok=True)
output_dir = radius_dir

result_stem = excel_result_stem(INPUT_FILE)
if RUN_SUFFIX is not None:
    result_stem = f"{result_stem}_{RUN_SUFFIX}"

project_name = f"{result_stem}_{radius_str}"
inspection_project_file = os.path.join(output_dir, project_name + "_STRUCTURES_MESH_ONLY.p3d")

print("=" * 100)
print(f"STRUCTURES + MESH TEST RUN: {project_name}")
print(f"Input file:       {INPUT_FILE}")
print(f"Borehole radius:  {RADIUS:.3f} m")
print(f"Output folder:    {output_dir}")
print("=" * 100)


# =============================================================================
# START PLAXIS
# =============================================================================

print("Starting PLAXIS Input...")
plaxis_process = subprocess.Popen(
    [
        PLAXIS_PATH,
        f"--AppServerPassword={PASSWORD}",
        f"--AppServerPort={PORT_i}",
    ],
    shell=False,
)

time.sleep(10)
s_i, g_i = new_server("localhost", PORT_i, password=PASSWORD)
print("Connected to PLAXIS Input.")

s_i.new()
g_i.setproperties("ModelType", "Full")

file = INPUT_FILE
extraction_mode = extraction_mode_from_filename(file)
print(f"Extraction mode: {extraction_mode}")


# =============================================================================
# MODEL SETTINGS
# =============================================================================

soilsheet = "OHE Ground Profile"
soilmatsheet = "Soil Properties"

# Borehole and radial mesh geometry.
R = float(RADIUS)   # [m] borehole radius
D1 = 2.0            # [m] first refinement-ring thickness from borehole wall
D2 = 5.0            # [m] second refinement-ring thickness
D3 = 10.0           # [m] outer refinement-ring thickness

# Mesh coarseness factors.
f1 = 0.05           # borehole excavation volume
f2 = 0.30           # first ring
f3 = 1.00           # second ring
f4 = 2.00           # outer ring
le = 1.0            # global element dimension

# Soil/loading constants.
K0_default = 0.5
gamma_w = 10.0      # [kN/m3]


# =============================================================================
# READ EXCEL INPUT
# =============================================================================

df_soil = pd.read_excel(file, sheet_name=soilsheet, engine="openpyxl")
df_soilmat = pd.read_excel(file, sheet_name=soilmatsheet, engine="openpyxl")

# Excel layout assumed:
#   row 0 = x-coordinate
#   row 1 = y-coordinate
#   row 2 = top elevation
#   row 3 onward = layer bottoms, with layer name in column 0
x_bh = float(df_soil.iloc[0, 1])
y_bh = float(df_soil.iloc[1, 1])

z_model_top = float(df_soil.iloc[2, 1])
z_model_bottom = float(df_soil.iloc[-1, 1])

n_layers = len(df_soil) - 3
domain_size = R + D1 + D2 + D3

print("Model input")
print(f"  Borehole x       = {x_bh}")
print(f"  Borehole y       = {y_bh}")
print(f"  Top elevation    = {z_model_top}")
print(f"  Bottom elevation = {z_model_bottom}")
print(f"  Number of layers = {n_layers}")
print(f"  Horizontal extent from borehole centre = {domain_size}")


# =============================================================================
# MATERIAL CREATION
# =============================================================================

material_by_name = {}

for i in range(len(df_soilmat)):

    mat_name = clean_name(df_soilmat.iloc[i, 1])
    soil_model = str(df_soilmat.iloc[i, 2]).strip()

    new_mat = g_i.soilmat()

    if soil_model in ["Linear", "Linear Elastic", "LE"]:

        gamma_sat_layer = float(df_soilmat.iloc[i, 3])
        gamma_eff_layer = gamma_sat_layer - gamma_w

        properties = [
            "Identification", mat_name,
            "SoilModel", 1,
            "DrainageType", "Drained",
            "gammaUnsat", gamma_eff_layer,
            "gammaSat", gamma_sat_layer,
            "Eref", float(df_soilmat.iloc[i, 4]),
            "nu", float(df_soilmat.iloc[i, 5]),
            "K0Determination", 1,
            "K0Primary", K0_default,
        ]

    elif soil_model == "MC":

        gamma_sat_layer = float(df_soilmat.iloc[i, 3])
        gamma_eff_layer = gamma_sat_layer - gamma_w

        properties = [
            "Identification", mat_name,
            "SoilModel", 2,
            "DrainageType", "Drained",
            "gammaUnsat", gamma_eff_layer,
            "gammaSat", gamma_sat_layer,
            "Eref", float(df_soilmat.iloc[i, 4]),
            "nu", float(df_soilmat.iloc[i, 5]),
            "K0Determination", 1,
            "K0Primary", K0_default,
            "cref", float(df_soilmat.iloc[i, 6]),
            "phi", float(df_soilmat.iloc[i, 7]),
            "psi", float(df_soilmat.iloc[i, 8]),
        ]

    elif soil_model == "SANISAND":

        # SANISAND calibration constants.
        G0 = 90
        nu = 0.05
        Mc = 1.28
        c = 0.80
        lambc = 0.012
        e0 = 0.898
        xi = 0.7
        m = 0.01
        h0 = 5.25
        ch = 1.01
        nb = 1.2
        A0 = 0.4
        nd = 1.35
        mu0 = 44
        xi_s = 0.005
        beta = 1

        if EINI_OVERRIDE is None:
            eini = 0.6855
        else:
            eini = float(EINI_OVERRIDE)

        print(f"Using SANISAND eini = {eini:.5f} for material {mat_name}")

        emax = 0.86
        emin = 0.55
        phi = float(df_soilmat.iloc[i, 7])
        psi = float(df_soilmat.iloc[i, 8])

        gamma_sat_layer = float(df_soilmat.iloc[i, 3])
        gamma_eff_layer = gamma_sat_layer - gamma_w

        properties = [
            "Identification", mat_name,
            "SoilModel", "User-defined",
            "DllFile", "sanisandms64.dll",
            "ModelInDll", "sanisandms",
            "DrainageType", "Non-porous",
            "gammaUnsat", gamma_eff_layer,
            "eInit", eini,
            "EoedInter", float(df_soilmat.iloc[i, 4]),
            "CInter", 0.001,
            "PhiInter", phi,
            "PsiInter", psi,
            "User1", G0,
            "User2", nu,
            "User3", Mc,
            "User4", c,
            "User5", lambc,
            "User6", e0,
            "User7", xi,
            "User8", m,
            "User9", h0,
            "User10", ch,
            "User11", nb,
            "User12", A0,
            "User13", nd,
            "User14", mu0,
            "User15", xi_s,
            "User16", beta,
            "User17", eini,
            "User18", emax,
            "User19", emin,
            "User20", 0,
            "User21", 0,
        ]

    else:
        raise ValueError(
            f"Unknown soil model '{soil_model}' for material '{mat_name}'."
        )

    new_mat.setproperties(*properties)
    material_by_name[mat_name] = new_mat

    print(f"Created material: {mat_name} using model {soil_model}")


# =============================================================================
# STRUCTURES MODE: MANUAL VOLUME CREATION
# =============================================================================

g_i.gotostructures()

# Storage for staged excavation and inspection.
borehole_soils = []
borehole_volumes = []

# Storage for mesh refinement.
zone_1_volumes = []   # borehole excavation volume
zone_2_volumes = []   # near ring
zone_3_volumes = []   # middle ring
zone_4_volumes = []   # outer ring

zone_1_volume_names = []
zone_2_volume_names = []
zone_3_volume_names = []
zone_4_volume_names = []

# Storage for borehole wall pressure loads.
borehole_wall_surfaces = []
borehole_load_names = []
borehole_load_refs = []
borehole_load_incs = []

# Cumulative vertical effective stress at layer tops.
sigma_v_eff_top = 0.0

for layer_idx in range(n_layers):

    layer_name = clean_name(df_soil.iloc[layer_idx + 3, 0])

    if layer_name not in material_by_name:
        raise ValueError(
            f"Layer '{layer_name}' has no matching material in Soil Properties."
        )

    layer_material = material_by_name[layer_name]

    if layer_idx == 0:
        z_top = float(df_soil.iloc[2, 1])
    else:
        z_top = float(df_soil.iloc[layer_idx + 2, 1])

    z_bottom = float(df_soil.iloc[layer_idx + 3, 1])
    dz = z_bottom - z_top
    layer_thickness = abs(dz)

    if dz >= 0:
        raise ValueError(
            f"Layer {layer_idx + 1} has non-negative dz={dz}. "
            "Check top/bottom elevations."
        )

    print(
        f"Creating layer {layer_idx + 1}: {layer_name}, "
        f"z_top={z_top}, z_bottom={z_bottom}, dz={dz}"
    )

    # -------------------------------------------------------------------------
    # ZONE 1: Borehole excavation volume
    # -------------------------------------------------------------------------
    g_i.polycurve(
        (x_bh + R, y_bh, z_top),
        (1, 0, 0),
        (0, 1, 0),
        "Arc", 90, 90, R,
        "Line", 90, R,
        "Line", 90, R,
    )

    create_surface_from_polycurve(g_i)
    extrude_surface_to_volume(g_i, dz)

    zone_1_soil, zone_1_volume = assign_latest_soil_material(
        g_i,
        layer_material,
        zone_1_volumes,
        zone_1_volume_names,
        borehole_soils,
    )

    borehole_volumes.append(zone_1_volume)

    # Decompose this volume so the borehole wall can be selected for pressure loading.
    g_i.decomposesrf(zone_1_volume)

    wall_surface_name = "Surface_" + zone_1_volume.Name.value + "_2"

    print(
        f"Layer {layer_idx + 1:02d}: "
        f"borehole volume = {zone_1_volume.Name.value}, "
        f"wall surface = {wall_surface_name}"
    )

    try:
        wall_surface = getattr(g_i, wall_surface_name)
    except AttributeError:
        raise RuntimeError(
            f"Could not find borehole wall surface '{wall_surface_name}'. "
            "Check decomposed surface numbering in PLAXIS."
        )

    borehole_wall_surfaces.append(wall_surface)

    gamma_layer = float(df_soilmat.loc[
        df_soilmat.iloc[:, 1].apply(clean_name) == layer_name,
        df_soilmat.columns[3]
    ].iloc[0])

    gamma_eff_layer = gamma_layer - gamma_w

    sigma_h_eff_top = sigma_v_eff_top * K0_default
    sigma_h_eff_gradient = K0_default * gamma_eff_layer

    BHload = g_i.surfload(
        wall_surface,
        "Distribution", "Perpendicular, vertical increment",
        "sign_ref", sigma_h_eff_top,
        "Zref", z_top,
        "sign_inc", sigma_h_eff_gradient,
    )

    borehole_load_names.append(BHload.Name.value)
    borehole_load_refs.append(sigma_h_eff_top)
    borehole_load_incs.append(sigma_h_eff_gradient)

    # Update cumulative vertical effective stress AFTER this layer.
    sigma_v_eff_top += gamma_eff_layer * layer_thickness

    # -------------------------------------------------------------------------
    # ZONE 2: First refinement ring, R to R + D1
    # -------------------------------------------------------------------------
    g_i.polycurve(
        (x_bh + R, y_bh, z_top),
        (1, 0, 0),
        (0, 1, 0),
        "Arc", 90, 90, R,
        "Line", 270, D1,
        "Line", 270, D1 + R,
        "Line", 270, D1 + R,
        "Line", 270, D1,
    )

    create_surface_from_polycurve(g_i)
    extrude_surface_to_volume(g_i, dz)

    zone_2_soil, zone_2_volume = assign_latest_soil_material(
        g_i,
        layer_material,
        zone_2_volumes,
        zone_2_volume_names,
    )

    # -------------------------------------------------------------------------
    # ZONE 3: Second refinement ring, R + D1 to R + D1 + D2
    # -------------------------------------------------------------------------
    g_i.polycurve(
        (x_bh + D1 + R, y_bh, z_top),
        (1, 0, 0),
        (0, 1, 0),
        "Line", 0, D2,
        "Line", 90, D1 + D2 + R,
        "Line", 90, D1 + D2 + R,
        "Line", 90, D2,
        "Line", 90, D1 + R,
        "Line", 270, D1 + R,
    )

    create_surface_from_polycurve(g_i)
    extrude_surface_to_volume(g_i, dz)

    zone_3_soil, zone_3_volume = assign_latest_soil_material(
        g_i,
        layer_material,
        zone_3_volumes,
        zone_3_volume_names,
    )

    # -------------------------------------------------------------------------
    # ZONE 4: Outer refinement ring, R + D1 + D2 to R + D1 + D2 + D3
    # -------------------------------------------------------------------------
    g_i.polycurve(
        (x_bh + D1 + D2 + R, y_bh, z_top),
        (1, 0, 0),
        (0, 1, 0),
        "Line", 0, D3,
        "Line", 90, D1 + D2 + D3 + R,
        "Line", 90, D1 + D2 + D3 + R,
        "Line", 90, D3,
        "Line", 90, D1 + D2 + R,
        "Line", 270, D1 + D2 + R,
    )

    create_surface_from_polycurve(g_i)
    extrude_surface_to_volume(g_i, dz)

    zone_4_soil, zone_4_volume = assign_latest_soil_material(
        g_i,
        layer_material,
        zone_4_volumes,
        zone_4_volume_names,
    )


print("Finished manual Structures geometry.")
print(f"  Zone 1 volumes: {len(zone_1_volumes)}")
print(f"  Zone 2 volumes: {len(zone_2_volumes)}")
print(f"  Zone 3 volumes: {len(zone_3_volumes)}")
print(f"  Zone 4 volumes: {len(zone_4_volumes)}")

print("\nBorehole wall load creation check:")
print(f"  n_layers:              {n_layers}")
print(f"  borehole_load_names:   {len(borehole_load_names)}")
print(f"  borehole_load_refs:    {len(borehole_load_refs)}")
print(f"  borehole_load_incs:    {len(borehole_load_incs)}")
print(f"  wall surfaces:         {len(borehole_wall_surfaces)}")

if not (
    len(borehole_load_names) == n_layers and
    len(borehole_load_refs) == n_layers and
    len(borehole_load_incs) == n_layers and
    len(borehole_wall_surfaces) == n_layers
):
    raise RuntimeError(
        "Mismatch in borehole wall load creation: "
        f"n_layers={n_layers}, "
        f"loads={len(borehole_load_names)}, "
        f"refs={len(borehole_load_refs)}, "
        f"incs={len(borehole_load_incs)}, "
        f"surfaces={len(borehole_wall_surfaces)}"
    )

print("\nBase borehole wall pressures per layer:")
for i in range(n_layers):
    print(
        f"  Layer {i + 1:02d}: "
        f"load={borehole_load_names[i]}, "
        f"sign_ref={borehole_load_refs[i]:10.3f}, "
        f"sign_inc={borehole_load_incs[i]:10.3f}"
    )


# =============================================================================
# MESH MODE: RADIAL REFINEMENT + MESH GENERATION
# =============================================================================

g_i.gotomesh()

# Zone 1: borehole excavation volumes.
for name in zone_1_volume_names:
    mesh_vol = get_mesh_volume_from_structure_volume_name(g_i, name)
    mesh_vol.CoarsenessFactor = f1
    print(f"Mesh refinement: {name}_1 -> f1 = {f1}")

# Zone 2: near-borehole ring.
for name in zone_2_volume_names:
    mesh_vol = get_mesh_volume_from_structure_volume_name(g_i, name)
    mesh_vol.CoarsenessFactor = f2
    print(f"Mesh refinement: {name}_1 -> f2 = {f2}")

# Zone 3: middle ring.
for name in zone_3_volume_names:
    mesh_vol = get_mesh_volume_from_structure_volume_name(g_i, name)
    mesh_vol.CoarsenessFactor = f3
    print(f"Mesh refinement: {name}_1 -> f3 = {f3}")

# Zone 4: outer ring.
for name in zone_4_volume_names:
    mesh_vol = get_mesh_volume_from_structure_volume_name(g_i, name)
    mesh_vol.CoarsenessFactor = f4
    print(f"Mesh refinement: {name}_1 -> f4 = {f4}")

print("Generating mesh...")
g_i.mesh(
    "ElementDimension", le,
    "UseEnhancedRefinements", False,
)
print("Mesh generated.")


# =============================================================================
# STOP HERE FOR INSPECTION
# =============================================================================

if SAVE_INSPECTION_MODEL:
    print(f"Saving inspection model to: {inspection_project_file}")
    g_i.save(inspection_project_file)

if INSPECTION_MODE_AFTER_STOP.lower() == "structures":
    g_i.gotostructures()
    print("PLAXIS is left in Structures mode for inspection.")
elif INSPECTION_MODE_AFTER_STOP.lower() == "mesh":
    g_i.gotomesh()
    print("PLAXIS is left in Mesh mode for inspection.")
else:
    print(
        f"Unknown INSPECTION_MODE_AFTER_STOP = {INSPECTION_MODE_AFTER_STOP}. "
        "PLAXIS remains in its current mode."
    )

print("=" * 100)
print("TEST COMPLETE: Structures and Mesh have been created.")
print("The script stops here. No stages are created, no calculation is run, and PLAXIS is not closed.")
print("Inspect the model manually in PLAXIS.")
print("=" * 100)

raise SystemExit("Stopped after Structures + Mesh for inspection.")
