import os
from os.path import dirname, realpath, join
import sys
from sys import argv, exit
from pathlib import Path

import pickle
import csv
import nibabel as nib
import numpy as np
import pandas as pd
import cv2
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from .uuuuuu import make_contour_img, render_volume, render_small_volume


def _make_label(label_file_path, excel_file_path):
    label_file_path = '/Users/jingyig/Work/Kavli/Waxholm_Rat/WHS_SD_rat_atlas_v4.label'
    excel_file_path = '/Users/jingyig/Work/Kavli/Waxholm_Rat/WHS SD rat brain atlas v4 labels for MBAT.xlsx'

    xl_file = pd.ExcelFile(excel_file_path)
    dfs = {sheet_name: xl_file.parse(sheet_name) for sheet_name in xl_file.sheet_names}
    dfs_keys = list(dfs.keys())
    if len(dfs_keys) != 1:
        raise Exception('need to be only 1 sheet')

    df = dfs[dfs_keys[0]]

    index = []
    level = []
    name = []

    for i in range(df.shape[0]):
        da_line = df.iloc[i].values
        for j in range(df.shape[1]):
            if ~np.isnan(da_line[j]):
                print(da_line[j])
                index.append(da_line[j])
                level.append(j)
                name.append(da_line[j+1])
                break

    index = np.ravel(index).astype(int)
    abv = df['Abbreviation'].values[:len(index)]
    parent = df['Parent'].values[:len(index)].astype(int)

    file = open(label_file_path, 'rb')
    lines = file.readlines()
    file.close()

    for i in range(len(lines)):
        da_line = lines[i].decode()
        if da_line[0] == '#':
            continue
        start_line = i
        break

    lindex = []
    red = []
    green = []
    blue = []
    lname = []
    for i in range(start_line, len(lines)):
        da_line = lines[i].decode()
        print(da_line)
        da_elements = da_line.split('"')
        da_numbers = da_elements[0].split()
        lindex.append(int(da_numbers[0]))
        red.append(int(da_numbers[1]))
        green.append(int(da_numbers[2]))
        blue.append(int(da_numbers[3]))
        lname.append(da_elements[1])

    lindex = np.ravel(lindex)
    red = np.ravel(red)
    green = np.ravel(green)
    blue = np.ravel(blue)

    colors = np.zeros((len(index), 3))
    colors[:] = np.nan

    for i in range(1, len(lname)):
        print(i)
        if lindex[i] not in index:
            raise Exception('not matching')

    for i in range(len(index)):
        if index[i] > 600:
            if index[i] == 1000:
                colors[i] = np.array([50, 168, 82])
            elif index[i] in [1001, 1050, 1002, 1003, 1004, 1005, 1006, 1051, 1007, 1008, 1009, 1010, 1011, 1012]:
                colors[i] = np.array([255, 255, 255])
            elif index[i] == 1048:
                colors[i] = np.array([114, 126, 186])
            elif index[i] == 1049:
                colors[i] = np.array([16, 79, 24])
            else:
                colors[i] = np.array([128, 128, 128])
        else:
            da_ind = np.where(lindex == index[i])[0][0]
            colors[i] = np.array([red[da_ind], green[da_ind], blue[da_ind]])

    label = {}
    label['index'] = index
    label['color'] = colors.astype(int)
    label['label'] = name
    label['abbrev'] = abv
    label['parent'] = parent
    label['level_indicator'] = np.ravel(level)

    outfile = open('atlas_labels.pkl', 'wb')
    pickle.dump(label, outfile)
    outfile.close()


