#! /bin/bash
set -eu

# NOTE: this assumes you've already installed Cython, GDAL, rasterio, Rtree and Shapely from 
# .whl files. See ./Developer.md if you need instructions on how to do that

# On OSX you must have run `brew install gdal` so that the header files are findable 
# C:\Users\Matt\AppData\Local\Programs\Python\Python38\python.exe -m virtualenv .venv
# Make sure pip is at a good version

# source ./.venv/Scripts/activate

# pip --timeout=120 install \
#   Cython==0.29.23 \
#   numpy==1.16.3 \
#   scipy>=1.8.1

# # Now install everything else
# .venv/Scripts/pip --timeout=120 install -r requirements.txt

# Install our packages as being editable
.venv/Scripts/pip install -e ./lib/commons
.venv/Scripts/pip install -e ./packages/rscontext
.venv/Scripts/pip install -e ./packages/vbet
.venv/Scripts/pip install -e ./packages/brat


read -p "Press [Enter] key to start backup..."