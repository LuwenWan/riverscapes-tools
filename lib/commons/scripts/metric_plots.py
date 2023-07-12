# brute forcing out some plots for firedrill for Alden S.
# need to install geopandas to use

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np

gpkg_path = ''
lyr_name = ''
lyr_name2 = ''
field_name = ''
hist = False
bar = False
pie = False

df = gpd.read_file(gpkg_path, layer=lyr_name)
df2 = gpd.read_file(gpkg_path, layer=lyr_name2)

# if need to sub to non-zero values
# df = df[df[field_name]>0]

# field stats
min, max, ave = df[field_name].min(), df[field_name].max(), df[field_name].mean()
min2, max2, ave2 = df2[field_name].min(), df2[field_name].max(), df2[field_name].mean()
print(min, max, ave)
print(min2, max2, ave2)

# histogram/distribution plots
if hist:
    fig, ax = plt.subplots(1, 2, figsize=(10, 5))
    ax[0].hist(df['Agriculture'], color='goldenrod')
    # ax[0].set_xscale('log')
    ax[0].set_yscale('log')
    ax[0].set_xlim(0, 1)
    ax[0].set_xlabel('Fraction Converted to Agriculture')
    ax[0].set_ylabel('IGO Count')
    ax[0].set_title('All Riverscapes')
    ax[1].hist(df2['Agriculture'], color='goldenrod')
    # ax[1].set_xscale('log')
    ax[1].set_yscale('log')
    ax[1].set_xlim(0, 1)
    ax[1].set_xlabel('Fraction Converted to Agriculture')
    ax[1].set_title('BLM Riverscapes')
    plt.suptitle('Riverscape Conversion to Agriculture', fontsize=16)
    plt.tight_layout()
    # plt.savefig('/mnt/c/Users/jordang/Documents/LTPBR/BLM_SanLuis/IGO_conversion_to_ag.png', dpi=250)
    plt.show()

if bar:
    cat1 = 0
    cat2 = 0
    cat3 = 0
    cat4 = 0
    cat5 = 0
    for i in df.index:
        if df.loc[i, 'FloodplainAccess'] < 0.25:
            cat1 += df.loc[i, 'LengthKM']
        elif 0.25 <= df.loc[i, 'FloodplainAccess'] < 0.75:
            cat2 += df.loc[i, 'LengthKM']
        elif 0.75 <= df.loc[i, 'FloodplainAccess'] < 0.95:
            cat3 += df.loc[i, 'LengthKM']
        else:
            cat4 += df.loc[i, 'LengthKM']
    cat12 = 0
    cat22 = 0
    cat32 = 0
    cat42 = 0
    cat52 = 0
    for i in df2.index:
        if df2.loc[i, 'FloodplainAccess'] < 0.25:
            cat12 += df2.loc[i, 'LengthKM']
        elif 0.25 <= df2.loc[i, 'FloodplainAccess'] < 0.75:
            cat22 += df2.loc[i, 'LengthKM']
        elif 0.75 < df2.loc[i, 'FloodplainAccess'] <= 0.95:
            cat32 += df2.loc[i, 'LengthKM']
        else:
            cat42 += df2.loc[i, 'LengthKM']
    vals1 = [int(cat1), int(cat2), int(cat3), int(cat4)]
    vals2 = [int(cat12), int(cat22), int(cat32), int(cat42)]
    fig, ax = plt.subplots(2, 1)
    rects = ax[0].barh(['<25% accessible', '25-75% accessible', '75-95% accessible', '>95% accessible'], vals1, color=['firebrick', 'salmon', 'lightsteelblue', 'royalblue'])
    ax[0].bar_label(rects, label_type='edge', color='k')
    ax[0].set_title('All')
    ax[0].set_xlim((0, 13000))
    rects2 = ax[1].barh(['<25% accessible', '25-75% accessible', '75-95% accessible', '>95% accessible'], vals2, color=['firebrick', 'salmon', 'lightsteelblue', 'royalblue'])
    ax[1].bar_label(rects2, label_type='edge', color='k')
    ax[1].set_title('BLM')
    ax[1].set_xlabel(r'length ($km$)')
    ax[1].set_xlim((0, 2200))
    plt.suptitle('Floodplain Accessibility by Reach', fontsize=16)
    plt.tight_layout()
    # plt.savefig('/mnt/c/Users/jordang/Documents/LTPBR/BLM_SanLuis/reaches_fpaccess.png', dpi=250)

if pie:
    vlow = 0
    low = 0
    mod = 0
    high = 0
    oth = 0
    for i in df.index:
        if df.loc[i, 'FloodplainAccess'] < 0.25:
            vlow += 1
        elif 0.25 <= df.loc[i, 'FloodplainAccess'] < 0.75:
            low += 1
        elif 0.75 <= df.loc[i, 'FloodplainAccess'] < 0.95:
            mod += 1
        else:
            high += 1
    vlow2 = 0
    low2 = 0
    mod2 = 0
    high2 = 0
    oth2 = 0
    for i in df2.index:
        if df2.loc[i, 'FloodplainAccess'] < 0.25:
            vlow2 += 1
        elif 0.25 <= df2.loc[i, 'FloodplainAccess'] < 0.75:
            low2 += 1
        elif 0.75 <= df2.loc[i, 'FloodplainAccess'] < 0.95:
            mod2 += 1
        else:
            high2 += 1
    sizes = [vlow, low, mod, high]
    sizes2 = [vlow2, low2, mod2, high2]
    labels = '<25% accessible', '25-75% accessible', '75-95% accessible', '>95% accessible'
    fig, ax = plt.subplots(1, 2, figsize=(10, 5))
    ax[0].pie(sizes, labels=labels, colors=['firebrick', 'salmon', 'lightsteelblue', 'royalblue'], autopct='%1.1f%%',
              explode=(0.6, 0.2, 0.1, 0.1))
    ax[0].set_title('All Riverscapes')
    ax[1].pie(sizes2, labels=labels, colors=['firebrick', 'salmon', 'lightsteelblue', 'royalblue'], autopct='%1.1f%%',
              explode=(0.6, 0.2, 0.1, 0.1))
    ax[1].set_title('BLM Riverscapes')
    plt.suptitle('Riverscape Floodplain Accessibility', fontsize=16)
    plt.tight_layout()
    # plt.savefig('/mnt/c/Users/jordang/Documents/LTPBR/BLM_SanLuis/IGO_fpaccess.png', dpi=250)
    plt.show()
