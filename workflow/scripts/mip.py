#!/usr/bin/env python

import struct
import numpy as np
import tifffile
import argparse
import os
import re
import logging
from tifffile import imread

def sanitize_filename(filename):
    """
    Sanitize the filename by removing special characters and ensuring it is safe for use.

    Args:
        filename (str): The original filename to sanitize.

    Returns:
        str: A sanitized version of the filename, with special characters  and extension removed
    """
    name, ext = os.path.splitext(filename)
    sanitized_name = re.sub(r'[^A-Za-z0-9_]', '', name)
    return f"{sanitized_name}"

def imagej_metadata_tags(metadata, byteorder):
    header = [{'>': b'IJIJ', '<': b'JIJI'}[byteorder]]
    bytecounts = [0]
    body = []

    def writestring(data, byteorder):
        return data.encode('utf-16' + {'>': 'be', '<': 'le'}[byteorder])

    def writedoubles(data, byteorder):
        return struct.pack(byteorder + ('d' * len(data)), *data)

    def writebytes(data, byteorder):
        return data.tobytes()

    metadata_types = (
        ('Info', b'info', 1, writestring),
        ('Labels', b'labl', None, writestring),
        ('Ranges', b'rang', 1, writedoubles),
        ('LUTs', b'luts', None, writebytes),
        ('Plot', b'plot', 1, writebytes),
        ('ROI', b'roi ', 1, writebytes),
        ('Overlays', b'over', None, writebytes))

    for key, mtype, count, func in metadata_types:
        if key not in metadata:
            continue
        if byteorder == '<':
            mtype = mtype[::-1]
        values = metadata[key]
        if count is None:
            count = len(values)
        else:
            values = [values]
        header.append(mtype + struct.pack(byteorder + 'I', count))
        for value in values:
            data = func(value, byteorder)
            body.append(data)
            bytecounts.append(len(data))

    body = b''.join(body)
    header = b''.join(header)
    data = header + body
    bytecounts[0] = len(header)
    bytecounts = struct.pack(byteorder + ('I' * len(bytecounts)), *bytecounts)
    return ((50839, 'B', len(data), data, True),
            (50838, 'I', len(bytecounts) // 4, bytecounts, True))


parser = argparse.ArgumentParser()

parser.add_argument("-l", "--lut", help="Comma-separated list of colors to use for the LUTs (default: magenta(m), red(r), orange(o), green(g))", default="m,r,o,g")
parser.add_argument("-c", "--channels", help='No. of channels in the image (default: 4)', type=int, default=4)
parser.add_argument("-i", "--input", help="Input file path")
parser.add_argument("-o", "--output", help="Output file path")
parser.add_argument("--log", help="Log file path")

args = parser.parse_args()

# Setup logging
logging.basicConfig(
    filename=args.log,
    filemode='a',
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

colors = args.lut.split(',')

if len(colors) != args.channels:
    logging.error(f"Number of colors ({len(colors)}) does not match the number of channels ({args.channels}).")
    raise ValueError("Mismatch between number of colors and channels.")

input_dir = args.input
output_dir = args.output

for root, dirs, files in os.walk(input_dir):

    for file in files:
        filename, ext = os.path.splitext(file)

        if ext not in ['.tif', '.tiff']:
            logging.error(f"Unsupported file format for: {file}. Skipping...")
            continue
        
        out_file = in_file = file

        image_path = os.path.join(root, in_file)

        logging.info(f"Starting process for {image_path}")

        image = imread(image_path)

        sanitized_name = sanitize_filename(out_file)
        sanitized_name = f"{sanitized_name}_mip{ext}"
        
        output_path = os.path.join(output_dir, sanitized_name)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logging.info(f"Created output directory: {output_dir}")

        mip = np.max(image, axis=0)

        val_range = np.arange(256, dtype='uint8')

        magenta = np.zeros((3, 256), dtype='uint8')
        magenta[[0, 2], :] = val_range

        red = np.zeros((3, 256), dtype='uint8')
        red[0] = val_range

        green = np.zeros((3, 256), dtype='uint8')
        green[1] = val_range

        orange = np.zeros((3, 256), dtype='uint8')
        orange[0, :] = val_range
        orange[1, :] = (val_range * 0.5).astype(np.uint8)

        blue = np.zeros((3, 256), dtype='uint8')
        blue[2] = val_range

        ijtags = None
        lut_colors = []

        for color in colors:
            if color == 'm':
                lut_colors.append(magenta)
            elif color == 'r':
                lut_colors.append(red)
            elif color == 'g':
                lut_colors.append(green)
            elif color == 'o':
                lut_colors.append(orange)
            elif color == 'b':
                lut_colors.append(blue)
            else:
                logging.error(f"Unsupported color '{color}' in LUT.")
                raise ValueError("Unsupported LUT color")

        if image.shape[1] == 5:
            ijtags = imagej_metadata_tags({'LUTs': lut_colors}, '>')
            tifffile.imwrite(output_path,
                            mip,
                            byteorder='>',
                            imagej=True,
                            metadata={'mode': 'color'},
                            extratags=ijtags)

        elif image.shape[1] == 4:
            ijtags = imagej_metadata_tags({'LUTs': lut_colors}, '>')
            tifffile.imwrite(output_path,
                            mip,
                            byteorder='>',
                            imagej=True,
                            metadata={'mode': 'composite'},
                            extratags=ijtags)
        else:
            logging.warning(f"Skipping {in_file}: Unsupported number of channels ({image.shape[2]}).")

        logging.info(f"Output written to: {output_path}")
    logging.info(f"Image processing complete for {input_dir}")
