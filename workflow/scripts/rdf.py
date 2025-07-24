#!/usr/bin/env python

import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import functools
import argparse
import re
import logging
import warnings
from pathlib import Path
from typing import List, Dict, Union, List


warnings.filterwarnings("ignore", category=UserWarning)
plt.style.use("dark_background")

def merge_reduced(result_df: pd.DataFrame,
                  df: pd.DataFrame,
                  map_cols: Dict[str, str],
                  reduction: str,
                  merge_on: Union[List[str], str] = ['ImageNumber', 'ObjectNumber'],
                  how: str='inner',
                  ):
    '''Merge df into result_df, reducing as needed.
    Only columns in map_cols are considered, and are renamed'''
    return result_df.merge(
        df.groupby(merge_on)[list(map_cols.keys())].aggregate(reduction).reset_index().rename(columns=map_cols),
        on=merge_on,
        how=how,
    )

def merge_result(result_df: pd.DataFrame,
                 df: pd.DataFrame,
                  map_cols: Dict[str, str],
                  merge_on: Union[List[str], str] = ['ImageNumber', 'ObjectNumber'],
                  how: str='inner',
                  ):
    return result_df.merge(
        df[merge_on + list(map_cols.keys())].rename(columns=map_cols),
        on=merge_on,
        how=how,
    )

def analyze(
    datafile,
    parsers=[],
    extra_columns=[],
    previous_result=None,
    merge_fcn=None,
    region='',
    reduce=False,
    ):
    for parser in parsers:
        parser.peek_file(datafile)
    data = pd.read_csv(datafile,
                       usecols=sum(
                        (parser.get_columns() for parser in parsers),
                        extra_columns,
                       )
                       )

    extra_data = []
    for parser in parsers:
        extra = parser.analyze(data)
        if extra is not None:
            extra_data.append(extra)

    if previous_result is not None and merge_fcn:
        for parser in parsers:
            if reduce:
                previous_result = parser.merge_reduced_result(
                    previous_result, data, region, merge_fcn)

            else:
                previous_result = parser.merge_result(
                    previous_result, data, region, merge_fcn)
        return previous_result, extra_data

    return data, extra_data

class CellProfilerParser():
    def peek_file(self, datafile):
        # optionally open and inspect file if e.g. needed to get columns
        pass

    def get_columns(self) -> List[str]:
        return []

    def analyze(self, df) -> Union[pd.DataFrame, None]:
        '''Add derived columns to df in place, return new df if needed.'''
        pass

    def merge_result(self, result, df, region, merge_fcn):
        '''Merge df with result for the given region.
        merge_fcn will be called with result, df, map_cols.'''
        pass

    def merge_reduced_result(self, result, df, region, merge_fcn):
        '''Merge df with result for the given region.
        merge_fcn will be called with result, df, map_cols, reduction.'''
        pass

class RDFParser(CellProfilerParser):
    def __init__(self, id_vars=[]):
        self.columns = []
        self.id_vars = id_vars

    def peek_file(self, datafile):
        self.columns = [
            column for column in open(datafile).readline().strip().split(',')
                if column.startswith('RDF_')
        ]

    def get_columns(self) -> List[str]:
        return self.columns + self.id_vars

    def analyze(self, df) -> Union[pd.DataFrame, None]:
        rdf_raw = df.melt(id_vars=self.id_vars)

        intensity = rdf_raw[rdf_raw.variable.str.startswith('RDF_Intensity')].reset_index(drop=True)
        extract = intensity.variable.str.extract(r'RDF_Intensity_C(\d)_R([-0-9]+)')
        intensity = intensity.assign(
            channel=extract[0].astype(int),
            radius=extract[1].astype(int),
        ).rename(columns={'value': 'intensity'}).drop(columns='variable')

        counts = rdf_raw[rdf_raw.variable.str.startswith('RDF_Count')].reset_index(drop=True)
        extract = counts.variable.str.extract(r'RDF_Counts_R([-0-9]+)')

        counts = counts.assign(
            radius=extract[0].astype(int)
        ).rename(columns={'value': 'counts'}).drop(columns='variable')

        return intensity.merge(counts, on=self.id_vars + ['radius'])


    def merge_result(self, result, df, region, merge_fcn):
        return result

    def merge_reduced_result(self, result, df, region, merge_fcn):
        return result

