#!/bin/bash

if [[ -z $1 ]]
  then
    echo "No dump file provided"
    exit 1
fi
if [[ -z $2 ]]
  then
    echo "No output file provided"
    exit 1
fi

OL_DUMP=$1
OUTPUT=$2

pv "$OL_DUMP" | zgrep ^/type/edition | grep -v '"languages": \[{"key": "/languages' | grep '"language' | gzip > "$OUTPUT"