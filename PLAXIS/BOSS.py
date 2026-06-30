# =============================================================================
# Run_3D_batch.py
#
# Batch runner for multiple CPT Excel inputs.
#
# Workflow per CPT:
#   1. Start a fresh PLAXIS Input process
#   2. Build the model from that CPT's plaxis_soil_input.xlsx
#   3. Save the PLAXIS project before calculation
#   4. Calculate
#   5. Save the calculated PLAXIS project
#   6. Export the result workbook to the shared output folder
#   7. Save PLAXIS project in the shared output folder
#   8. Close PLAXIS before starting the next CPT/radius
# =============================================================================

from plxscripting.easy import *
import subprocess
import time
import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime


# =============================================================================
# GLOBAL SETTINGS
# =============================================================================

PLAXIS_PATH = r"C:\Program Files\Seequent\PLAXIS 3D 2025\Plaxis3DInput.exe"
PORT_i = 10000
PASSWORD = "SxDBR<TYKRAX834~"

# Folder that contains the four CPT input folders.
# The script will look for: <INPUT_BASE_DIR>\*\plaxis_soil_input.xlsx
INPUT_BASE_DIR = r"C:\AA_Thesis\Results\First_sand_layer_tests"
MAX_RUNS = 4

# Shared output root for all CPTs and all radius batches.
# The script will create one subfolder per borehole radius, and inside that one
# subfolder per CPT to avoid filename collisions between equally named Excel files.
OUTPUT_ROOT_DIR = r"C:\Users\caupi\OneDrive - Delft University of Technology\Thesis\PLAXIS_runs\SANISAND"

# Borehole radii to run. One batch of all CPT files is run for every radius here.
# Example: [0.25] runs one batch. [0.20, 0.25, 0.30] runs three batches.
BOREHOLE_RADII = [0.45]

# To use explicit files instead of automatic discovery, set USE_EXPLICIT_INPUT_FILES = True
# and fill CPT_INPUT_FILES below.
USE_EXPLICIT_INPUT_FILES = True


# Remember that it must contain Linear, MC or SANISAND in filename. If latter two then only last layer is extracted. 
# either upload the file direction or if you want the following file and change the eini as followed for sanisand only
# {"input_file": r"C:\AA_Thesis\Results\First_sand_layer_tests\plaxis_soil_input_SANISAND.xlsx", "eini": 0.6855,"run_suffix": "eini_0p6855",}

CPT_INPUT_FILES = [
    # r"C:\AA_Thesis\Results\First_sand_layer_tests\plaxis_soil_input_sanisand.xlsx",
    {
        "input_file": r"C:\AA_Thesis\Results\First_sand_layer_tests\plaxis_soil_input_sanisand.xlsx",
        "eini": 0.6,
        "run_suffix": "eini_0p6",
    },
    {
        "input_file": r"C:\AA_Thesis\Results\First_sand_layer_tests\plaxis_soil_input_sanisand.xlsx",
        "eini": 0.55,
        "run_suffix": "eini_0p55",
    },
]

# -----------------------------------------------------------------------------------------------------------------

def radius_folder_name(radius):
    """Return a filesystem-safe radius folder name, e.g. 0.25 -> Radius_0p25m."""
    return f"Radius_{radius:.2f}m".replace(".", "p")


def excel_result_stem(input_file):
    """Result name requested: loaded Excel file name followed by PLAXIS_results."""
    return os.path.splitext(os.path.basename(input_file))[0] + "_PLAXIS_results"

