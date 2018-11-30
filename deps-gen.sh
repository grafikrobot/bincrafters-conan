#!/bin/bash

pushd `dirname $0`
DEPS_DIR=${PWD}
popd

pushd $1
./bootstrap.sh
pushd tools/boostdep/build
../../../b2
popd
dist/bin/boostdep --module-levels > "${DEPS_DIR}/deps-levels.txt"
dist/bin/boostdep --list-dependencies > "${DEPS_DIR}/deps-header.txt"
dist/bin/boostdep --track-sources --list-dependencies > "${DEPS_DIR}/deps-source.txt"
ls -1d libs/*/build > "${DEPS}/deps-build.txt"
popd
