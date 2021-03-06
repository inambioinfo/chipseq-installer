#!/bin/bash

# variables
PYTHON_EXE=/home/mib-cri/software/python2.7/bin
PROJECT_ROOT=`pwd`
VIRTUALENV_ACTIVATE=${PROJECT_ROOT}/bin/activate
VIRTUALENV_VERSION=1.10.1

echo "Checking core dependencies before installing..."

for core_tool in wget tar unzip make cp ${PYTHON_EXE}/python
do
    command -v $core_tool >/dev/null 2>&1 || { echo >&2 "It requires $core_tool but it's not installed. Aborting."; exit 1; }
    echo "... $core_tool installed"
done

echo "Running chipseq setup script in $PROJECT_ROOT"

cd ${PROJECT_ROOT}

if [ ! -e ${VIRTUALENV_ACTIVATE} ]; then
    echo "Installing python virtualenv in $PROJECT_ROOT"
    if [ ! -e "${PROJECT_ROOT}/virtualenv.py" ]; then
	wget https://pypi.python.org/packages/source/v/virtualenv/virtualenv-${VIRTUALENV_VERSION}.tar.gz --no-check-certificate
	tar -zxvf virtualenv-${VIRTUALENV_VERSION}.tar.gz 
	echo "${PROJECT_ROOT}/virtualenv.py downloaded"
    fi
    ${PYTHON_EXE}/python virtualenv-${VIRTUALENV_VERSION}/virtualenv.py ${PROJECT_ROOT}
    echo "Virtual environment generated"
fi

source ${VIRTUALENV_ACTIVATE}
pip install fabric
pip install PyYAML

echo "================================================================================"
echo
echo "[1] Please, to activate python virtualenv, do"
echo "-bash-> source bin/activate"
echo "--csh-> source bin/activate.csh"
echo
echo "[2] Then, install chipseq pipeline:"
echo "-bash-> fab -f chipseq-installer-master/scripts/chipseq_installer.py local deploy > chipseq_installer.out 2>&1 &"
echo "--csh-> fab -f chipseq-installer-master/scripts/chipseq_installer.py local_csh deploy >& chipseq_installer.out &"
echo
echo "================================================================================"
echo