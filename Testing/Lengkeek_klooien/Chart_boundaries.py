import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# 1. Define the SBT Index (Isbt) function
def get_isbt(qt_pa, Rf):
    return np.sqrt((3.47 - np.log10(qt_pa))**2 + (1.22 + np.log10(Rf))**2)

# 2. Setup the Grid for the background colors
rf_grid = np.logspace(-1, 1.2, 500)
qt_grid = np.logspace(0, 3, 500)
RF, QT = np.meshgrid(rf_grid, qt_grid)
ISBT = get_isbt(QT, RF)

# 3. Define Robertson (2010) standard boundaries and colors
# Zones: 2: Organic, 3: Clay, 4: Silt mixtures, 5: Sand mixtures, 6: Sands, 7: Gravelly sand
bounds = [0, 1.31, 2.05, 2.6, 2.95, 3.6, 10]
# Colors roughly matching standard Robertson charts
colors = ['#556B2F', '#90EE90', '#D2B48C', '#FFFF00', '#FFA500', '#FF0000'] # Dark Green to Red
cmap = mcolors.ListedColormap(colors)
norm = mcolors.BoundaryNorm(bounds, cmap.N)

# 4. Lengkeek (2024) specific boundaries for Organic Soils
rf_l2024 = np.linspace(0.1, 20, 500)
# Peat (2a): qt/pa = 16.7 * (Rf - 5.1)^0.25
qt_peat = np.where(rf_l2024 > 5.1, 16.7 * (rf_l2024 - 5.1)**0.25, np.nan)
# Organic Clay (2b): qt/pa = 10.3 * (Rf - 2.7)^0.15
qt_org_clay = np.where(rf_l2024 > 2.7, 10.3 * (rf_l2024 - 2.7)**0.15, np.nan)

# 5. Create Plot
fig, ax = plt.subplots(figsize=(9, 10))

# Background: Robertson (2010) Zones
im = ax.pcolormesh(RF, QT, ISBT, cmap=cmap, norm=norm, alpha=0.4, shading='auto')

# Plot Lengkeek (2024) Boundaries
ax.plot(rf_l2024, qt_peat, color='black', linewidth=2.5, label='L2024: Peat (2a)')
ax.plot(rf_l2024, qt_org_clay, color='darkgreen', linewidth=2.5, linestyle='--', label='L2024: Organic Clay (2b)')

# Formatting
ax.set_xscale('log')
ax.set_yscale('log')
ax.set_xlim(0.1, 20)
ax.set_ylim(1, 1000)
ax.set_xlabel('Friction Ratio $R_f$ (%)', fontweight='bold')
ax.set_ylabel('Normalized Cone Resistance $q_t/p_a$ (-)', fontweight='bold')
ax.grid(True, which="both", ls="-", alpha=0.2)

# Labeling Zones (approximate positions)
ax.text(0.2, 500, '7: Gravelly Sand', fontsize=9)
ax.text(0.2, 100, '6: Sands', fontsize=9)
ax.text(0.2, 30, '5: Sand Mixtures', fontsize=9)
ax.text(0.2, 10, '4: Silt Mixtures', fontsize=9)
ax.text(0.2, 3, '3: Clays', fontsize=9)
ax.text(8, 2, '2: Organic Soils', fontsize=9, color='darkgreen', fontweight='bold')

plt.title('Non-Normalised SBT Chart (Robertson 2010)\nwith Lengkeek (2024) Organic Boundaries', pad=20)
plt.legend(loc='upper right')
plt.tight_layout()
plt.show()