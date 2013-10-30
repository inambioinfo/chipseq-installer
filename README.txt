================================================================================
== Installer for the ChipSeq Pipeline
================================================================================

--------------------------------------------------------------------------------
-- Dependencies
--------------------------------------------------------------------------------

We are sorry but you will need to have these installed before we can start...
- wget 
- tar 
- unzip 
- svn 
- make 
- cp 
- rsync
- python2.7
- boots http://www.boost.org/
- atlas http://math-atlas.sourceforge.net/

Write about striping

--------------------------------------------------------------------------------
-- 1. Before you have any of our codes on your computer...
--------------------------------------------------------------------------------

Create a project directory e.g. chipseq-test
> mkdir chipseq-test

Get installer code
> svn co svn://uk-cri-lbio01/pipelines/chipseq/trunk/chipseq-build

--------------------------------------------------------------------------------
-- 2. Before you start...
--------------------------------------------------------------------------------

- edit chipseq-build/env.bashrc
modify CHIPSEQ_ROOT=/home/pajon01/chipseq-test/ 
to represent the root of your project so one level above this one where this README is.

- edit scripts/setup.sh
modify PYTHON_PATH=/home/mib-cri/software/python2.7/bin
to point to your own installation of python.

--------------------------------------------------------------------------------
-- Then the real installation...
--------------------------------------------------------------------------------

- from $CHIPSEQ_ROOT, run
> chipseq-build/scripts/setup.sh

and follow the instructions

- activate python virtualenv, do
> source bin/activate

- then, install chipseq pipeline:
> fab -f chipseq-build/scripts/chipseq_installer.py local deploy > chipseq_installer.out 2>&1 &

to follow the installation do
> tail -f chipseq_installer.out

--------------------------------------------------------------------------------
-- Testing...
--------------------------------------------------------------------------------
> cd chipseq-test
> ../Process10/RScripts/ChipSeq.r --genome mm10 --callMacsPeaks Yes --callMacsMotifs Yes

