#!/usr/bin/env bash
set -uo pipefail
R=/home/yk/ext/rife-ncnn/src/rife.cpp
echo "==== remaining outimage.data writes ===="
grep -n 'outimage.data' "$R"
echo "==== enclosing function for each ===="
for ln in $(grep -n 'outimage.data' "$R" | cut -d: -f1); do
    fn=$(awk -v target="$ln" 'NR<=target && /^[a-zA-Z].*::.*\(/ {last=$0; ln2=NR} END {print ln2": "last}' "$R")
    echo "line $ln <- $fn"
done
echo "==== context of the last one ===="
sed -n '4380,4400p' "$R"