def extraction_mode_from_filename(input_file):
    """
    Decide extraction mode from the input Excel filename.

    Linear files:
        extract all layers

    MC files:
        extract only the final sand layer

    SANISAND files:
        extract only the final sand layer
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
        "Expected filename to contain 'MC' or 'Linear'."
    )

# =============================================================================
# PLAXIS PROCESS MANAGEMENT
# =============================================================================

def start_plaxis():
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

    return plaxis_process, s_i, g_i


def close_plaxis(plaxis_process):
    print("Closing PLAXIS process tree...")

    # Prefer killing only the process tree belonging to this specific PLAXIS instance.
    # This is more controlled than taskkill by image name.
    try:
        subprocess.run(
            ["taskkill", "/PID", str(plaxis_process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        try:
            plaxis_process.terminate()
            plaxis_process.wait(timeout=20)
        except Exception:
            try:
                plaxis_process.kill()
            except Exception:
                pass

    time.sleep(5)
    print("PLAXIS closed.")


def get_batch_runs():
    runs = []

    if USE_EXPLICIT_INPUT_FILES:
        input_items = CPT_INPUT_FILES[:MAX_RUNS]

        for item in input_items:
            if isinstance(item, dict):
                input_file = item["input_file"]
                eini = item.get("eini", None)
                run_suffix = item.get("run_suffix", None)
            else:
                input_file = item
                eini = None
                run_suffix = None

            cpt_name = os.path.splitext(os.path.basename(input_file))[0]

            if run_suffix is not None:
                cpt_name = f"{cpt_name}_{run_suffix}"

            runs.append(
                {
                    "input_file": input_file,
                    "cpt_name": cpt_name,
                    "eini": eini,
                    "run_suffix": run_suffix,
                }
            )

    else:
        search_pattern = os.path.join(INPUT_BASE_DIR, "*.xlsx")
        input_files = sorted(glob.glob(search_pattern))[:MAX_RUNS]

        for input_file in input_files:
            cpt_name = os.path.splitext(os.path.basename(input_file))[0]

            runs.append(
                {
                    "input_file": input_file,
                    "cpt_name": cpt_name,
                    "eini": None,
                    "run_suffix": None,
                }
            )

    if not runs:
        raise RuntimeError(
            "No CPT input files found. Check INPUT_BASE_DIR or set USE_EXPLICIT_INPUT_FILES=True."
        )

    return runs


# =============================================================================
# SINGLE CPT MODEL RUN
# =============================================================================

def run_single_cpt(input_file, radius, eini_override=None, run_suffix=None):
    radius_dir = os.path.join(OUTPUT_ROOT_DIR, radius_folder_name(radius))
    os.makedirs(radius_dir, exist_ok=True)
    output_dir = radius_dir
    result_stem = excel_result_stem(input_file)

    if run_suffix is not None:
        result_stem = f"{result_stem}_{run_suffix}"
    
    project_name = f"{result_stem}_{radius_folder_name(radius)}"

    print("=" * 100)
    print(f"Starting CPT run: {project_name}")
    print(f"Input file:       {input_file}")
    print(f"Borehole radius:  {radius:.3f} m")
    print(f"Output folder:    {output_dir}")
    print("=" * 100)

    os.makedirs(output_dir, exist_ok=True)

    plaxis_process, s_i, g_i = start_plaxis()

    try:
        s_i.new()
        g_i.setproperties("ModelType", "Full")

        # Current CPT Excel input file used by the model code below.
        file = input_file
        extraction_mode = extraction_mode_from_filename(file)
        print(f"Extraction mode: {extraction_mode}")

        soilsheet = "OHE Ground Profile"
        soilmatsheet = "Soil Properties"

        # Borehole and radial mesh geometry
        R = float(radius) # [m] borehole radius
        D1 = 2.0          # [m] first refinement-ring thickness, measured from borehole wall
        D2 = 5.0          # [m] second refinement-ring thickness
        D3 = 10.0         # [m] outer refinement-ring thickness

        # Mesh coarseness factors
        f1 = 0.05         # borehole excavation volume
        f2 = 0.30         # first ring
        f3 = 1.00         # second ring
        f4 = 2.00         # outer ring
        le = 1.0          # global element dimension

        # Load steps for later staged excavation/unloading
        # 100 intervals from LF = 1.00 to LF = 0.00.
        N_UNLOADING_INTERVALS = 100
        lf = np.linspace(1.0, 0.0, N_UNLOADING_INTERVALS + 1)

        # Export only every 10th unloading step.
        # This gives LF = 1.00, 0.90, 0.80, ..., 0.00.
        EXTRACT_EVERY_N_UNLOADING_STEPS = 10

        ONLY_EXTRACT_EXTRA_PHASES = True                                        # This setting is a personal setting that you have to change.

        # Temporary manual phase extraction.
        # Use this when PLAXIS phase 101 crashes but you still want phase 100.
        # To restore normal behaviour later, set this to [] or delete this block.
        EXTRA_PHASE_INDICES_TO_EXTRACT = [92, 93, 94, 95, 96, 97, 98, 99, 100, 101]

        # Default values for simple pressure loading, if needed later
        K0_default = 0.5
        gamma_w = 10.0    # [kN/m3]


        # =============================================================================
        # 3. READ EXCEL INPUT
        # =============================================================================

        df_soil = pd.read_excel(file, sheet_name=soilsheet, engine="openpyxl")
        df_soilmat = pd.read_excel(file, sheet_name=soilmatsheet, engine="openpyxl")


        def clean_name(value):
            return (
                str(value)
                .strip()
                .replace(" ", "_")
                .replace("/", "_")
                .replace("-", "_")
            )


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
        # 4. MATERIAL CREATION ONLY
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

                # Fill these constants from your calibration/input section.
                # This one is based on Ottawa sand tested by Chong & Santamarina (2016). D50=0.35

                # Elasticity
                G0 = 90
                nu = 0.05
                # Critical state 
                Mc = 1.28
                c = 0.80
                lambc = 0.012
                e0 = 0.898
                xi = 0.7
                # Yield surface
                m = 0.01
                # Plastic modulus
                h0 = 5.25
                ch = 1.01
                nb = 1.2
                # Dilatancy
                A0 = 0.4
                nd = 1.35
                # Memory surface
                mu0 = 44
                xi_s = 0.005
                beta = 1

                if eini_override is None:
                    eini = 0.6855 # void ratio initial (midway between loose and dense for the ottowa sand)
                else:
                    eini = float(eini_override)
                print(f"Using SANISAND eini = {eini:.5f} for material {mat_name}")
                emax = 0.86  # from Chong Santamarina 2016, for D50=0.35mm, emax=0.898, emin=0.55
                emin = 0.55 # from Chong Santamarina 2016, for D50=0.35mm, emax=0.898, emin=0.55
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
                    "EoedInter", float(df_soilmat.iloc[i, 4]), # value of tessel was 100E03, much deeper soil
                    "CInter", 0.001, # interface cohesion that is why it is almost 0
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
                    "User18", emax, # Tessel had 1
                    "User19", emin, # Tessel had 0.6
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
        # 5. STRUCTURES MODE: MANUAL VOLUME CREATION
        # =============================================================================

        g_i.gotostructures()

        # Storage for staged excavation
        borehole_soils = []
        borehole_volumes = []

        # Storage for mesh refinement
        zone_1_volumes = []   # borehole excavation volume
        zone_2_volumes = []   # near ring
        zone_3_volumes = []   # middle ring
        zone_4_volumes = []   # outer ring


        zone_1_volume_names = []
        zone_2_volume_names = []
        zone_3_volume_names = []
        zone_4_volume_names = []

        # Storage for optional borehole pressure loads later
        borehole_wall_surfaces = []
        borehole_load_names = []
        borehole_load_refs = []
        borehole_load_incs = []

        # Determination of sigma in the soil
        sigma_v_eff_top = 0.0

        def assign_latest_soil_material(material, volume_list, volume_name_list, soil_list=None):
            created_soil = g_i.Soils[-1]
            created_volume = g_i.Volumes[-1]

            created_soil.setmaterial(material)

            volume_list.append(created_volume)
            volume_name_list.append(created_volume.Name.value)

            if soil_list is not None:
                soil_list.append(created_soil)

            return created_soil, created_volume


        def create_surface_from_polycurve():
            """
            Converts Polycurve_1 to Surface_1 and deletes the polycurve.
            """
            g_i.surface(g_i.Polycurve_1)
            g_i.delete(g_i.Polycurve_1)


        def extrude_surface_to_volume(dz):
            """
            Extrudes Surface_1 over dz and deletes the source surface.
            """
            g_i.extrude(g_i.Surface_1, (0, 0, dz))
            g_i.delete(g_i.Surface_1)


        # -------------------------------------------------------------------------
        # Manual geometry creation:
        #   For every layer, create four volumes:
        #     zone 1 = borehole excavation
        #     zone 2 = first refinement ring
        #     zone 3 = second refinement ring
        #     zone 4 = outer ring
        # -------------------------------------------------------------------------

        for layer_idx in range(n_layers):

            # Layer name from Excel
            layer_name = clean_name(df_soil.iloc[layer_idx + 3, 0])

            if layer_name not in material_by_name:
                raise ValueError(
                    f"Layer '{layer_name}' has no matching material in Soil Properties."
                )

            layer_material = material_by_name[layer_name]

            # Top and bottom elevations
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
                    f"Check top/bottom elevations."
                )

            print(
                f"Creating layer {layer_idx + 1}: {layer_name}, "
                f"z_top={z_top}, z_bottom={z_bottom}, dz={dz}"
            )

            # =====================================================================
            # ZONE 1: Borehole excavation volume
            #
            # IMPORTANT:
            # This uses the original PLAXIS-accepted quarter-sector definition
            # from the simple model. Do not replace it with Line 270 / Line 0;
            # that caused PLAXIS to reject the surface geometry.
            # =====================================================================

            g_i.polycurve(
                (x_bh + R, y_bh, z_top),
                (1, 0, 0),
                (0, 1, 0),
                "Arc", 90, 90, R,
                "Line", 90, R,
                "Line", 90, R,
            )

            create_surface_from_polycurve()
            extrude_surface_to_volume(dz)

            zone_1_soil, zone_1_volume = assign_latest_soil_material(
                layer_material,
                zone_1_volumes,
                zone_1_volume_names,
                borehole_soils,
            )

            borehole_volumes.append(zone_1_volume)
            # Decompose this volume so the borehole wall can later be selected
            # for pressure loading if needed.
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

            # Layer-specific effective unit weight
            gamma_layer = float(df_soilmat.loc[
                df_soilmat.iloc[:, 1].apply(clean_name) == layer_name,
                df_soilmat.columns[3]
            ].iloc[0])

            # Effective unit weight from Excel
            gamma_eff_layer = gamma_layer - gamma_w

            #stress at the top of this layer
            sigma_h_eff_top = sigma_v_eff_top * K0_default

            # Stress gradient within this layer
            sigma_h_eff_gradient = K0_default * gamma_eff_layer

            # Create borehole wall support pressure
            BHload = g_i.surfload(
            wall_surface,
            "Distribution", "Perpendicular, vertical increment",
            "sign_ref", sigma_h_eff_top,
            "Zref", z_top,
            "sign_inc", sigma_h_eff_gradient
            )

            borehole_load_names.append(BHload.Name.value)
            borehole_load_refs.append(sigma_h_eff_top)
            borehole_load_incs.append(sigma_h_eff_gradient)

            # IMPORTANT: update cumulative vertical effective stress AFTER this layer
            sigma_v_eff_top += gamma_eff_layer * layer_thickness

            # =====================================================================
            # ZONE 2: First refinement ring, R to R + D1
            # =====================================================================

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

            create_surface_from_polycurve()
            extrude_surface_to_volume(dz)

            zone_2_soil, zone_2_volume = assign_latest_soil_material(
                layer_material,
                zone_2_volumes,
                zone_2_volume_names,
            )

            # =====================================================================
            # ZONE 3: Second refinement ring, R + D1 to R + D1 + D2
            # =====================================================================

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

            create_surface_from_polycurve()
            extrude_surface_to_volume(dz)

            zone_3_soil, zone_3_volume = assign_latest_soil_material(
                layer_material,
                zone_3_volumes,
                zone_3_volume_names,
            )

            # =====================================================================
            # ZONE 4: Outer refinement ring, R + D1 + D2 to R + D1 + D2 + D3
            # =====================================================================

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

            create_surface_from_polycurve()
            extrude_surface_to_volume(dz)

            zone_4_soil, zone_4_volume = assign_latest_soil_material(
                layer_material,
                zone_4_volumes,
                zone_4_volume_names,
            )


        print("Finished manual Structures geometry.")
        print(f"  Zone 1 volumes: {len(zone_1_volumes)}")
        print(f"  Zone 2 volumes: {len(zone_2_volumes)}")
        print(f"  Zone 3 volumes: {len(zone_3_volumes)}")
        print(f"  Zone 4 volumes: {len(zone_4_volumes)}")

        # =============================================================================
        # 6. MESH MODE: RADIAL REFINEMENT
        # =============================================================================

        g_i.gotomesh()


        def get_mesh_volume_from_structure_volume_name(g_i, structure_volume_name):
            """
            PLAXIS often exposes a structure volume called Volume_61
            in mesh mode as Volume_61_1.

            This function tries that naming convention first.
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


        # Zone 1: borehole excavation volumes
        for name in zone_1_volume_names:
            mesh_vol = get_mesh_volume_from_structure_volume_name(g_i, name)
            mesh_vol.CoarsenessFactor = f1
            print(f"Mesh refinement: {name}_1 -> f1 = {f1}")


        # Zone 2: near-borehole ring
        for name in zone_2_volume_names:
            mesh_vol = get_mesh_volume_from_structure_volume_name(g_i, name)
            mesh_vol.CoarsenessFactor = f2
            print(f"Mesh refinement: {name}_1 -> f2 = {f2}")


        # Zone 3: middle ring
        for name in zone_3_volume_names:
            mesh_vol = get_mesh_volume_from_structure_volume_name(g_i, name)
            mesh_vol.CoarsenessFactor = f3
            print(f"Mesh refinement: {name}_1 -> f3 = {f3}")


        # Zone 4: outer ring
        for name in zone_4_volume_names:
            mesh_vol = get_mesh_volume_from_structure_volume_name(g_i, name)
            mesh_vol.CoarsenessFactor = f4
            print(f"Mesh refinement: {name}_1 -> f4 = {f4}")


        g_i.mesh(
            "ElementDimension", le,
            "UseEnhancedRefinements", False
        )

        # =============================================================================
        # 7. STAGES MODE: STEPWISE BOREHOLE UNLOADING
        # =============================================================================

        g_i.gotostages()

        # Initial phase
        g_i.set(g_i.InitialPhase.DeformCalcType, "K0 procedure")

        # =============================================================================
        # Activate all manually created soil volumes in the Initial Phase
        # =============================================================================

        all_soil_volume_names = (
            zone_1_volume_names +
            zone_2_volume_names +
            zone_3_volume_names +
            zone_4_volume_names
        )

        for name in all_soil_volume_names:
            stage_volume = getattr(g_i, name + "_1")
            stage_volume.activate(g_i.InitialPhase)

        print(f"Activated {len(all_soil_volume_names)} soil volumes in Initial Phase.")

        g_i.GroundwaterFlow.deactivate(g_i.InitialPhase)
        g_i.Dynamics.deactivate(g_i.InitialPhase)
        g_i.Water.deactivate(g_i.InitialPhase)

        # Boundary conditions for initial phase
        g_i.Deformations.BoundaryXMin.set(g_i.InitialPhase, "Normally fixed")
        g_i.Deformations.BoundaryXMax.set(g_i.InitialPhase, "Normally fixed")
        g_i.Deformations.BoundaryYMin.set(g_i.InitialPhase, "Normally fixed")
        g_i.Deformations.BoundaryYMax.set(g_i.InitialPhase, "Normally fixed")
        g_i.Deformations.BoundaryZMin.set(g_i.InitialPhase, "Normally fixed")
        g_i.Deformations.BoundaryZMax.set(g_i.InitialPhase, "Normally fixed")

        previous_phase = g_i.InitialPhase

        for step_idx, load_factor in enumerate(lf):

            g_i.phase(previous_phase)
            phase = g_i.phases[-1]

            phase.Identification = f"Borehole unloading {step_idx + 1} - LF {load_factor:.2f}"

            # Remove the borehole soil volumes
            for name in zone_1_volume_names:
                borehole_volume_stage = getattr(g_i, name + "_1")
                borehole_volume_stage.deactivate(phase)


            # Activate and scale all borehole wall pressures
            for load_idx, load_name in enumerate(borehole_load_names):

                borehole_load_stage = getattr(g_i, load_name + "_1")

                scaled_ref = borehole_load_refs[load_idx] * load_factor
                scaled_inc = borehole_load_incs[load_idx] * load_factor

                borehole_load_stage.activate(phase)

                borehole_load_stage.sign_ref.set(phase, scaled_ref)
                borehole_load_stage.sign_inc.set(phase, scaled_inc)


            # Keep calculation conditions consistent
            g_i.GroundwaterFlow.deactivate(phase)
            g_i.Dynamics.deactivate(phase)
            g_i.Water.deactivate(phase)

            # Boundary conditions
            g_i.Deformations.BoundaryXMin.set(phase, "Normally fixed")
            g_i.Deformations.BoundaryXMax.set(phase, "Normally fixed")
            g_i.Deformations.BoundaryYMin.set(phase, "Normally fixed")
            g_i.Deformations.BoundaryYMax.set(phase, "Normally fixed")
            g_i.Deformations.BoundaryZMin.set(phase, "Normally fixed")
            g_i.Deformations.BoundaryZMax.set(phase, "Normally fixed")

            previous_phase = phase


        # =============================================================================
        # DEBUG: CHECK CREATED BOREHOLE WALL LOADS
        # =============================================================================

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
        # 8. CALCULATE
        # =============================================================================
        
        project_file = os.path.join(output_dir, project_name + ".p3d")
        print(f"Saving PLAXIS project before calculation to: {project_file}")
        g_i.save(project_file)

        print("Starting PLAXIS calculation...")
        g_i.calculate()
        print("Calculation finished.")

        print(f"Saving calculated PLAXIS project to: {project_file}")
        g_i.save(project_file)


        # =============================================================================
        # 9. OUTPUT EXTRACTION
        # =============================================================================
        # -------------------------------------------------------------------------
        # Output file
        # -------------------------------------------------------------------------
        # output_dir is provided by run_single_cpt()
        os.makedirs(output_dir, exist_ok=True)

        output_file = os.path.join(output_dir, f"{result_stem}.xlsx")

        output_port = g_i.view(g_i.InitialPhase)
        s_o, g_o = new_server('localhost', port=output_port, password=PASSWORD)


        # -------------------------------------------------------------------------
        # Horizontal extraction distances from borehole wall
        # -------------------------------------------------------------------------
        distances_from_wall = np.concatenate([
            np.array([0.02, 0.05, 0.10, 0.15]),     # very close to borehole wall
            np.arange(0.20, 2.00 + 0.001, 0.10),   # 0.20 m to 2.00 m every 0.10 m
            np.arange(2.50, 5.00 + 0.001, 0.50),   # 2.50 m to 5.00 m every 0.50 m
            np.arange(6.00, 10.00 + 0.001, 1.00),  # 6.00 m to 10.00 m every 1.00 m
        ])

        # Extraction direction: 45 degrees in x-y plane
        theta = np.radians(45.0)

        # -------------------------------------------------------------------------
        # Vertical extraction points
        #
        # For all layers except the last:
        #   one point at the middle of the layer.
        #
        # For the last layer:
        #   points every 2.00 m.
        # -------------------------------------------------------------------------
        last_layer_vertical_spacing = 0.7 # [m] vertical spacing for extraction points in the last layer

        vertical_points = []

        if extraction_mode == "all_layers":

            # Linear run:
            # extract one point at the middle of every layer,
            # and multiple points in the final sand layer.
            for layer_idx in range(n_layers):

                layer_name = clean_name(df_soil.iloc[layer_idx + 3, 0])

                if layer_idx == 0:
                    z_top = float(df_soil.iloc[2, 1])
                else:
                    z_top = float(df_soil.iloc[layer_idx + 2, 1])

                z_bottom = float(df_soil.iloc[layer_idx + 3, 1])

                if layer_idx < n_layers - 1:
                    z_mid = 0.5 * (z_top + z_bottom)

                    vertical_points.append({
                        "layer_index": layer_idx + 1,
                        "layer_name": layer_name,
                        "z": float(z_mid)
                    })

                else:
                    z_values = np.arange(
                        z_top - last_layer_vertical_spacing,
                        z_bottom + 0.2, # To avoid extraction at boundary
                        -last_layer_vertical_spacing
                    )

                    for z_val in z_values:
                        vertical_points.append({
                            "layer_index": layer_idx + 1,
                            "layer_name": layer_name,
                            "z": float(z_val)
                        })

        elif extraction_mode == "last_layer_only":

            # MC run:
            # extract only in the final sand layer.
            layer_idx = n_layers - 1

            layer_name = clean_name(df_soil.iloc[layer_idx + 3, 0])
            z_top = float(df_soil.iloc[layer_idx + 2, 1])
            z_bottom = float(df_soil.iloc[layer_idx + 3, 1])

            z_values = np.arange(
                z_top - last_layer_vertical_spacing,
                z_bottom + 0.2, # To avoid extraction at boundary
                -last_layer_vertical_spacing
            )

            for z_val in z_values:
                vertical_points.append({
                    "layer_index": layer_idx + 1,
                    "layer_name": layer_name,
                    "z": float(z_val)
                })

        else:
            raise ValueError(f"Unknown extraction_mode: {extraction_mode}")

        print("Vertical extraction points:")
        for vp in vertical_points:
            print(
                f"  layer={vp['layer_index']}, "
                f"name={vp['layer_name']}, "
                f"z={vp['z']:.3f}"
            )


        # -------------------------------------------------------------------------
        # Build coordinate table
        # -------------------------------------------------------------------------
        coords = []

        for vp in vertical_points:
            for d_wall in distances_from_wall:

                r = R + d_wall

                x = x_bh + r * np.cos(theta)
                y = y_bh + r * np.sin(theta)
                z = vp["z"]

                coords.append({
                    "layer_index": vp["layer_index"],
                    "layer_name": vp["layer_name"],
                    "distance_from_wall": float(d_wall),
                    "radius_from_centre": float(r),
                    "x": float(x),
                    "y": float(y),
                    "z": float(z)
                })


        # -------------------------------------------------------------------------
        # Safe result extraction helper
        # -------------------------------------------------------------------------
        def safe_get_result(phase, result_type, coord):
            """
            Returns a PLAXIS result as float where possible.
            Returns np.nan if the result is unavailable.
            """
            try:
                value = g_o.getsingleresult(phase, result_type, coord)

                if value is None:
                    return np.nan

                if isinstance(value, str):
                    # PLAXIS may return strings like "not found" or empty values.
                    try:
                        return float(value)
                    except ValueError:
                        return np.nan

                return float(value)

            except Exception:
                return np.nan


        # -------------------------------------------------------------------------
        # Result column definition
        # -------------------------------------------------------------------------
        column_names = [
            "phase_index",
            "phase_name",
            "load_factor",

            "layer_index",
            "layer_name",

            "distance_from_wall",
            "radius_from_centre",

            "x",
            "y",
            "z",

            "sigx",
            "sigy",
            "sigz",
            "sigxy",
            "sigyz",
            "sigzx",

            "sig1",
            "sig2",
            "sig3",

            "e",

            "epsx",
            "epsy",
            "epsz",
            "epsxy",
            "epsyz",
            "epszx",
        ]


        # -------------------------------------------------------------------------
        # Extract selected phases only
        # -------------------------------------------------------------------------
        n_phases = len(g_o.Phases)
        print(f"len(lf) = {len(lf)}")
        print(f"n_phases in PLAXIS Output = {n_phases}")
        print(f"last available phase index = {n_phases - 1}")

        phase_indices_to_extract = []

        if ONLY_EXTRACT_EXTRA_PHASES:
            # Manual-only mode:
            # only extract the phases listed in EXTRA_PHASE_INDICES_TO_EXTRACT.
            for phase_idx in EXTRA_PHASE_INDICES_TO_EXTRACT:
                if 0 < phase_idx < n_phases:
                    phase_indices_to_extract.append(phase_idx)
                else:
                    print(
                        f"Warning: requested phase_{phase_idx}, "
                        f"but valid phase indices are 0 to {n_phases - 1}."
                    )

        else:
            # PLAXIS phase index:
            #   0 = InitialPhase
            #   1 = unloading step 0, LF = 1.00
            #   2 = unloading step 1, LF = 0.99
            #   ...
            #   101 = unloading step 100, LF = 0.00
            for lf_idx in range(len(lf)):
                if lf_idx % EXTRACT_EVERY_N_UNLOADING_STEPS == 0:
                    phase_idx = lf_idx + 1

                    if phase_idx < n_phases:
                        phase_indices_to_extract.append(phase_idx)

            # Always include final calculated phase, in case it was missed by rounding/indexing.
            final_phase_idx = n_phases - 1
            if final_phase_idx not in phase_indices_to_extract:
                phase_indices_to_extract.append(final_phase_idx)

            
            # -------------------------------------------------------------------------
            # Temporary manual additions/removals
            # -------------------------------------------------------------------------
            for phase_idx in EXTRA_PHASE_INDICES_TO_EXTRACT:
                if 0 < phase_idx < n_phases:
                    phase_indices_to_extract.append(phase_idx)


        phase_indices_to_extract = sorted(set(phase_indices_to_extract))

        print("Phase indices selected for extraction:")
        for phase_idx in phase_indices_to_extract:
                lf_idx = phase_idx - 1
                lf_value = float(lf[lf_idx]) if lf_idx < len(lf) else np.nan
                print(f"  phase_{phase_idx}: LF = {lf_value:.2f}")

        with pd.ExcelWriter(output_file, mode="w", engine="openpyxl") as writer:

            for phase_idx in phase_indices_to_extract:

                phase = g_o.Phases[phase_idx]

                try:
                    phase_name = phase.Identification.value
                except Exception:
                    phase_name = f"phase_{phase_idx}"

                if phase_idx == 0:
                    load_factor = np.nan
                else:
                    lf_idx = phase_idx - 1
                    load_factor = float(lf[lf_idx]) if lf_idx < len(lf) else np.nan

                rows = []

                print(f"Extracting results for phase {phase_idx}: {phase_name}")

                for c in coords:

                    x = c["x"]
                    y = c["y"]
                    z = c["z"]
                    coord = (x, y, z)

                    sigx = safe_get_result(phase, g_o.ResultTypes.Soil.SigxxE, coord)
                    sigy = safe_get_result(phase, g_o.ResultTypes.Soil.SigyyE, coord)
                    sigz = safe_get_result(phase, g_o.ResultTypes.Soil.SigzzE, coord)

                    sigxy = safe_get_result(phase, g_o.ResultTypes.Soil.Sigxy, coord)
                    sigyz = safe_get_result(phase, g_o.ResultTypes.Soil.Sigyz, coord)
                    sigzx = safe_get_result(phase, g_o.ResultTypes.Soil.Sigzx, coord)

                    sig1 = safe_get_result(phase, g_o.ResultTypes.Soil.SigmaEffective1, coord)
                    sig2 = safe_get_result(phase, g_o.ResultTypes.Soil.SigmaEffective2, coord)
                    sig3 = safe_get_result(phase, g_o.ResultTypes.Soil.SigmaEffective3, coord)

                    # Strains and void ratio may be unavailable in InitialPhase or for some models.
                    if phase_idx == 0:
                        e = np.nan
                        epsx = np.nan
                        epsy = np.nan
                        epsz = np.nan
                        epsxy = np.nan
                        epsyz = np.nan
                        epszx = np.nan
                    else:
                        e = safe_get_result(phase, g_o.ResultTypes.Soil.VoidRatio, coord)

                        epsx = safe_get_result(phase, g_o.ResultTypes.Soil.Epsxx, coord)
                        epsy = safe_get_result(phase, g_o.ResultTypes.Soil.Epsyy, coord)
                        epsz = safe_get_result(phase, g_o.ResultTypes.Soil.Epszz, coord)

                        epsxy = safe_get_result(phase, g_o.ResultTypes.Soil.Gamxy, coord)
                        epsyz = safe_get_result(phase, g_o.ResultTypes.Soil.Gamyz, coord)
                        epszx = safe_get_result(phase, g_o.ResultTypes.Soil.Gamzx, coord)

                    rows.append([
                        phase_idx,
                        phase_name,
                        load_factor,

                        c["layer_index"],
                        c["layer_name"],

                        c["distance_from_wall"],
                        c["radius_from_centre"],

                        x,
                        y,
                        z,

                        sigx,
                        sigy,
                        sigz,
                        sigxy,
                        sigyz,
                        sigzx,

                        sig1,
                        sig2,
                        sig3,

                        e,

                        epsx,
                        epsy,
                        epsz,
                        epsxy,
                        epsyz,
                        epszx,
                    ])

                df_phase = pd.DataFrame(rows, columns=column_names)

                # Excel sheet names max length is 31 characters
                sheet_name = f"phase_{phase_idx}"
                df_phase.to_excel(writer, sheet_name=sheet_name, index=False)

            # ---------------------------------------------------------------------
            # Metadata sheet
            # ---------------------------------------------------------------------
            metadata_rows = [
                ["created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                ["input_file", file],
                ["R", R],
                ["radius_folder", radius_folder_name(radius)],
                ["D1", D1],
                ["D2", D2],
                ["D3", D3],
                ["x_bh", x_bh],
                ["y_bh", y_bh],
                ["z_model_top", z_model_top],
                ["z_model_bottom", z_model_bottom],
                ["n_layers", n_layers],
                ["n_phases", n_phases],
                ["last_layer_vertical_spacing", last_layer_vertical_spacing],
                ["horizontal_distances_from_wall_m", ", ".join([f"{d:.3f}" for d in distances_from_wall])],
                ["extraction_angle_deg", 45.0],
            ]

            df_metadata = pd.DataFrame(metadata_rows, columns=["parameter", "value"])
            df_metadata.to_excel(writer, sheet_name="metadata", index=False)

        print(f"Results written to: {output_file}")

    finally:
        close_plaxis(plaxis_process)

    print("=" * 100)
    print(f"Finished CPT run: {project_name}")
    print("=" * 100)


# =============================================================================
# BATCH EXECUTION
# =============================================================================

if __name__ == "__main__":
    runs = get_batch_runs()

    print("Discovered/configured CPT inputs:")
    for idx, run in enumerate(runs, start=1):
        print(f"  {idx}. {run['cpt_name']} -> {run['input_file']}")

    print("Borehole radii to run:")
    for radius in BOREHOLE_RADII:
        print(f"  - {radius:.3f} m -> {os.path.join(OUTPUT_ROOT_DIR, radius_folder_name(radius))}")

    for radius in BOREHOLE_RADII:
        print("#" * 100)
        print(f"Starting radius batch: R = {radius:.3f} m")
        print("#" * 100)

        for run in runs:
            run_single_cpt(
                input_file=run["input_file"],
                radius=radius,
                eini_override=run["eini"],
                run_suffix=run["run_suffix"],
            )

        print("#" * 100)
        print(f"Finished radius batch: R = {radius:.3f} m")
        print("#" * 100)

    print("BOMBACLAT. All CPT/radius runs completed.")
