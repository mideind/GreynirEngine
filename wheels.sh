#!/usr/bin/env bash
echo "Building manylinux2010 wheels..."
# Build manylinux2010 versions via a Docker CentOS6 image
# See https://github.com/pypa/python-manylinux-demo/blob/master/.travis.yml
# and https://github.com/pypy/manylinux
mkdir -p /tmp/io
chmod 777 /tmp/io
chgrp docker /tmp/io
rm -rf /tmp/io/*
mkdir -p /tmp/io/src
mkdir -p /tmp/io/test
mkdir -p /tmp/io/wheelhouse
chmod 777 /tmp/io/wheelhouse
chgrp docker /tmp/io/wheelhouse
# Fresh copy everything to the /tmp/io temporary subdirectory,
# expanding symlinks
cp -L ./* /tmp/io
cp -L -r ./src/* /tmp/io/src
cp -L -r ./test/* /tmp/io/test
# Pull the latest pypywheels/manylinux2010 Docker image
docker pull pypywheels/manylinux2010-pypy_x86_64
# Run the Docker image
docker run --rm -e PLAT=manylinux2010_x86_64 -it -v /tmp/io:/io pypywheels/manylinux2010-pypy_x86_64 bash /io/build_wheels.sh
# Copy the finished wheels
mkdir -p ./dist
mv /tmp/io/wheelhouse/reynir* ./dist