class CorrelationParser(CellProfilerParser):
    def __init__(self, measures, reduce=False):
        self.columns = []
        self.measures = measures
        self.reduce = reduce

    def peek_file(self, datafile):
        measures = tuple(f'Correlation_{measure}' for measure in self.measures)
        self.columns = [
            column for column in open(datafile).readline().strip().split(',')
            if column.startswith(measures)
        ]

    def get_columns(self) -> List[str]:
        return self.columns + (['AreaShape_Area'] if self.reduce else [])

    def merge_result(self, result, df, region, merge_fcn):
        map_cols = {
            column: f'{region}_{column[12:]}'
            for column in self.columns
        }
        return merge_fcn(result, df, map_cols)

    def merge_reduced_result(self, result, df, region, merge_fcn):
        map_cols = {
            column: f'Mean_{region}_{column[12:]}'
            for column in self.columns
        }
        map_cols['AreaShape_Area'] = '_tmp_total_area'
        result = merge_fcn(result, df, map_cols, 'sum')
        result[list(map_cols.values())] /= result['_tmp_total_area'].to_numpy()[:, None]
        result = result.drop(columns='_tmp_total_area')

        return result

class RimEnrichmentParser(CellProfilerParser):
    def __init__(self, images: list, area_normalization, bins, total_bins, ignore_last=0):
        self.images = images
        self.area_normalization = area_normalization
        self.bins = bins
        self.total_bins = total_bins
        self.ignore_last = ignore_last


    def _bins(self):
        return range(self.total_bins, self.total_bins-self.bins, -1)

    def get_columns(self) -> List[str]:
        return [
            f'RadialDistribution_FracAtD_{image}_{bin - self.ignore_last}of{self.total_bins}'
            for image in (self.images + [self.area_normalization])
            for bin in self._bins()
        ]

    def analyze(self, df) -> Union[pd.DataFrame, None]:
        relative_area = df[[
            f'RadialDistribution_FracAtD_{self.area_normalization}'
            f'_{bin - self.ignore_last}of{self.total_bins}'
                for bin in self._bins()
        ]].sum(axis=1)

        for image in self.images:
            df[f'{image}_Rim_Enrichment'] = df[[
                f'RadialDistribution_FracAtD_{image}_{bin - self.ignore_last}of{self.total_bins}'
                for bin in self._bins()
            ]].sum(axis=1) / relative_area

    def merge_result(self, result, df, region, merge_fcn):
        '''Merge df with result for the given region.
        merge_fcn will be called with result, df, map_cols.'''
        map_cols = {
            f'{image}_Rim_Enrichment': f'{region}_{image}_Rim_Enrichment'
            for image in self.images
        }

        return merge_fcn(result, df, map_cols)


    def merge_reduced_result(self, result, df, region, merge_fcn):
        '''Merge df with result for the given region.
        merge_fcn will be called with result, df, map_cols, reduction.'''
        map_cols = {
            f'{image}_Rim_Enrichment': f'Mean_{region}_{image}_Rim_Enrichment'
            for image in self.images
        }

        return merge_fcn(result, df, map_cols, 'mean')

class IntensityParser(CellProfilerParser):
    def __init__(self, measures=['Mean'], images=list(), locations=list(), total_intens=False):
        self.measures = measures
        self.images = images
        self.locations = locations
        self.total_intens = total_intens

    def get_columns(self) -> List[str]:
        result = []

        if self.total_intens:
            result = ['AreaShape_Area']
            self.measures.append('Mean')

        result += [
            f'Intensity_{measure}Intensity_{image}'
                for measure in self.measures
                for image in self.images
        ]
        if self.locations:
            result += [
                f'Location_CenterMassIntensity_{coord}_{image}'
                for coord in ('X', 'Y')
                for image in self.images
            ]

        return result

    def analyze(self, df) -> Union[pd.DataFrame, None]:
        '''Add derived columns to df in place, return new df if needed.'''
        if self.total_intens:
            for image in self.images:
                df[f'Intensity_TotalIntensity_{image}'] = (
                    df[f'Intensity_MeanIntensity_{image}']
                        * df['AreaShape_Area'])

    def _map_cols(self, df, prefix):
        map_cols = {
            column: column.replace('Intensity', prefix, 1)
            for column in df.columns
            if column.startswith('Intensity')
        }

        if self.locations:
            map_cols.update({
                column: column.replace('Location', prefix)
                for column in df.columns
                if column.startswith('Location')
            })

        return map_cols


    def merge_result(self, result, df, region, merge_fcn):
        '''Merge df with result for the given region.
        merge_fcn will be called with result, df, map_cols.'''
        map_cols = self._map_cols(df, region)
        return merge_fcn(result, df, map_cols)

    def merge_reduced_result(self, result, df, region, merge_fcn):
        '''Merge df with result for the given region.
        merge_fcn will be called with result, df, map_cols, reduction.'''

        map_cols = self._map_cols(df, f'Mean_{region}')

        result = merge_fcn(result, df, map_cols, 'mean')

        if self.total_intens:
            map_cols = {
                'AreaShape_Area': '_tmp_total_area',
            }
            map_cols.update({
                f'Intensity_TotalIntensity_{image}': f'Total_{region}_TotalIntensity_{image}'
                for image in self.images
            })

            result = merge_fcn(result, df, map_cols, 'sum')

            for image in self.images:
                result[f'MeanWeighted_{region}_Intensity_{image}'] = (
                    result[f'Total_{region}_TotalIntensity_{image}'] / 
                    result['_tmp_total_area']
                )

            result = result.drop(columns='_tmp_total_area')

        return result
    
