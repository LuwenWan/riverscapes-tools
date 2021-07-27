"""Name:     Channel Area Tool

   Purpose:  Create a new RS project that generates bankfull and merges with flowareas/waterbody to create channel polygons

   Author:   Kelly Whitehead

   Date:     July 14, 2021"""

import argparse
import os
import sys
import uuid
import traceback
import datetime
import time
from typing import List, Dict

from osgeo import ogr

from rscommons.util import safe_makedirs, parse_metadata, pretty_duration
from rscommons import RSProject, RSLayer, ModelConfig, Logger, dotenv, initGDALOGRErrors
from rscommons import GeopackageLayer
from rscommons.math import safe_eval
from rscommons.raster_buffer_stats import raster_buffer_stats2
from rscommons.vector_ops import get_geometry_unary_union, buffer_by_field, copy_feature_class, merge_feature_classes, remove_holes_feature_class, difference
from rscommons.vbet_network import vbet_network

from channel.channel_report import ChannelReport
from channel.__version__ import __version__

Path = str

DEFAULT_FUNCTION = "0.177 * (a ** 0.397) * (p ** 0.453)"
DEFAULT_FUNCTION_PARAMS = "a=TotDASqKm"

initGDALOGRErrors()

cfg = ModelConfig('http://xml.riverscapes.xyz/Projects/XSD/V1/ChannelArea.xsd', __version__)

LayerTypes = {
    'INPUTS': RSLayer('Inputs', 'INPUTS', 'Geopackage', 'inputs/inputs.gpkg', {
        'FLOWLINES': RSLayer('NHD Flowlines', 'FLOWLINES', 'Vector', 'flowlines'),
        'FLOWAREAS': RSLayer('NHD Flow Areas', 'FLOWAREAS', 'Vector', 'flowareas'),
        'WATERBODY': RSLayer('NHD Water Body Areas', 'WATER_BODIES', 'Vector', 'waterbody'),
    }),
    'INTERMEDIATES': RSLayer('Intermediates', 'Intermediates', 'Geopackage', 'intermediates/intermediates.gpkg', {
        'FILTERED_WATERBODY': RSLayer('NHD Waterbodies (Filtered)', 'FILTERED_WATERBODY', 'Vector', 'waterbody_filtered'),
        'FILTERED_FLOWAREAS': RSLayer('NHD Flow Areas (Filtered)', 'FILTERED_FLOWAREAS', 'Vector', 'flowarea_filtered'),
        'FLOW_AREA_NO_ISLANDS': RSLayer('Flow Areas No Islands', 'FLOW_AREA_NO_ISLANDS', 'Vector', 'flowarea_no_islands'),
        'COMBINED_FA_WB': RSLayer('Combined Flow Area and Waterbody', 'COMBINED_FA_WB', 'Vector', 'combined_fa_wb'),
        'BANKFULL_NETWORK': RSLayer('Bankfull Network', 'BANKFULL_NETWORK', 'Vector', 'bankfull_network'),
        'BANKFULL_POLYGONS': RSLayer('Bankfull Polygons', 'BANKFULL_POLYGONS', 'Vector', 'bankfull_polygons'),
        'DIFFERENCE_POLYGONS': RSLayer('Difference Polygons', 'DIFFERENCE_POLYGONS', 'Vector', 'difference_polygons'),
    }),
    'OUTPUTS': RSLayer('VBET', 'OUTPUTS', 'Geopackage', 'outputs/channel_area.gpkg', {
        'CHANNEL_AREA': RSLayer('Channel Area Polygons', 'CHANNEL_AREA', 'Vector', 'channel_area'),
    }),
    'REPORT': RSLayer('RSContext Report', 'REPORT', 'HTMLFile', 'outputs/channel_area.html')
}