def process_atlas_raw_data(atlas_folder, data_file=None, segmentation_file=None, mask_file=None,
                           bregma_coordinates=None, lambda_coordinates=None, return_file=False):

    atlas_path = os.path.join(atlas_folder, data_file)
    segmentation_path = os.path.join(atlas_folder, segmentation_file)
    mask_path = os.path.join(atlas_folder, mask_file)

    if os.path.exists(mask_path):
        mask = nib.load(mask_path)
        mask_data = mask.get_fdata()[:, :, :, 0]
    else:
        mask_data = None

    if not os.path.exists(atlas_path) or not os.path.exists(segmentation_path):
        return

    # pre-process atlas
    atlas = nib.load(atlas_path)
    atlas_header = atlas.header
    pixdim = atlas_header.get('pixdim')[1]
    atlas_data = atlas.get_fdata()
    new_atlas_data = atlas_data.copy()
    if mask_data is not None:
        # make atlas with mask
        new_atlas_data = new_atlas_data - np.min(new_atlas_data)
        for i in range(len(mask_data)):
            new_atlas_data[i][mask_data[i] == 0] = 0
        new_atlas_data = new_atlas_data / np.max(new_atlas_data)

    # voxel size in um
    vxsize = 1e3 * pixdim

    atlas_info = [
        {'name': 'anterior', 'values': np.arange(atlas_data.shape[0]) * vxsize, 'units': 'um'},
        {'name': 'dorsal', 'values': np.arange(atlas_data.shape[1]) * vxsize, 'units': 'um'},
        {'name': 'right', 'values': np.arange(atlas_data.shape[2]) * vxsize, 'units': 'um'},
        {'vxsize': vxsize, 'pixdim': pixdim,
         'Bregma': [bregma_coordinates[0], bregma_coordinates[1], bregma_coordinates[2]],
         'Lambda': [lambda_coordinates[0], lambda_coordinates[1], lambda_coordinates[2]]}
    ]

    atlas = {'data': new_atlas_data, 'info': atlas_info}

    atlas_data = atlas['data']
    atlas_info = atlas['info']

    outfile = open(os.path.join(atlas_folder, 'atlas_pre_made.pkl'), 'wb')
    pickle.dump(atlas, outfile)
    outfile.close()

    # pre-process segmentation
    segmentation = nib.load(segmentation_path)
    segmentation_data = segmentation.get_fdata()
    if mask_data is not None:
        # make segmentation with mask
        for i in range(len(mask_data)):
            segmentation_data[i][mask_data[i] == 0] = 0
        segmentation_data = segmentation_data.astype('int')

    segment = {'data': segmentation_data}

    outfile = open(os.path.join(atlas_folder, 'segment_pre_made.pkl'), 'wb')
    pickle.dump(segment, outfile)
    outfile.close()

    sagital_contour_img = np.zeros(atlas_data.shape, 'i')
    coronal_contour_img = np.zeros(atlas_data.shape, 'i')
    horizontal_contour_img = np.zeros(atlas_data.shape, 'i')

    # pre-process boundary
    for i in range(len(segmentation_data)):
        da_slice = segmentation_data[i, :, :].copy()
        contour_img = make_contour_img(da_slice)
        sagital_contour_img[i, :, :] = contour_img

    for i in range(segmentation_data.shape[1]):
        da_slice = segmentation_data[:, i, :].copy()
        contour_img = make_contour_img(da_slice)
        coronal_contour_img[:, i, :] = contour_img

    for i in range(segmentation_data.shape[2]):
        da_slice = segmentation_data[:, :, i].copy()
        contour_img = make_contour_img(da_slice)
        horizontal_contour_img[:, :, i] = contour_img

    boundary = {'s_contour': sagital_contour_img,
                'c_contour': coronal_contour_img,
                'h_contour': horizontal_contour_img}

    bnd = {'data': boundary}

    outfile_ct = open(os.path.join(atlas_folder, 'contour_pre_made.pkl'), 'wb')
    pickle.dump(bnd, outfile_ct)
    outfile_ct.close()

    if return_file:
        return atlas_data, atlas_info, segmentation_data, boundary
    else:
        return


# AtlasMeshProcessor(atlas_folder, atlas_data, segmentation_data, mesh_data_factor, level)




class AtlasMeshProcessor(object):
    def __init__(self, atlas_folder, atlas_data, segmentation_data, factor, level):
        meshdata = render_volume(atlas_data, atlas_folder, factor=factor, level=level)

        small_meshdata_list = render_small_volume(atlas_data, segmentation_data, atlas_folder,
                                                  factor=factor, level=level)


class AtlasLoader(object):
    def __init__(self, atlas_folder):
        pre_made_atlas_path = os.path.join(atlas_folder, 'atlas_pre_made.pkl')
        pre_made_segment_path = os.path.join(atlas_folder, 'segment_pre_made.pkl')
        pre_made_boundary_path = os.path.join(atlas_folder, 'contour_pre_made.pkl')

        pre_made_label_info_path = os.path.join(atlas_folder, 'atlas_labels.pkl')

        chk1 = os.path.exists(pre_made_label_info_path)
        chk2 = os.path.exists(pre_made_atlas_path)
        chk3 = os.path.exists(pre_made_segment_path)
        chk4 = os.path.exists(pre_made_boundary_path)

        if not np.all([chk1, chk2, chk3, chk4]):
            self.msg = 'Please pre-process the raw data of your desire atlas.'
            self.success = False
        else:
            # laod label info
            try:
                infile = open(pre_made_label_info_path, 'rb')
                self.label_info = pickle.load(infile)
                infile.close()
                self.success = True
            except ValueError:
                self.msg = 'Please give the label information file. If you do not have one, ' \
                           'the maintainers are more than happy to help you to process one.'
                self.success = False
            # load atlas
            try:
                infile_atlas = open(pre_made_atlas_path, 'rb')
                atlas = pickle.load(infile_atlas)
                infile_atlas.close()

                self.atlas_data = atlas['data']
                self.atlas_info = atlas['info']
                # load segmentation
                infile_seg = open(pre_made_segment_path, 'rb')
                segment = pickle.load(infile_seg)
                infile_seg.close()

                self.segmentation_data = segment['data']
                self.success = True
            except ValueError:
                self.msg = 'Please re-process atlas and label segmentation file.'
                self.success = False

            # load boundary
            try:
                infile = open(pre_made_boundary_path, 'rb')
                bnd = pickle.load(infile)
                infile.close()

                self.boundary = bnd['data']
                self.success = True
            except ValueError:
                self.msg = 'Please re-process boundary file.'
                self.success = False





class AtlasMeshLoader(object):
    def __init__(self, atlas_folder):
        pre_made_meshdata_path = os.path.join(atlas_folder, 'atlas_meshdata.pkl')

