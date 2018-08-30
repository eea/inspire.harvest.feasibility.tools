#!/usr/bin/env bash

xargs -I {} ./test_download_svc.sh {} < ../data/endpoints_all.csv
