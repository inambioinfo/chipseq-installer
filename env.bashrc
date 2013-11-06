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

# Pkg config for Cairo
export PKG_CONFIG_PATH=${CHIPSEQ_ROOT}/lib/pkgconfig/

# R libraries
export R_LIBS=${CHIPSEQ_ROOT}/lib/R/library

# Perl libraries
export PERLLIB=${CHIPSEQ_ROOT}/bin/perl/lib
export PERL5LIB=${CHIPSEQ_ROOT}/bin/perl/lib
export PERL_MM_USE_DEFAULT=1

# Python path
export PYTHONPATH=

# LD Library path
export LD_LIBRARY_PATH=${CHIPSEQ_ROOT}/lib/R/lib:${CHIPSEQ_ROOT}/lib:${LD_LIBRARY_PATH}
# --------------------------------------------------------------------------------

