#!/bin/bash
# Build a GreynirPackage release and upload it to PyPi
if [ "$1" = "" ]; then
   echo "Version name argument missing"
   exit 1
fi
echo "Upload a new GreynirPackage version:" "$1"
# Fix permission bits
chmod -x src/reynir/*.py
chmod -x src/reynir/*.cpp
chmod -x src/reynir/*.grammar
chmod -x src/reynir/*.grammar.bin
chmod -x src/reynir/config/*
chmod -x src/reynir/resources/*
# Create the base source distribution
rm -rf build/*
python3 setup.py sdist
# Create the binary wheels
source wheels.sh
# Upload the new release
# Since twine doesn't work under PyPy (our default Python interpreter),
# we resort to using Python2 to run it
python2 -m twine upload dist/reynir-$1*
echo "Upload of" "$1" "done"