def channel(huc: int,
            flowlines: Path,
            flowareas: Path,
            waterbodies: Path,
            bankfull_function: str,
            bankfull_function_params: dict,
            project_folder: Path,
            reach_code_field: str = None,
            reach_codes: Dict[str, List[str]] = None,
            epsg: int = cfg.OUTPUT_EPSG,
            meta: Dict[str, str] = None):
    """Create a new RS project that generates bankfull and merges with flowareas/waterbody to create channel polygons

    Args:
        huc (int): NHD huc id
        flowlines (Path): NHD flowlines or other stream line network
        flowareas (Path): NHD flowareas or other stream polygon areas
        waterbodies (Path): NHD waterbodies or other water polygon areas
        bankfull_function (str): equation to generate bankfull
        bankfull_function_params (dict): dict with entry for each bankfull equation param as value or fieldname
        project_folder (Path): location to save output project
        reach_code_field (str, optional): field to read for reach code filter for flowlines, flowareas and waterbodies, Defaults to None.
        reach_codes (Dict[str, List[str]], optional): dict entry for flowline, flowarea and waterbody and associated reach codes. Defaults to None.
        epsg ([int], optional): epsg spatial reference value. Defaults to cfg.OUTPUT_EPSG.
        meta (Dict[str, str], optional): metadata key-value pairs. Defaults to None.
    """

    timer = time.time()
    log = Logger('ChannelAreaTool')
    log.info('Starting Channel Area Tool v.{}'.format(cfg.version))
    log.info('Using Equation: "{}" and params: "{}"'.format(bankfull_function, bankfull_function_params))

    meta['Bankfull Equation'] = bankfull_function
    for layer, codes in reach_codes.items():
        meta[f'{layer} Reach Codes'] = str(codes)

    project, _realization, proj_nodes = create_project(huc, project_folder, meta)

    # Input Preparation
    inputs_gpkg_path = os.path.join(project_folder, LayerTypes['INPUTS'].rel_path)
    intermediates_gpkg_path = os.path.join(project_folder, LayerTypes['INTERMEDIATES'].rel_path)
    output_gpkg_path = os.path.join(project_folder, LayerTypes['OUTPUTS'].rel_path)

    GeopackageLayer.delete(inputs_gpkg_path)
    GeopackageLayer.delete(intermediates_gpkg_path)

    if flowlines is not None:
        proj_flowlines = os.path.join(inputs_gpkg_path, LayerTypes['INPUTS'].sub_layers['FLOWLINES'].rel_path)
        copy_feature_class(flowlines, proj_flowlines, epsg=epsg)

    if flowareas is not None:
        proj_flowareas = os.path.join(inputs_gpkg_path, LayerTypes['INPUTS'].sub_layers['FLOWAREAS'].rel_path)
        copy_feature_class(flowareas, proj_flowareas, epsg=epsg)

    if waterbodies is not None:
        proj_waterbodies = os.path.join(inputs_gpkg_path, LayerTypes['INPUTS'].sub_layers['WATERBODY'].rel_path)
        copy_feature_class(waterbodies, proj_waterbodies, epsg=epsg)

    project.add_project_geopackage(proj_nodes['Inputs'], LayerTypes['INPUTS'])

    # Generate Intermediates
    if proj_flowareas is not None:
        log.info('Filtering flowarea polygons')
        filtered_flowareas = os.path.join(intermediates_gpkg_path, LayerTypes['INTERMEDIATES'].sub_layers['FILTERED_FLOWAREAS'].rel_path)
        fcode_filter = ""
        if reach_code_field is not None and reach_codes['flowarea'] is not None:
            fcode_filter = f"{reach_code_field} = " + f" or {reach_code_field} = ".join([f"'{fcode}'" for fcode in reach_codes['flowarea']])
        copy_feature_class(proj_flowareas, filtered_flowareas, attribute_filter=fcode_filter)

        log.info('Removing flowarea islands')
        filtered_flowarea_no_islands = os.path.join(intermediates_gpkg_path, LayerTypes['INTERMEDIATES'].sub_layers['FLOW_AREA_NO_ISLANDS'].rel_path)
        remove_holes_feature_class(filtered_flowareas, filtered_flowarea_no_islands)

    if proj_waterbodies is not None:
        log.info('Filtering waterbody polygons')
        filtered_waterbodies = os.path.join(intermediates_gpkg_path, LayerTypes['INTERMEDIATES'].sub_layers['FILTERED_WATERBODY'].rel_path)
        fcode_filter = ""
        if reach_code_field is not None and reach_codes['waterbody'] is not None:
            fcode_filter = f"{reach_code_field} = " + f" or {reach_code_field} = ".join([f"'{fcode}'" for fcode in reach_codes['waterbody']])

        copy_feature_class(waterbodies, filtered_waterbodies, attribute_filter=fcode_filter)

    combined_flow_polygons = os.path.join(intermediates_gpkg_path, LayerTypes['INTERMEDIATES'].sub_layers['COMBINED_FA_WB'].rel_path)
    if filtered_waterbodies is not None and filtered_flowarea_no_islands is not None:
        log.info('Merging waterbodies and flowareas')
        merge_feature_classes([filtered_waterbodies, filtered_flowarea_no_islands], combined_flow_polygons)
    elif filtered_flowarea_no_islands is not None:
        log.info('No waterbodies found, copying flowareas')
        copy_feature_class(filtered_flowarea_no_islands, combined_flow_polygons)
    elif filtered_waterbodies is not None:
        log.info('No flowareas found, copying waterbodies')
        copy_feature_class(filtered_waterbodies, combined_flow_polygons)
    else:
        log.info('No waterbodies or flowareas in project')
        combined_flow_polygons = None

    bankfull_polygons = None
    if proj_flowlines is not None:
        log.info('Filtering bankfull flowline network')
        bankfull_network = os.path.join(intermediates_gpkg_path, LayerTypes['INTERMEDIATES'].sub_layers['BANKFULL_NETWORK'].rel_path)
        if reach_code_field is not None and reach_codes['flowline'] is not None:
            vbet_network(proj_flowlines, None, bankfull_network, epsg, reach_codes['flowline'], reach_code_field)
        else:
            copy_feature_class(proj_flowlines, bankfull_network)

        if bankfull_function is not None:
            log.info("Calculing bankfull width")
            calculate_bankfull(bankfull_network, 'bankfull_m', bankfull_function, bankfull_function_params)
            bankfull_polygons = os.path.join(intermediates_gpkg_path, LayerTypes['INTERMEDIATES'].sub_layers['BANKFULL_POLYGONS'].rel_path)
            buffer_by_field(bankfull_network, bankfull_polygons, "bankfull_m", cfg.OUTPUT_EPSG, centered=True)

    output_channel_area = os.path.join(output_gpkg_path, LayerTypes['OUTPUTS'].sub_layers['CHANNEL_AREA'].rel_path)
    if bankfull_polygons is not None and combined_flow_polygons is not None:
        log.info('Combining Bankfull polygons with flowarea/waterbody polygons into final channel area output')
        channel_polygons = os.path.join(intermediates_gpkg_path, LayerTypes['INTERMEDIATES'].sub_layers['DIFFERENCE_POLYGONS'].rel_path)
        difference(combined_flow_polygons, bankfull_polygons, channel_polygons, cfg.OUTPUT_EPSG)
        merge_feature_classes([channel_polygons, combined_flow_polygons], output_channel_area)
    elif bankfull_polygons is not None:
        log.info('Copying Bankfull polygons into final channel area output')
        copy_feature_class(bankfull_polygons, output_channel_area)
    elif combined_flow_polygons is not None:
        log.info('Copying filtered flowarea/waterbody polygons into final channel area output')
        copy_feature_class(combined_flow_polygons, output_channel_area)
    else:
        log.warning('No output channel polygons were produced')

    # Now add our Geopackages to the project XML
    project.add_project_geopackage(proj_nodes['Intermediates'], LayerTypes['INTERMEDIATES'])
    project.add_project_geopackage(proj_nodes['Outputs'], LayerTypes['OUTPUTS'])

    # Processing time in hours
    ellapsed_time = time.time() - timer
    project.add_metadata({"ProcTimeS": "{:.2f}".format(ellapsed_time)})
    project.add_metadata({"ProcTimeHuman": pretty_duration(ellapsed_time)})

    # Report
    report_path = os.path.join(project.project_dir, LayerTypes['REPORT'].rel_path)
    project.add_report(proj_nodes['Outputs'], LayerTypes['REPORT'], replace=True)
    report = ChannelReport(report_path, project)
    report.write()

    log.info('Channel Area Completed Successfully')


