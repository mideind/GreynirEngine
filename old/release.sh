#!/bin/bash
# Build a GreynirEngine release and upload it to PyPi
if [ "$1" = "" ]; then
   echo "Version name argument missing"
   exit 1
fi
echo "Upload a new GreynirEngine version:" "$1"
# Fix permission bits
chmod -x src/reynir/*.py
chmod -x src/reynir/*.cpp
chmod -x src/reynir/*.grammar
chmod -x src/reynir/config/*
chmod -x src/reynir/resources/*
# Remove binary grammar files as they may be out of date
rm src/reynir/Greynir.*.bin
# Create the base source distribution
rm -rf build/*
python3 setup.py sdist
# Create the binary wheels
source wheels.sh
# Upload the new release
twine upload dist/reynir-$1*
echo "Upload of" "$1" "done"
