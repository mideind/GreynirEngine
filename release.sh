#!/bin/bash
# Build a Reynir release and upload it to PyPi
if [ "$1" = "" ]; then
   echo "Version name argument missing"
   exit 1
fi
echo "Upload a new Reynir version:" "$1"
# Fix permission bits
chmod -x src/reynir/*.py
chmod -x src/reynir/*.cpp
chmod -x src/reynir/*.grammar
chmod -x src/reynir/*.grammar.bin
chmod -x src/reynir/config/*
chmod -x src/reynir/resources/*
# Create the base source distribution
python setup.py sdist
# Create the binary wheels
source wheels.sh
# Upload the new release
twine upload dist/reynir-$1*
echo "Upload of" "$1" "done"

