import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ==========================================
# 1. USER SETTINGS & FILE PATHS
# ==========================================
GEF_FILE_PATH = r"C:\AA_Thesis\CPT_Measurements\Campus-Zuid\Pre-boren\S1022749_CPTU1-2.gef"
MIN_LAYER_THICKNESS = 0.2  # Meters
USE_DUMMY_DATA = False      # Set to True to test without a GEF file

# Soil Type Definitions (Robertson 1990)
SBT_ZONES = {
    1: {"name": "Sensitive Fine Grained",      "color": "#E0E0E0"}, 
    2: {"name": "Organic Soils",               "color": "#8D6E63"}, 
    3: {"name": "Clays",                       "color": "#1E88E5"}, 
    4: {"name": "Silty Clay to Clay",          "color": "#4DD0E1"}, 
    5: {"name": "Clayey Silt to Silty Clay",   "color": "#4CAF50"}, 
    6: {"name": "Sands",                       "color": "#FFEE58"}, 
    7: {"name": "Gravelly Sand to Sand",       "color": "#FFB300"}, 
    8: {"name": "Very Stiff Sand/Clayey Sand", "color": "#F44336"}, 
    9: {"name": "Very Stiff Fine Grained",     "color": "#9C27B0"}  
}

# ==========================================
# 2. CORE FUNCTIONS
# ==========================================

def parse_gef(file_path):
    """Parses depth, qc, and fs from a standard GEF file."""
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
                    # Adjust indices [0, 1, 2] if your GEF columns are different
                    data.append([float(x) for x in parts[:3]])
        
        return pd.DataFrame(data, columns=['depth', 'qc', 'fs'])
    except Exception as e:
        print(f"Error reading GEF: {e}")
        return None

def classify_robertson_9_zone(qc, fs):
    """Basic Robertson 1990 classification logic."""
    if qc <= 0 or fs <= 0: return 1
    Rf = (fs / qc) * 100
    if Rf > 8: return 1
    if qc < 0.5: return 2
    if Rf > 4 and qc < 1.5: return 3
    if Rf > 2 and qc < 3: return 4
    if Rf > 1 and qc < 10: return 5
    if Rf < 2 and qc > 10: return 6
    if Rf < 1 and qc > 20: return 7
    if qc > 20: return 8
    return 9

def apply_layer_filter(df, min_thick):
    """Merges layers thinner than the user-defined threshold."""
    df['raw_zone'] = df.apply(lambda x: classify_robertson_9_zone(x['qc'], x['fs']), axis=1)
    df['filtered_zone'] = df['raw_zone'].copy()
    
    # Simple smoothing: if a point's neighbors are the same but it's different, flip it
    # Then apply thickness logic
    df['layer_id'] = (df['raw_zone'] != df['raw_zone'].shift()).cumsum()
    layer_stats = df.groupby('layer_id')['depth'].agg(['min', 'max'])
    layer_stats['thickness'] = layer_stats['max'] - layer_stats['min']
    
    for idx, row in layer_stats[layer_stats['thickness'] < min_thick].iterrows():
        if idx > 1:
            prev_zone = df.loc[df['layer_id'] == idx-1, 'filtered_zone'].iloc[0]
            df.loc[df['layer_id'] == idx, 'filtered_zone'] = prev_zone
            
    return df

def plot_cpt_results(df):
    """Generates the side-by-side log plot."""
    fig, axes = plt.subplots(1, 4, figsize=(12, 8), sharey=True, 
                             gridspec_kw={'width_ratios': [2, 1, 0.5, 0.5]})
    
    # qc Plot
    axes[0].plot(df['qc'], df['depth'], color='black', lw=1.5)
    axes[0].set_xlabel('qc [MPa]')
    axes[0].invert_yaxis()
    axes[0].grid(True, which='both', alpha=0.3)

    # Rf Plot
    rf = (df['fs'] / df['qc']) * 100
    axes[1].plot(rf, df['depth'], color='red', lw=1)
    axes[1].set_xlabel('Rf [%]')
    axes[1].set_xlim(0, 10)
    axes[1].grid(True, alpha=0.3)

    # Classification Stripes
    for zone_id, info in SBT_ZONES.items():
        axes[2].fill_betweenx(df['depth'], 0, 1, where=(df['raw_zone'] == zone_id), color=info['color'])
        axes[3].fill_betweenx(df['depth'], 0, 1, where=(df['filtered_zone'] == zone_id), color=info['color'])

    axes[2].set_title('Raw')
    axes[3].set_title('Filtered')
    axes[3].tick_params(labelleft=True)
    for ax in [axes[2], axes[3]]: ax.set_xticks([])

    plt.suptitle(f"CPT Analysis (Min Thickness: {MIN_LAYER_THICKNESS}m)")
    plt.tight_layout()
    plt.show()

# ==========================================
# 3. EXECUTION BLOCK
# ==========================================
if __name__ == "__main__":
    if USE_DUMMY_DATA:
        # Create fake data if no file is present
        z = np.linspace(0, 20, 500)
        qc = np.where(z < 10, 2.0, 15.0) + np.random.normal(0, 0.5, 500)
        fs = qc * 0.03
        df = pd.DataFrame({'depth': z, 'qc': qc, 'fs': fs})
    else:
        df = parse_gef(GEF_FILE_PATH)

    if df is not None:
        df = apply_layer_filter(df, MIN_LAYER_THICKNESS)
        plot_cpt_results(df)
    else:
        print("Process failed. Check your file path or GEF structure.")