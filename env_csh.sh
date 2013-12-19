umask 022
setenv CHIPSEQ_ROOT /Path/To/Edit/
setenv PATH ${CHIPSEQ_ROOT}/bin:${PATH}
source ${CHIPSEQ_ROOT}/bin/activate.csh
setenv PKG_CONFIG_PATH ${CHIPSEQ_ROOT}/lib/pkgconfig/
setenv R_LIBS ${CHIPSEQ_ROOT}/lib/R/library
setenv PERLLIB ${CHIPSEQ_ROOT}/bin/perl/lib
setenv PERL5LIB ${CHIPSEQ_ROOT}/bin/perl/lib
set PERL_MM_USE_DEFAULT=1
unset PYTHONPATH
setenv LD_LIBRARY_PATH ${LD_LIBRARY_PATH}:${CHIPSEQ_ROOT}/lib:${CHIPSEQ_ROOT}/lib/R/lib
