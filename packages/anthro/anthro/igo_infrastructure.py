"""Functions to attribute IGO points with attributes related to the presence of infrastructure within the riverscape.

Jordan Gilbert

Dec 2022
"""
import os
import sqlite3
import json
import numpy as np
from osgeo import ogr
from rscommons import GeopackageLayer, get_shp_or_gpkg
from rscommons.classes.vector_base import VectorBase, get_utm_zone_epsg
from rscommons.vector_ops import get_geometry_unary_union


def infrastructure_attributes(igo: str, windows: str, road: str, rail: str, canal: str, crossings: str, diversions: str,
                              out_gpkg_path: str):

    in_data = {
        road: 'Road',
        rail: 'Rail',
        canal: 'Canal',
        crossings: 'RoadX',
        diversions: 'DivPts'
    }

    # get epsg_proj
    with get_shp_or_gpkg(igo) as inref:
        ftr = inref.ogr_layer.GetFeature(1)
        long = ftr.GetGeometryRef().GetEnvelope()[0]
        epsg_proj = get_utm_zone_epsg(long)

    conn = sqlite3.connect(out_gpkg_path)
    # curs = conn.cursor()

    with get_shp_or_gpkg(road) as reflyr:
        sref, transform = reflyr.get_transform_from_epsg(reflyr.spatial_ref, epsg_proj)

    for dataset, label in in_data.items():
        ds = get_geometry_unary_union(dataset)
        # sref, transform = ds.get_transform_from_epsg(ds.spatial_ref, epsg_proj)

        counter = 1
        for igoid, window in windows.items():
            print(f'summarizing on igo {counter} of {len(windows)} for dataset {label}')

            lyr_cl = window[0].intersection(ds)
            # project clipped layer to utm epsg

            # leave null if layer is empty?
            if lyr_cl.is_empty is True:
                continue
            else:
                if lyr_cl.type in ['MultiLineString', 'LineString']:
                    ogrlyr = VectorBase.shapely2ogr(lyr_cl)
                    lyr_clipped = VectorBase.ogr2shapely(ogrlyr, transform=transform)
                    lb1 = label + '_len'
                    lb2 = label + '_dens'
                    conn.execute(f'UPDATE IGOAttributes SET {lb1} = {lyr_clipped.length} WHERE IGOID = {igoid}')
                    if window[2] == 0.0:
                        conn.commit()
                        continue
                    else:
                        conn.execute(f'UPDATE IGOAttributes SET {lb2} = {lyr_clipped.length / window[2]} WHERE IGOID = {igoid}')
                    conn.commit()
                if lyr_cl.type in ['MultiPoint']:
                    lb1 = label + '_ct'
                    lb2 = label + '_dens'
                    conn.execute(f'UPDATE IGOAttributes SET {lb1} = {len(lyr_cl.geoms)} WHERE IGOID = {igoid}')
                    if window[2] == 0.0:
                        conn.commit()
                        continue
                    else:
                        conn.execute(f'UPDATE IGOAttributes SET {lb2} = {len(lyr_cl.geoms) / window[2]} WHERE IGOID = {igoid}')
                    conn.commit()
                if lyr_cl.type in ['Point']:
                    lb1 = label + '_ct'
                    lb2 = label + '_dens'
                    if lyr_cl.is_empty is True:
                        conn.execute(f'UPDATE IGOAttributes SET {lb1} = 0 WHERE IGOID = {igoid}')
                        conn.execute(f'UPDATE IGOAttributes SET {lb2} = 0 WHERE IGOID = {igoid}')
                    else:
                        conn.execute(f'UPDATE IGOAttributes SET {lb1} = 1 WHERE IGOID = {igoid}')
                        if window[2] == 0.0:
                            conn.commit()
                            continue
                        else:
                            conn.execute(f'UPDATE IGOAttributes SET {lb2} = {1 / window[2]} WHERE IGOID = {igoid}')
            counter += 1


# conn.execute('CREATE INDEX ix_igo_levelpath on anthro_igo_geom(LevelPathI)')
# conn.execute('CREATE INDEX ix_igo_segdist on anthro_igo_geom(seg_distance)')
# conn.execute('CREATE INDEX ix_igo_size on anthro_igo_geom(stream_size)')
# conn.commit()
# conn = None
# conn = sqlite3.connect(os.path.dirname(dgo))
# conn.execute('CREATE INDEX ix_dgo_levelpath on dgo(LevelPathI)')
# conn.execute('CREATE INDEX ix_dgo_segdist on dgo(seg_distance)')
# conn.commit()