class BlankParser(CellProfilerParser):
    def __init__(self, columns=list()):
        self.columns = columns

    def get_columns(self):
        return self.columns

    '''Pass through any columns, useful for joining datasets'''
    def merge_result(self, result, df, region, merge_fcn):
        '''Merges all columns in df.'''
        return merge_fcn(result, df, dict(zip(self.columns, self.columns)))

    def merge_reduced_result(self, result, df, region, merge_fcn):
        raise ValueError('Operation not allowed for BlankParser')

class CountingParser(CellProfilerParser):
    '''Count number of observations for merging.'''
    def get_columns(self) -> List[str]:
        return ['ObjectNumber']

    def merge_result(self, result, df, region, merge_fcn):
        '''Do nothing on non-reduced merge.'''
        raise ValueError('Operation not allowed for CountingParser')

    def merge_reduced_result(self, result, df, region, merge_fcn):
        map_cols = {'ObjectNumber': f'Count_{region}'}
        return merge_fcn(result, df, map_cols, 'count')

class ImageParser(CellProfilerParser):
    def __init__(self, regex=None, debug_regex=False):
        self.regex = regex
        self.map_cols = []
        self.debug = debug_regex

    def get_columns(self) -> List[str]:
        return ['Metadata_FileLocation', 'Metadata_Series', 'ImageNumber']

    def analyze(self, df) -> Union[pd.DataFrame, None]:
        if self.regex is None:
            return
        parsed = df['Metadata_FileLocation'].str.extract(self.regex)

        if self.debug and parsed.isna().any(axis=None):
            print(df.loc[parsed.isna().any(axis=1), 'Metadata_FileLocation'].unique())
            raise ValueError("Regex failed")

        self.map_cols = {column: column for column in parsed.columns}
        self.map_cols['Metadata_FileLocation'] = 'Metadata_FileLocation'

        # joining doesn't modify the df in place, use columns instead
        for col in parsed.columns:
            df[col] = parsed[col]

    def merge_result(self, result, df, region, merge_fcn):
        return merge_fcn(result, df, self.map_cols)

    def merge_reduced_result(self, result, df, region, merge_fcn):
        raise ValueError('Operation not allowed for FilelocationParser')

class ShapeParser(CellProfilerParser):
    def get_columns(self):
        return ['AreaShape_Area',
                'AreaShape_Eccentricity',
                'AreaShape_Perimeter',
                ]

    def analyze(self, df):
        df['AreaShape_Circularity'] = (
            4 * np.pi * df['AreaShape_Area'] /
                df['AreaShape_Perimeter'] ** 2
        )

    def merge_result(self, result, df, region, merge_fcn):
        columns = self.get_columns() + ['AreaShape_Circularity']
        map_cols = {
            column: column.replace('AreaShape', region)
            for column in columns
        }

        return merge_fcn(result, df, map_cols)

    def merge_reduced_result(self, result, df, region, merge_fcn):
        map_cols = {
            f'AreaShape_{measure}': f'Mean_{region}_{measure}'
            for measure in ('Area', 'Circularity', 'Perimeter', 'Eccentricity')
        }
        result = merge_fcn(result, df, map_cols, 'mean')

        map_cols = {
            'AreaShape_Area': f'Total_{region}_Area',
        }
        result = merge_fcn(result, df, map_cols, 'sum')

        return result

parser = argparse.ArgumentParser()

