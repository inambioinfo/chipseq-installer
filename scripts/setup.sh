#!/bin/bash

# variables
PYTHON_PATH=/home/mib-cri/software/python2.7/bin
PROJECT_ROOT=`pwd`
VIRTUALENV_ACTIVATE=${PROJECT_ROOT}/bin/activate

echo "Running chipseq setup script in $PROJECT_ROOT"
cd ${PROJECT_ROOT}

if [ ! -e ${VIRTUALENV_ACTIVATE} ]; then
    echo "Installing python virtualenv in $PROJECT_ROOT"
    if [ ! -e "${PROJECT_ROOT}/virtualenv.py" ]; then
	wget https://raw.github.com/pypa/virtualenv/master/virtualenv.py --no-check-certificate
	echo "${PROJECT_ROOT}/virtualenv.py downloaded"
    fi
    ${PYTHON_PATH}/python virtualenv.py ${PROJECT_ROOT}
    echo "Virtual environment generated"
fi

source ${VIRTUALENV_ACTIVATE}
pip install fabric
pip install PyYAML

echo
echo ">>> [1] Please, to activate python virtualenv, do"
echo ">>> source bin/activate"
echo
echo ">>> [2] Then, install chipseq pipeline:"
echo "    This script requires that you can do a 'ssh localhost'"
echo "    to your installation machine. If you'd like to do this "
echo "    without any passwords you can setup your ssh keys with:"
echo "    > cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys"
echo
echo ">>> fab -f chipseq-build/scripts/fabfile.py local deploy_chipseq"
echo