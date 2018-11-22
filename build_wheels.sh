#!/usr/bin/env bash
# Build the reynir wheels on the CentOS5 base manylinux1 platform
# This script should be executed inside the Docker container!
# It is invoked indirectly from wheels.sh

# Stop execution upon error; show executed commands
set -e -x

# Compile wheels for Python 3.4-3.7
for PYBIN in cp34 cp35 cp36 cp37
do
#    "${PYBIN}/pip" install -r /io/dev-requirements.txt
    "/opt/python/${PYBIN}-${PYBIN}m/bin/pip" wheel /io/ -w wheelhouse/
done

# Bundle external shared libraries into the wheels
for whl in wheelhouse/reynir-*.whl
do
    auditwheel repair "$whl" -w /io/wheelhouse/
done

# Set read/write permissions on the wheels
chmod 666 /io/wheelhouse/*
