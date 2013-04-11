# --------------------------------------------------------------------------------
# chipseq specific
#
umask 022 #(666-022)=644 (rw-r--r--) for files & (777-022)=755 (dwxr-xr-x) for directories

# To be defined per project
export CHIPSEQ_ROOT=/home/pajon01/chipseq-test

# bin
export PATH=${GALAXY_ROOT}/bin:${PATH}

# Python virtualenv
source ${GALAXY_ROOT}/bin/activate

# LD Library path
export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:${GALAXY_ROOT}/lib:${GALAXY_ROOT}/lib64/R/lib
# --------------------------------------------------------------------------------