def calculate_bankfull(network_layer: Path, out_field: str, eval_fn: str, function_params: dict):
    """caluclate bankfull value for each feature in network layer

    Args:
        network_layer (Path): netowrk layer
        out_field (str): field to store bankfull values
        eval_fn (str): equation to use in eval function
        function_params (dict): parameters to use in eval function
    """
    with GeopackageLayer(network_layer, write=True) as layer:

        layer.create_field(out_field, ogr.OFTReal)

        layer.ogr_layer.StartTransaction()
        for feat, *_ in layer.iterate_features("Calculating bankfull"):

            fn_params = {}
            for param, value in function_params.items():
                if isinstance(value, str):
                    field_value = feat.GetField(value)
                    fn_params[param] = field_value if field_value is not None else 0
                else:
                    fn_params[param] = value
            # eval seems to mutate the fn_params object so we pass in a copy so that we can report on the errors if needed
            result = safe_eval(eval_fn, fn_params)
            feat.SetField(out_field, result)
            layer.ogr_layer.SetFeature(feat)

        layer.ogr_layer.CommitTransaction()


def create_project(huc: int, output_dir: Path, meta: dict = None):
    """Create channel area project

    Args:
        huc (int): NHD huc id
        output_dir (Path): output directory for new project
        meta (dict, optional): key-value pair of project metadata. Defaults to None.

    Returns:
        RSProject, realization, proj_nodes
    """
    project_name = 'Channel Area for HUC {}'.format(huc)
    project = RSProject(cfg, output_dir)
    project.create(project_name, 'ChannelArea')

    project.add_metadata({
        'HUC{}'.format(len(huc)): str(huc),
        'HUC': str(huc),
        'ChannelAreaVersion': cfg.version,
        'ChannelAreaTimestamp': str(int(time.time()))
    })

    # Incorporate project metadata to the riverscapes project
    if meta is not None:
        project.add_metadata(meta)

    realizations = project.XMLBuilder.add_sub_element(project.XMLBuilder.root, 'Realizations')
    realization = project.XMLBuilder.add_sub_element(realizations, 'ChannelArea', None, {
        'id': 'ChannelArea',
        'dateCreated': datetime.datetime.now().isoformat(),
        'guid': str(uuid.uuid1()),
        'productVersion': cfg.version
    })

    project.XMLBuilder.add_sub_element(realization, 'Name', project_name)
    proj_nodes = {
        'Inputs': project.XMLBuilder.add_sub_element(realization, 'Inputs'),
        'Intermediates': project.XMLBuilder.add_sub_element(realization, 'Intermediates'),
        'Outputs': project.XMLBuilder.add_sub_element(realization, 'Outputs')
    }

    # Make sure we have these folders
    proj_dir = os.path.dirname(project.xml_path)
    safe_makedirs(os.path.join(proj_dir, 'inputs'))
    safe_makedirs(os.path.join(proj_dir, 'intermediates'))
    safe_makedirs(os.path.join(proj_dir, 'outputs'))

    project.XMLBuilder.write()
    return project, realization, proj_nodes


