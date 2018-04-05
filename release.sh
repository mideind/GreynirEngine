#!/bin/bash
# Build a Reynir release and upload it to PyPi
if [ "$1" = "" ]; then
   echo "Version name argument missing"
   exit 1
fi
echo "Upload a new Reynir version:" "$1"
# Create the base source distribution
python setup.py sdist
# Create the binary wheels
source wheels.sh
# Upload the new release
twine upload dist/reynir-$1*
echo "Upload of" "$1" "done"

