#!/bin/bash

# Go to home directory
cd ~

# Delete .curlrc and .wgetrc
rm -f .curlrc .wgetrc

# Export proxy settings
export http_proxy='http://ga.dp.tech:8118'
export https_proxy='http://ga.dp.tech:8118'

export BOHRIUM_BOHRIUM_URL="https://bohrium.test.dp.tech"
export BOHRIUM_TIEFBLUE_URL="https://tiefblue.test.dp.tech"
export BOHRIUM_OPENAPI_URL="https://openapi.test.dp.tech"
export BOHRIUM_BASE_URL="https://openapi.test.dp.tech"
export TIEFBLUE_BASE_URL="https://tiefblue-zjk-test.test.dp.tech"

# Activate conda environment
source /root/.bashrc  # Adjust path if needed
conda activate optimade