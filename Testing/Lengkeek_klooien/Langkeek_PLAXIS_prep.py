import numpy as np
import pandas as pd
import os

# ==========================================
# 1. USER SETTINGS
# ==========================================
GEF_FILE_PATH = r"C:\AA_Thesis\CPT_Measurements\Campus-Zuid\Pre-boren\S1022749_CPTU1-2.gef"
GWL = 0.0  
PA = 0.1   
MIN_LAYER_THICKNESS = 0.20  # Filters out layers thinner than 20cm

# ==========================================
# 2. PARSER & ENGINE
# ==========================================
def parse_gef(file_path):
    data = []
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        start_reading = False
        for line in lines:
            if '#EOH=' in line:
                start_reading = True
                continue
            if start_reading:
                parts = line.strip().replace('|', ' ').split()
                if len(parts) >= 3:
                    data.append([float(x) for x in parts[:3]])
        return pd.DataFrame(data, columns=['depth', 'qc', 'fs'])
    except Exception as e:
        print(f"Error reading GEF: {e}")
        return None

def process_langkeek_data(df):
    gamma_sat, gamma_w = 18.0/1000, 9.81/1000
    df['sigma_v0'] = df['depth'] * gamma_sat
    df['u0'] = np.where(df['depth'] > GWL, (df['depth'] - GWL) * gamma_w, 0)
    df['sigma_veff'] = (df['sigma_v0'] - df['u0']).replace(0, 0.0001)

    # Iterative Robertson (2010) + Langkeek Boundaries
    df['n'] = 1.0
    for _ in range(5):
        df['Qtn'] = ((df['qc'] - df['sigma_v0']) / PA) * (PA / df['sigma_veff'])**df['n']
        df['Fr'] = (df['fs'] / (df['qc'] - df['sigma_v0'])) * 100
        df['Ic'] = ((3.47 - np.log10(df['Qtn'].clip(0.1)))**2 + (np.log10(df['Fr'].clip(0.1)) + 1.22)**2)**0.5
        df['n'] = (0.381 * df['Ic'] + 0.05 * (df['sigma_veff'] / PA) - 0.15).clip(0.5, 1.0)

    def get_zone(ic):
        if ic > 3.60: return "Organic"
        if ic > 2.95: return "Clay"
        if ic > 2.60: return "Silt_Mix"
        if ic > 2.05: return "Sand_Mix"
        if ic > 1.31: return "Sand"
        return "Gravelly_Sand"

    df['Soil_Type'] = df['Ic'].apply(get_zone)
    
    # --- LAYER CLEAN-UP LOGIC ---
    # 1. Initial ID assignment
    df['Layer_ID'] = (df['Soil_Type'] != df['Soil_Type'].shift()).cumsum()
    
    # 2. Iterate to merge thin layers
    # We do this twice to catch layers that become thin after their neighbor merged
    for _ in range(2):
        layer_stats = df.groupby('Layer_ID')['depth'].agg(['min', 'max'])
        layer_stats['thickness'] = layer_stats['max'] - layer_stats['min']
        
        for idx, row in layer_stats[layer_stats['thickness'] < MIN_LAYER_THICKNESS].iterrows():
            if idx > 1:
                # Get the soil type of the layer ABOVE it
                prev_type = df.loc[df['Layer_ID'] == idx-1, 'Soil_Type'].iloc[0]
                df.loc[df['Layer_ID'] == idx, 'Soil_Type'] = prev_type
        
        # Re-calculate IDs after merging types
        df['Layer_ID'] = (df['Soil_Type'] != df['Soil_Type'].shift()).cumsum()

    df['Layer_Label'] = df['Soil_Type'] + "_L" + df['Layer_ID'].astype(str)
    return df

# ==========================================
# 3. EXECUTION
# ==========================================
if __name__ == "__main__":
    cpt_df = parse_gef(GEF_FILE_PATH)
    if cpt_df is not None:
        processed_df = process_langkeek_data(cpt_df)
        
        # Summary for PLAXIS
        plaxis_summary = processed_df.groupby(['Layer_ID', 'Soil_Type']).agg({
            'depth': ['min', 'max'],
            'qc': 'mean',
            'Ic': 'mean'
        }).reset_index()
        plaxis_summary.columns = ['Layer_ID', 'Soil_Type', 'Top', 'Bottom', 'Avg_qc', 'Avg_Ic']
        
        # Save
        processed_df.to_csv("CPT_Full_Points.csv", index=False)
        plaxis_summary.to_csv("PLAXIS_Layer_Summary.csv", index=False)
        
        print(f"Success! Files saved in: {os.getcwd()}")