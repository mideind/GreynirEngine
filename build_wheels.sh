#!/usr/bin/env bash
# Build the reynir wheels on the CentOS5/6 base manylinux1/manylinux2010 platform
# This script should be executed inside the Docker container!
# It is invoked indirectly from wheels.sh

# Stop execution upon error; show executed commands
set -e -x

# Create wheels for Python 3.7
for PYBIN in cp37; do
    "/opt/python/${PYBIN}-${PYBIN}m/bin/pip" wheel /io/ -w wheelhouse/
done
# Create wheels for Python >= 3.8
for PYBIN in cp38 cp39; do
	"/opt/python/${PYBIN}-${PYBIN}/bin/pip" wheel /io/ -w wheelhouse/
done
# Create wheels for PyPy3 (>=3.7)
for PYBIN in /opt/pypy/pypy3.*/bin; do
    "${PYBIN}/pip" wheel /io/ -w wheelhouse/
done

# Bundle external shared libraries into the wheels
for whl in wheelhouse/reynir-*.whl; do
    auditwheel repair "$whl" --plat $PLAT -w /io/wheelhouse/
done

# Set read/write permissions on the wheels
chmod 666 /io/wheelhouse/*
