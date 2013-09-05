# --------------------------------------------------------------------------------
# chipseq specific
#
umask 022 #(666-022)=644 (rw-r--r--) for files & (777-022)=755 (dwxr-xr-x) for directories

# To be defined per project
export CHIPSEQ_ROOT=/home/tom/Desktop/Pipelines/Test

# bin
export PATH=${CHIPSEQ_ROOT}/bin:${PATH}

# Python virtualenv
source ${CHIPSEQ_ROOT}/bin/activate

export R_LIBS=${CHIPSEQ_ROOT}/lib/R/library

export PYTHONPATH=

# LD Library path
export LD_LIBRARY_PATH=${CHIPSEQ_ROOT}/lib/R/lib:${CHIPSEQ_ROOT}/lib:${LD_LIBRARY_PATH}
# --------------------------------------------------------------------------------