parser.add_argument('--regex', type=str)
parser.add_argument("--output-dir", type=str, help="Output directory for results")
parser.add_argument("--input-dir", type=str, help="Input directory with cellprofiler outputs")
parser.add_argument("--log-file", type=str, default=None, help="Log file to write debug messages")

args = parser.parse_args()

regex = args.regex
output_directory = args.output_dir
input_directory = args.input_dir
log_file = args.log_file

if log_file:
    logging.basicConfig(
        filename=log_file,
        filemode='a',
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

else:
    print("No log file specified...")

if not output_directory:
    logging.error("Output directory not specified.")
    raise ValueError("Output directory must be specified.")

if not input_directory:
    logging.error("Input directory not specified.")
    raise ValueError("Input directory must be specified.")

pattern = re.compile("{0}".format(regex))

def read_data(directory, regex=None, dfc=True, bins=4, debug_regex=False):
    directory = Path(directory)
    # some variables reused below - Specifies the key columns to carry through merges
    extra_columns = ['ImageNumber', 'Parent_MergedGC']
    
    extras = {
        'extra_columns': extra_columns,
        'reduce': True,
        'merge_fcn': functools.partial(merge_reduced, merge_on=extra_columns)
    }
    
    extras_left = {
        'extra_columns': extra_columns,
        'reduce': True,
        'merge_fcn': functools.partial(merge_reduced, merge_on=extra_columns, how='left')
    }

    logging.info(f"Merging results from csv files")

    # Parse information from filename using the provided regex
    result, _ = analyze(directory / 'Image.csv', 
                              parsers=[
                                  ImageParser(regex, debug_regex=debug_regex),                              
                              ])

    logging.info(f"Parsed image metadata from {directory / 'Image.csv'}")

    result, _ = analyze(directory / 'MergedGC.csv',
                              previous_result=result,
                              parsers=[BlankParser(['ObjectNumber'])],
                              extra_columns=['ImageNumber', ],
                              merge_fcn=functools.partial(merge_result, merge_on=['ImageNumber'], how='left'),
                             )
    result = result.rename(columns={'ObjectNumber': 'Parent_MergedGC'})

    logging.info(f"Merging results from {directory}/MergedGC.csv")

    logging.info(f"Merging results from csv files")
    # Measure features from GC objects
    result, _ = analyze(directory / 'InitialGC.csv',
                              previous_result=result,
                              parsers=[
                                  ShapeParser(),
                                  CountingParser(),
                              ],
                              region='GC',
                              **extras,
                             )
    logging.info(f'Parsed initial GC objects from {directory / "InitialGC.csv"}')

    # RDF result is in the eroded GC area
    result, extra = analyze(directory / 'ErodedGC.csv',
                              previous_result=result,
                              parsers=[
                                  RDFParser(id_vars=['ImageNumber', 'ObjectNumber', 'Parent_MergedGC']),
                              ],
                              region='GC',
                              **extras,
                             )
    
    logging.info(f'Parsed RDF from {directory / "ErodedGC.csv"}')
    
    # Measure features from FC objects
    result, _ = analyze(directory / 'InitialFC.csv',
                              previous_result=result,
                              parsers=[
                                  CountingParser(),
                                  ShapeParser(),
                              ],
                              region='FC',
                              **extras_left
                             )
    
    logging.info(f'Merging results from {directory / "InitialFC.csv"}')
    return result, extra

full_data, extra_data = read_data(input_directory, pattern, bins=4)

rdf, = extra_data

# need to average GCs from each parent
rdf_avg = []
groups = ['ImageNumber', 'Parent_MergedGC', 'channel', 'radius']
for name, dat in rdf.groupby(groups):
    rdf_avg.append(dict(
        zip(groups, name),
        intensity=(((dat['intensity'] * dat['counts']).fillna(0).sum()) / dat['counts'].sum()),
        counts=dat['counts'].sum(),
    ))
rdf_avg = pd.DataFrame(rdf_avg)

merged = rdf_avg.merge(full_data[['ImageNumber', 'Parent_MergedGC', 'time', 'treatment']], 
                   on=['ImageNumber', 'Parent_MergedGC'])
# average raw values based on target and ssu, estimate sem from total variance
groups = ['time', 'treatment', 'channel']
channels = ['', 'SURF6', 'rRNA', 'FC', 'GC']
rdf_data = []

for name, dat in merged.groupby(groups):
    pivoted = dat.pivot_table(columns='radius', values=['intensity', 'counts'], index=['ImageNumber', 'Parent_MergedGC'])
    average_intens = ((pivoted['intensity'] * pivoted['counts']).fillna(0).sum()) / pivoted['counts'].sum()
    mn, mx = pivoted['intensity'].min(), pivoted['intensity'].max()
    normed = (pivoted['intensity'] - mn) / (mx - mn)
    
    sem = np.sqrt((((normed - normed.mean())**2) * pivoted['counts']).sum() / pivoted['counts'].sum()) / np.sqrt(len(normed))
    mn, mx = average_intens.min(), average_intens.max()
    norm_intens = (average_intens - mn) / (mx - mn)
    for radius, vals in pd.concat([norm_intens, average_intens, sem], axis=1).iterrows():
        rdf_data.append(dict(
            zip(groups, name),
            norm_intensity=vals[0],
            intensity=vals[1],
            sem=vals[2],
            channel=channels[name[2]],
            radius=radius,
            distance=radius * 0.0425,
        ))

rdf_data = pd.DataFrame(rdf_data)  
rdf_data['time'] = rdf_data.time.astype(int)

logging.info("Saving the final dataframes to CSV files")
rdf_data.to_csv(f'{input_directory}/rdf_plot_data.csv', index=False)
full_data.to_csv(f'{input_directory}/full_data.csv', index=False)
merged.to_csv(f'{input_directory}/merged_data.csv', index=False)


plot = sns.relplot(data=rdf_data, x='distance', y='intensity', col='channel',
            kind='line', style='treatment', hue='time', facet_kws=dict(sharex=True, sharey=False), palette=sns.color_palette("tab10"))

plot.set(xlabel ="Distance {um}", ylabel = "Intensity")


plot = sns.relplot(data=rdf_data, x='distance', y='norm_intensity', col='channel', 
            kind='line', style='treatment', hue='time', facet_kws=dict(sharex=True, sharey=False), palette=sns.color_palette("tab10"))

plot.set(xlabel ="Distance {um}", ylabel = "Intensity")

plot.savefig(f'{output_directory}/rdf_plot.png', dpi=300, bbox_inches='tight')
logging.info(f"Saved the rdf plot at {output_directory}/rdf_plot.png")

channels = ['SURF6', 'rRNA', 'FC', 'GC']
g = sns.relplot(data=rdf_data, x='distance', y='norm_intensity', col='time', col_wrap=3,
            kind='line', style='treatment', hue='channel', facet_kws=dict(sharex=True, sharey=False), hue_order=channels, palette=sns.color_palette("tab10"))

for time, ax in g.axes_dict.items():
    for channel in channels:
        sub_dat = rdf_data[(rdf_data.channel==channel) & (rdf_data.time == time)]
        ax.fill_between(sub_dat.distance, sub_dat.norm_intensity - sub_dat['sem'], sub_dat.norm_intensity + sub_dat['sem'], alpha=0.3)
        g.set(xlabel ="Distance {um}", ylabel = "Intensity")

g.savefig(f'{output_directory}/rdf_plot_overlay.png', dpi=300, bbox_inches='tight')
logging.info(f"Saved the rdf plot at {output_directory}/rdf_plot_overlay.png")

# get peak position over time
overall_peak_vals = []
for channel, title in enumerate(rdf_data.channel.unique()):
    result = []
    for name, dat in rdf_data[rdf_data.channel == title].groupby(["time",])[
        ["distance", "intensity"]
    ]:
        result.append(
            {
                "com_distance": np.average(
                    dat["distance"],
                    weights=(dat["intensity"] - dat["intensity"].min())
                    / (dat["intensity"].max() - dat["intensity"].min()),
                ),
                "max_distance": dat.loc[dat['intensity'].idxmax(), 'distance'],
                # "time": name[0], # modified because the groupby above results in a tuple
                "time": name, # Python 3.8 allows for this(?)
            }
        )
    peak_vals = pd.DataFrame.from_records(result)
    overall_peak_vals.append(peak_vals.assign(channel=title))
overall_peak_vals = pd.concat(overall_peak_vals, ignore_index=True)

sns.relplot(data=overall_peak_vals, x='time', y='com_distance', col='channel', col_wrap=2, kind='line', hue='channel', palette=sns.color_palette("tab10"))
plt.subplots()
consd = sns.lineplot(data=overall_peak_vals, x='time', y='com_distance', hue='channel')

consd.get_figure().savefig(f'{output_directory}/rdf_com_distances.png', dpi=300, bbox_inches='tight')
logging.info(f"Saved the rdf peak distances at {output_directory}/rdf_com_distances.png")