def main():
    """Create a new RS project that generates bankfull and merges with flowareas/waterbody to create channel polygons
    """
    parser = argparse.ArgumentParser(
        description='Riverscapes Channel Area Tool',
        # epilog="This is an epilog"
    )
    parser.add_argument('huc', help='NHD huc id', type=str)
    parser.add_argument('flowlines', help='NHD flowlines feature class', type=str)
    parser.add_argument('flowareas', help='NHD flowareas feature class', type=str)
    parser.add_argument('waterbodies', help='NHD waterbodies', type=str)
    parser.add_argument('output_dir', help='Folder where output VBET project will be created', type=str)
    parser.add_argument('--bankfull_function', help='width field in flowlines feature class (e.g. BFWidth). Default: "{}"'.format(DEFAULT_FUNCTION), type=str, default=DEFAULT_FUNCTION)
    parser.add_argument('--bankfull_function_params', help='Field that contains reach code (e.g. FCode). Omitting this option retains all features. Default: "{}"'.format(DEFAULT_FUNCTION_PARAMS), type=str, default=DEFAULT_FUNCTION_PARAMS)
    parser.add_argument('--reach_code_field', help='Field that contains reach code (e.g. FCode). Omitting this option retains all features.', type=str)
    parser.add_argument('--flowline_reach_codes', help='Comma delimited reach codes (FCode) to retain when filtering features. Omitting this option retains all features.', type=str)
    parser.add_argument('--flowarea_reach_codes', help='Comma delimited reach codes (FCode) to retain when filtering features. Omitting this option retains all features.', type=str)
    parser.add_argument('--waterbody_reach_codes', help='Comma delimited reach codes (FCode) to retain when filtering features. Omitting this option retains all features.', type=str)
    parser.add_argument('--precip', help='mean annual precipiation in cm')
    parser.add_argument('--prism_data')
    parser.add_argument('--huc8boundary')
    parser.add_argument('--epsg', help='output epsg', type=int)
    parser.add_argument('--meta', help='riverscapes project metadata as comma separated key=value pairs', type=str)
    parser.add_argument('--verbose', help='(optional) a little extra logging ', action='store_true', default=False)
    parser.add_argument('--debug', help='Add debug tools for tracing things like memory usage at a performance cost.', action='store_true', default=False)

    args = dotenv.parse_args_env(parser)

    # make sure the output folder exists
    safe_makedirs(args.output_dir)

    # Initiate the log file
    log = Logger('Channel Area')
    log.setup(logPath=os.path.join(args.output_dir, 'channel_area.log'), verbose=args.verbose)
    log.title('Riverscapes Channel Area For HUC: {}'.format(args.huc))

    meta = parse_metadata(args.meta)
    bankfull_params = parse_metadata(args.bankfull_function_params)

    reach_codes = {}
    reach_codes['flowline'] = args.flowline_reach_codes.split(',') if args.flowline_reach_codes else None
    reach_codes['flowarea'] = args.flowarea_reach_codes.split(',') if args.flowarea_reach_codes else None
    reach_codes['waterbody'] = args.waterbody_reach_codes.split(',') if args.waterbody_reach_codes else None

    if args.precip is not None:
        precip = args.precip
    elif args.prism_data is not None and args.huc8boundary is not None:
        polygon = get_geometry_unary_union(args.huc8boundary, epsg=cfg.OUTPUT_EPSG)
        precip = raster_buffer_stats2({1: polygon}, args.prism_data)[1]['Mean'] / 10
        log.info('Mean annual precipitation for HUC {} is {} cm'.format(args.huc, precip))

    else:
        raise ValueError('precip or prism_data and huc8boundary not provided.')

    bankfull_params['p'] = precip

    try:
        if args.debug is True:
            from rscommons.debug import ThreadRun
            memfile = os.path.join(args.output_dir, 'vbet_mem.log')
            retcode, max_obj = ThreadRun(channel, memfile, args.huc, args.flowlines, args.flowareas, args.waterbodies, args.bankfull_function, bankfull_params, args.output_dir, args.reach_code_field, reach_codes, meta=meta)
            log.debug('Return code: {}, [Max process usage] {}'.format(retcode, max_obj))

        else:
            channel(args.huc, args.flowlines, args.flowareas, args.waterbodies, args.bankfull_function, bankfull_params, args.output_dir, args.reach_code_field, reach_codes, meta=meta)

    except Exception as e:
        log.error(e)
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
