Installer for the ChipSeq Pipeline
==================================

Dependencies
--------------------------------------------------------------------------------

We are sorry but you will need to have these installed before we can start...
- wget 
- tar 
- unzip 
- make 
- cp 
- python2.7
- boots http://www.boost.org/

Write about striping...

Warnings
--------------------------------------------------------------------------------

- UCSC Tools
If you are getting an error when running these tools that gives libssl.so.10 
error while loading shared libraries. You should try installing openssl using 
our installer:

> fab -f chipseq-installer-master/scripts/chipseq_installer.py local install_openssl

- SciPy Python library
If you are getting an error while installing scipy with our installer, please
try to install atlas using this command:

>  fab -f chipseq-installer-master/scripts/chipseq_installer.py local install_atlas

- The installer script uses fabric and requires that you can do a 
'ssh localhost' on your installation machine. 
If you cannot you will have to setup your ssh keys like this:

> cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys"

Before you have any of our codes on your computer...
--------------------------------------------------------------------------------

Create a project directory e.g. chipseq-test
> mkdir chipseq-test

> cd chipseq-test

Get installer code
> wget --no-check-certificate -r https://github.com/crukci-bioinformatics/chipseq-installer/archive/master.zip -O master-installer.zip

> unzip master-installer.zip 

Before you start... edit your python executable
--------------------------------------------------------------------------------

- edit chipseq-installer-master/scripts/setup.sh
modify PYTHON_PATH=/home/mib-cri/software/python2.7/bin
to point to your own installation of python.

Then start the real installation...
--------------------------------------------------------------------------------

- run

> chipseq-installer-master/scripts/setup.sh

and follow the instructions

- activate python virtualenv, do

> source bin/activate # on bash shell

> source bin/activate.csh # on csh shell

- then, install chipseq pipeline:

> fab -f chipseq-installer-master/scripts/chipseq_installer.py local deploy > chipseq_installer.out 2>&1 & # for bash shell

> fab -f chipseq-installer-master/scripts/chipseq_installer.py local_csh deploy >& chipseq_installer.out & # for csh shell

to follow the installation do

> tail -f chipseq_installer.out

Testing...
--------------------------------------------------------------------------------
To run on an LSF machine..you are good to go!!
If you wish to run on a non-LSF machine then please edit chipseq-pipeline-master/Process10/Config/config.ini and change "Mode = LSF" -> "Mode = local"

> cd chipseq-test

> ../chipseq-pipeline-master/Process10/RScripts/ChipSeq.r --genome mm9 --callMacsPeaks Yes --callMacsMotifs Yes --callMacsPeakProfile Yes


