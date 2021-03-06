"""
Created by Anne Pajon on 11 Apr 2013

Copyright (c) 2012 Cancer Research UK - Cambridge Institute.

This source file is licensed under The MIT License (MIT).

And many ideas have been taken from:
- https://github.com/chapmanb/bcbb/blob/master/galaxy/galaxy_fabfile.py
- https://github.com/chapmanb/cloudbiolinux

It is a fabric deployment file to set up the chipseq pipeline developed by 
Thomas Carroll. Fabric (http://docs.fabfile.org) is used to manage the automation 
of the installation.

Usage:
    fab -f scripts/chipseq_installer.py local deploy > chipseq_installer.out
"""
import os
from contextlib import contextmanager

from fabric.api import *
from fabric.contrib.files import *
from fabric.operations import local as lrun

import yaml

# -- Common setup
env.hosts = ['localhost']
env.project_dir = os.getenv('PWD')
env.tmp_dir = os.path.join(env.project_dir, 'tmp')
env.bin_dir = os.path.join(env.project_dir, 'bin')
env.lib_dir = os.path.join(env.project_dir, 'lib')
env.annotation_dir = os.path.join(env.project_dir, 'annotation')
env.grch37_dir = os.path.join(env.annotation_dir, "grch37_ensembl")
env.mm9_dir = os.path.join(env.annotation_dir, "mm9_Ensembl")
env.test_dir = os.path.join(env.project_dir, "chipseq-test")
env.testfq_dir = os.path.join(env.test_dir, "fqdirectory")
env.r_lib_dir = os.path.join(env.project_dir, 'lib/R/library')
env.perl_dir = os.path.join(env.bin_dir, 'perl')
env.meme_dir = os.path.join(env.bin_dir, 'meme')
env.sicer_dir = os.path.join(env.bin_dir, 'sicer')
env.java_dir = os.path.join(env.lib_dir, 'jdk1.7.0_51')
env.chipseq_installer = os.path.join(env.project_dir, 'chipseq-installer-master')
env.chipseq_pipeline = os.path.join(env.project_dir, 'chipseq-pipeline-master')
env.chipseq_path = os.path.join(env.chipseq_pipeline, 'Process10')
env.chipseq_config_path = os.path.join(env.chipseq_path, 'Config')
env.use_sudo = False

# ================================================================================
# == Host specific setup

def local():
    """Setup environment for local installation in bash shell for running chipseq jobs on the cluster.
    """
    env.r_dir = env.project_dir
    env.shell = "/bin/bash"
    env.env_setup = ('env.sh')
    env.activate = 'activate'

def local_csh():
    """Setup environment for local installation in csh shell for running chipseq jobs on the cluster.
    """
    env.r_dir = env.project_dir
    env.shell = "/bin/csh"
    env.env_setup = ('env_csh.sh')
    env.activate = 'activate.csh'

# ================================================================================
# == Fabric instructions

def deploy():
    """Setup environment, install dependencies and tools
    and deploy chipseq pipeline
    """
    setup_environment()
    install_dependencies()
    install_tools()
    install_data()
    install_chipseq()
    install_test()

def deploy_withextras():
    """Setup environment, install dependencies and tools
    and deploy chipseq pipeline with extras such as atlas and openssl
    """
    setup_environment()
    install_atlas() # needed for installing SciPy library
    install_openssl() # needed for ucsc tools and perl
    install_dependencies()
    install_tools()
    install_data()
    install_chipseq()
    install_test()

# ================================================================================
# == Decorators and build utilities

def setup_environment():
    """Copy adhoc environment variables, set CHIPSEQ_ROOT path and create tmp directory
    """
    sed_chipseq_root = env.project_dir.replace('/', '\/')
    setup_ori = os.path.join(env.chipseq_installer, env.env_setup)
    setup_dest = os.path.join(env.project_dir, env.env_setup)
    lrun("sed 's/\/Path\/To\/Edit\//%s/' %s > %s" % (sed_chipseq_root, setup_ori, setup_dest))
    _make_dir(env.tmp_dir)

def lexists(path):
    return os.path.exists(path)

def vlrun(command):
    """Run a command in a virtual environment. This prefixes the run command with the source command.
    Usage:
        vlrun('pip install tables')
    """
    source = 'source %(project_dir)s/bin/%(activate)s && source %(project_dir)s/%(env_setup)s && ' % env
    return lrun(source + command, shell='%s' % env.shell)    

def _if_not_python_lib(library):
    """Decorator that checks if a python library is installed.
    """
    def argcatcher(func):
        def decorator(*args, **kwargs):
            with settings(warn_only=True):
                result = vlrun("python -c 'import %s'" % library)
            if result.failed:
                return func(*args, **kwargs)
        return decorator
    return argcatcher

def _make_dir(path):
    with settings(warn_only=True):
        if lrun("test -d %s" % path).failed:
            lrun("mkdir -p %s" % path)

def _get_expected_file(path, url):
    tar_file = os.path.split(url)[-1]
    safe_tar = "--pax-option='delete=SCHILY.*,delete=LIBARCHIVE.*'"
    exts = {(".tar.gz", ".tgz") : "tar %s -xzpf" % safe_tar,
            (".tar.xz",) : "tar %s -xJpf" % safe_tar,
            (".tar.bz2",): "tar %s -xjpf" % safe_tar,
            (".zip",) : "unzip -o"}
    for ext_choices, tar_cmd in exts.iteritems():
        for ext in ext_choices:
            if tar_file.endswith(ext):
                return tar_file, tar_file[:-len(ext)], tar_cmd
    raise ValueError("Did not find extract command for %s" % url)

def _safe_dir_name(path, dir_name, need_dir=True):
    replace_try = ["", "-src", "_core"]
    for replace in replace_try:
        check = dir_name.replace(replace, "")
        if lexists(os.path.join(path, check)):
            return check
        # still couldn't find it, it's a nasty one
        for check_part in (dir_name.split("-")[0].split("_")[0],
                           dir_name.split("-")[-1].split("_")[-1],
                           dir_name.split(".")[0]):
            with settings(hide('warnings', 'running', 'stdout', 'stderr'),
                          warn_only=True):
                dirs = lrun("ls -d1 %s/*%s*/" % (path, check_part)).split("\n")
                dirs = [x for x in dirs if "cannot access" not in x and "No such" not in x]
                if len(dirs) == 1:
                    return dirs[0]
                if need_dir:
                    raise ValueError("Could not find directory %s" % dir_name)

def _fetch_and_unpack(path, url, need_dir=True, wget_options=''):
    tar_file, dir_name, tar_cmd = _get_expected_file(path, url)
    if lexists(os.path.join(path, tar_file)):
       lrun("rm -rf %s" % os.path.join(path, tar_file)) 
    lrun("wget --no-check-certificate %s %s" % (wget_options, url))
    vlrun("%s %s" % (tar_cmd, tar_file))
    return _safe_dir_name(path, dir_name, need_dir)
    
def _fetch(path, url):
    tar_file = os.path.split(url)[-1]
    if not lexists(os.path.join(path, tar_file)):
        lrun("wget -r %s -O %s" % (url, os.path.join(path, tar_file)))

def _fetch_and_unpack_genome(path, url):
    tar_file = os.path.split(url)[-1]
    if not lexists(os.path.join(path, tar_file)):
        lrun("wget -r %s -O %s" % (url, tar_file))
        lrun("gzip -d -r  %s" % tar_file)

def _configure_make(env, options=''):
    vlrun("./configure --disable-error --prefix=%s %s" % (env.project_dir, options))
    vlrun("make")
    vlrun("make install")

def _get_install(url, env, make_command, make_options=''):
    """Retrieve source from a URL and install in our system directory.
    """
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        with lcd(dir_name):
            make_command(env, make_options)
    
# ================================================================================
# == Required dependencies to install chipseq pipeline

def install_dependencies():
    """Install chipseq dependencies:
    - tar
    - Perl & libraries
    - Cairo
    - R & libraries
    - Python libraries
    - rsync
    - git
    - Java
    - Richard Bowers' workflow
    """
    install_tar()
    install_perl()
    install_perl_libraries()
    install_cairo()
    install_r()
    install_r_libraries()
    install_python_libraries()
    install_rsync()
    install_git()
    install_java()
    install_workflow()
    
def install_tar():
    """Install tar 1.27 with xz 5.0.5
    to uncompress xz archive
    """
    xz_url = "http://tukaani.org/xz/xz-5.0.5.tar.gz"
    url = "http://ftp.gnu.org/gnu/tar/tar-1.27.tar.gz"
    _get_install(xz_url, env, _configure_make)
    _get_install(url, env, _configure_make)

def install_atlas():
    """Install atlas 3.10.1
    Atlas may need to be installed to have numpy anc scipy installed
    """
    lapack_url = "http://www.netlib.org/lapack/lapack-3.4.1.tgz"
    lapack_tar = os.path.join(env.tmp_dir, 'lapack-3.4.1.tgz')
    atlas_url = "http://sourceforge.net/projects/math-atlas/files/Stable/3.10.1/atlas3.10.1.tar.bz2"
    atlas_dir = "ATLAS3.10.1"
    atlas_lib = os.path.join(env.lib_dir, 'atlas')
    _make_dir(atlas_lib)
    with lcd(env.tmp_dir):
        lrun("wget %s" % lapack_url)
        dir_name = _fetch_and_unpack(env.tmp_dir, atlas_url)
        lrun("mv ATLAS %s" % atlas_dir)
        with lcd(atlas_dir):
            _make_dir("linux_install")
            with lcd("linux_install"):
                lrun("../configure -b 64 -D c -DPentiumCPS=2400 --shared --prefix=%s --with-netlib-lapack-tarfile=%s" % (atlas_lib, lapack_tar))
                lrun("make build")
                lrun("make check")
                lrun("make ptcheck")
                lrun("make install")
    with lcd(env.lib_dir):
        # all shared lib needs to be moved from lib/atlas/lib to lib/atlas to be picked up by scipy installer
        lrun("mv atlas/lib/* atlas/.")
        
def install_cairo():
    """Install cairo 1.12.16
    Needed when no X11 support available
    """ 
    pixman_url = "http://www.cairographics.org/releases/pixman-0.30.2.tar.gz"
    cairo_url = "http://www.cairographics.org/releases/cairo-1.12.16.tar.xz"
    _get_install(pixman_url, env, _configure_make)
    _get_install(cairo_url, env, _configure_make, "--disable-static --disable-gobject")
    
def install_python_libraries():
    """Install Python libraries
    """
    vlrun("pip install fluent-logger==0.3.3")
    vlrun("pip install nose==1.3.0")
    vlrun("pip install numpy==1.7.1")
    vlrun("pip install cython==0.19.2")
    vlrun("pip install numexpr==2.2.2")
    vlrun("pip install pyyaml==3.10")
    vlrun("pip install rpy2==2.3.8")
    vlrun("pip install pysam==0.7.4")
    vlrun("pip install scipy==0.12.1")
    vlrun("pip install bx-python==0.7.1")
    vlrun("pip install configparser")
    vlrun("pip install biopython==1.62")    
    _install_rpy_lib()

@_if_not_python_lib("rpy")
def _install_rpy_lib():
    """Install RPy 1.0.3
    """
    url = "http://sourceforge.net/projects/rpy/files/rpy/1.0.3/rpy-1.0.3.tar.gz"
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        with lcd(dir_name):
            lrun("sed -i 's/\[0\-9\]/\[0\-9\]\+/g' rpy_tools.py")
            lrun("sed -i 's/Rdevices.h/Rembedded.h/g' src/RPy.h")
            vlrun("python setup.py install")

def install_r():
    """Install R 2.15.0
    """
    _make_dir(env.r_lib_dir)
    url = "http://cran.r-project.org/src/base/R-2/R-2.15.0.tar.gz"
    option = "--enable-R-shlib"
    if not lexists(os.path.join(env.r_dir, "bin/R")):
        _get_install(url, env, _configure_make, option)
        # create symlinks in bin for installation on mac only
        if not lexists(os.path.join(env.bin_dir, "R")):
            lrun('ln -fs %(r_dir)s/bin/R %(bin_dir)s/R' % env)
            lrun('ln -fs %(r_dir)s/bin/Rscript %(bin_dir)s/Rscript' % env)

def install_r_libraries():
    """Install R libraries listed in r-libraries.yaml needed to run chipseq pipeline
    """
    # Load list of R libraries to install
    config_file = open(os.path.join(env.chipseq_installer, "scripts/r-libraries.yaml"), 'r')
    config = yaml.load(config_file)
    # Create an Rscript file with install details.
    out_file = "install_packages.R"
    if lexists(out_file):
        lrun("rm -f %s" % out_file)
    lrun("touch %s" % out_file)
    repo_info = """
    cran.repos <- getOption(\"repos\")
    cran.repos[\"CRAN\" ] <- \"%s\"
    options(repos=cran.repos)
    source(\"%s\")
    """ % (config["cranrepo"], config["biocrepo"])
    lrun("echo '%s' >> %s" % (repo_info, out_file))
    bioc_install = """
    bioc.pkgs <- c(%s)

    """ % (", ".join('"%s"' % p for p in config['bioc']))
    bioc_install2 = """
    biocLite(lib=\"%(r_lib_dir)s\",lib.loc=\"%(r_lib_dir)s\",ask=F)
    biocLite(bioc.pkgs,lib=\"%(r_lib_dir)s\",lib.loc=\"%(r_lib_dir)s\",ask=F)    
    """ % env
    lrun("echo '%s' >> %s" % (bioc_install, out_file))
    lrun("echo '%s' >> %s" % (bioc_install2, out_file))
    std_install = """
    std.pkgs <- c(%s)
    """ % (", ".join('"%s"' % p for p in config['cran']))
    lrun("echo '%s' >> %s" % (std_install, out_file))
    std_install2 = """
    install.packages(std.pkgs,lib=\"%(r_lib_dir)s\")
    """ % env
    lrun("echo '%s' >> %s" % (std_install2, out_file))
    gplots_install = """
    download.file(\"http://cran.r-project.org/src/contrib/Archive/gplots/gplots_2.10.1.tar.gz\",\"%(tmp_dir)s/gplots_2.10.1.tar.gz\")
    
    """ % env
    lrun("echo '%s' >> %s" % (gplots_install, out_file))
    gplots_install2 = """
    install.packages(\"%(tmp_dir)s/gplots_2.10.1.tar.gz\",lib=\"%(r_lib_dir)s\")
    """ % env
    lrun("echo '%s' >> %s" % (gplots_install2, out_file))    
    
    spp_install = """
    download.file(\"http://compbio.med.harvard.edu/Supplements/ChIP-seq/spp_1.11.tar.gz\",\"%(tmp_dir)s/spp_1.11.tar.gz\")
    
    """ % env
    lrun("echo '%s' >> %s" % (spp_install, out_file))
    spp_install2 = """
    install.packages(\"%(tmp_dir)s/spp_1.11.tar.gz\",lib=\"%(r_lib_dir)s\")
    
    """ % env
    lrun("echo '%s' >> %s" % (spp_install2, out_file))  
    GMC_install = """
    download.file(\"http://genometricorr.sourceforge.net/R/src/contrib/GenometriCorr_1.1.9.tar.gz\",\"%(tmp_dir)s/GenometriCorr_1.1.9.tar.gz\")
    
    """ % env
    lrun("echo '%s' >> %s" % (GMC_install, out_file))
    GMC_install2 = """
    install.packages(\"%(tmp_dir)s/GenometriCorr_1.1.9.tar.gz\",lib=\"%(r_lib_dir)s\")
    
    """ % env
    lrun("echo '%s' >> %s" % (GMC_install2, out_file))       

    hmisc_install = """
    download.file(\"http://cran.r-project.org/src/contrib/Archive/Hmisc/Hmisc_3.10-1.1.tar.gz\",\"%(tmp_dir)s/Hmisc_3.10-1.1.tar.gz\")   
    """ % env
    lrun("echo '%s' >> %s" % (hmisc_install, out_file))
    hmisc_install2 = """
    install.packages(\"%(tmp_dir)s/Hmisc_3.10-1.1.tar.gz\",lib=\"%(r_lib_dir)s\")
    """ % env
    lrun("echo '%s' >> %s" % (hmisc_install2, out_file))       

    gdd_install = """
    download.file(\"http://www.rforge.net/src/contrib/GDD_0.1-13.tar.gz\",\"%(tmp_dir)s/GDD_0.1-13.tar.gz\")   
    """ % env
    lrun("echo '%s' >> %s" % (gdd_install, out_file))
    gdd_install2 = """
    install.packages(\"%(tmp_dir)s/GDD_0.1-13.tar.gz\",lib=\"%(r_lib_dir)s\")
    """ % env
    lrun("echo '%s' >> %s" % (gdd_install2, out_file))       
       
    gridsvg_install = """
    download.file(\"http://cran.r-project.org/src/contrib/Archive/gridSVG/gridSVG_0.9-1.tar.gz\",\"%(tmp_dir)s/gridSVG_0.9-1.tar.gz\")   
    """ % env
    lrun("echo '%s' >> %s" % (gridsvg_install, out_file))
    gridsvg_install2 = """
    install.packages(\"%(tmp_dir)s/gridSVG_0.9-1.tar.gz\",lib=\"%(r_lib_dir)s\")
    """ % env
    lrun("echo '%s' >> %s" % (gridsvg_install2, out_file))       

    # Run the script and then get rid of it
    vlrun("%s %s" % (os.path.join(env.bin_dir, "Rscript"), out_file))
    lrun("rm -f %s" % out_file)

def install_perl():
    """Install perl 5.18.0
    """
    url = "http://www.cpan.org/src/5.0/perl-5.18.0.tar.gz"
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        if not lexists(env.perl_dir):
            _make_dir(env.perl_dir)
        with lcd(dir_name):
            lrun("sh Configure -de -Dprefix='%s'" % (env.perl_dir))
            lrun("make")
            lrun("make install")

def install_perl_libraries():
    """Install perl libraries
    """
    lrun("%s/bin/cpan App::cpanminus < /dev/null" % (env.perl_dir))    
    lrun("%s/bin/cpanm --skip-installed --notest HTML::PullParser < /dev/null" % (env.perl_dir))
    lrun("%s/bin/cpanm --skip-installed --notest HTML::Template < /dev/null" % (env.perl_dir))
    lrun("%s/bin/cpanm --skip-installed --notest LWP < /dev/null" % (env.perl_dir))
    lrun("%s/bin/cpanm --skip-installed --notest SOAP::Lite < /dev/null" % (env.perl_dir))
    lrun("%s/bin/cpanm --skip-installed --notest XML::Simple < /dev/null" % (env.perl_dir))    
                
def install_rsync():
    """Install rsync 3.1.0
    """
    url = "http://rsync.samba.org/ftp/rsync/src/rsync-3.1.0.tar.gz"
    _get_install(url, env, _configure_make)
    
def install_git():
    """Install git 1.8.4.2
    """
    url = "http://git-core.googlecode.com/files/git-1.8.4.2.tar.gz"
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        with lcd(dir_name):
            lrun("make prefix=%s all" % env.project_dir)
            lrun("make prefix=%s install" % env.project_dir)

def install_java():
    """Install Java 7
    http://download.oracle.com/otn-pub/java/jdk/7u51-b13/jdk-7u51-linux-x64.tar.gz
    """
    tar_file = "jdk-7u51-linux-x64.tar.gz"
    with lcd(env.tmp_dir):
        lrun('wget --no-check-certificate --no-cookies --header "Cookie: oraclelicense=accept-securebackup-cookie" http://download.oracle.com/otn-pub/java/jdk/7u51-b13/%s -O %s' % (tar_file, tar_file))
        lrun ("tar zxvf %s -C %s" % (tar_file, env.lib_dir))

def install_workflow():
    """Install Richard Bower CRUK-CI workflow manager
    Checkout the workflow manager from repository.
    """
    with lcd(env.lib_dir):
        workflow_path = os.path.join(env.chipseq_installer, "workflow-manager")
        lrun('cp -r %s .' % workflow_path)

# ================================================================================
# == Required specific tools to install chipseq pipeline

def install_tools():
    """Install chipseq specific tools:
    - UCSC tools: liftOver, TwoBitToFa, FaToTwoBit, BedToBigBed, WigToBigWig, BedGraphToBigWig
    - samtools
    - BEDTools
    - picard
    - bwa
    - macs
    - meme
    - sicer
    """
    install_ucsc_tools()
    install_samtools()
    install_bedtools()
    install_picard()    
    install_bwa()
    install_macs()
    install_meme()
    install_sicer()
    install_gtf2bed()

def install_gtf2bed():
    """Install gtf2bed from trunk
    """
    url = "https://ea-utils.googlecode.com/svn/trunk/clipper/gtf2bed"
    with lcd(env.bin_dir):
    	lrun("wget %s -O gtf2bed.pl" % (url))         
    
def install_openssl():
    """Install openssl 1.0.1e
    For UCSC tools that gives libssl.so.10 error while loading shared libraries
    """
    url = "http://www.openssl.org/source/openssl-1.0.1e.tar.gz"
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        with lcd(dir_name):
            lrun("./config --prefix=%s --shared" % env.project_dir)
            lrun("make")
            lrun("make install")
    with lcd(env.lib_dir):
        lrun("ln -s ../lib64/libssl.so.1.0.0 libssl.so.10")
        lrun("ln -s ../lib64/libcrypto.so.1.0.0 libcrypto.so.10")
            
def install_ucsc_tools():
    """Install useful executables from UCSC.
    see https://github.com/chapmanb/cloudbiolinux/blob/master/cloudbio/custom/bio_nextgen.py
    for an up-to-date version
    """
    tools = ["liftOver", "faToTwoBit", "twoBitToFa", "bedToBigBed", "wigToBigWig", "bedGraphToBigWig"]
    url = "http://hgdownload.cse.ucsc.edu/admin/exe/linux.x86_64/"
    for tool in tools:
        with lcd(env.bin_dir):
            if not lexists(os.path.join(env.bin_dir, tool)):
                lrun("wget %s%s" % (url, tool))
                lrun("chmod a+rwx %s" % tool)

def install_samtools():
    """Install samtools 0.1.18
    """
    url = "http://sourceforge.net/projects/samtools/files/samtools/0.1.18/samtools-0.1.18.tar.bz2"
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        with lcd(dir_name):
            lrun("make")
            # copy executables to bin
            lrun("find . -perm /u=x -type f -exec cp {} %(bin_dir)s \;" % env)

def install_bedtools():
    """Install BEDTools 2.17.0
    """
    url = "http://bedtools.googlecode.com/files/BEDTools.v2.17.0.tar.gz"
    with lcd(env.tmp_dir):
        # cannot _fetch_and_unpack return because package name does not match unpacked dir
        _fetch_and_unpack(env.tmp_dir, url, False)
        with lcd("bedtools-2.17.0"):
            lrun("make clean")
            lrun("make all")
            lrun("find bin/. -perm /u=x -type f -exec cp {} %(bin_dir)s \;" % env)

def install_picard():
    """Install Picard 1.96
    """
    version = "1.96"
    url = 'http://downloads.sourceforge.net/project/picard/picard-tools/%s/picard-tools-%s.zip' % (version, version)
    picard_dir = os.path.join(env.bin_dir, "picard")
    _make_dir(picard_dir)
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        with lcd(dir_name):
            lrun("mv *.jar %s" % picard_dir)

def install_bwa():
    """Install BWA 0.5.9
    Aligns short nucleotide sequences against a long reference sequence.
    http://bio-bwa.sourceforge.net/
    """
    version = "0.5.9"
    url = "http://downloads.sourceforge.net/project/bio-bwa/bwa-%s.tar.bz2" % (version)
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        with lcd(dir_name):
            arch = lrun("uname -m")
            # if not 64bit, remove the appropriate flag
            if arch.find("x86_64") == -1:
                lrun("sed -i.bak -r -e 's/-O2 -m64/-O2/g' Makefile")
            lrun("make")
            # copy executables to bin
            lrun("find . -perm /u=x -type f -exec cp {} %(bin_dir)s \;" % env)

def install_macs():
    """Install MACS 1.4.2
    Model-based Analysis for ChIP-Seq.
    http://liulab.dfci.harvard.edu/MACS/
    """
    version = "1.4.2"
    url = "https://github.com/downloads/taoliu/MACS/MACS-%s.tar.gz" % version
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        with lcd(dir_name):
            vlrun("python setup.py install")
            lrun("chmod a+rwx bin/*")
            lrun("find bin/. -perm /u=x -type f -exec cp {} %(bin_dir)s \;" % env)

def install_meme():
    """Install meme 4.9.1
    """
    url = "http://ebi.edu.au/ftp/software/MEME/4.9.1/meme_4.9.1.tar.gz"
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        with lcd(dir_name):
           lrun("./configure --prefix=%(meme_dir)s --with-url='http://meme.nbcr.net/meme' --with-perl=%(bin_dir)s/perl/bin/perl --with-python=%(bin_dir)s/python2.7" % env)
           lrun("make")
           lrun("make install")      
           
def install_sicer():
    """Install SICER 1.1
    """
    url = "http://home.gwu.edu/~wpeng/SICER_V1.1.tgz"
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        with lcd(dir_name):
            lrun("mv SICER %(sicer_dir)s" % env)          

# ================================================================================
# == Install chipseq pipeline and update config file

def install_chipseq():
    install_chipseq_pipeline()
    update_config()
          
def install_chipseq_pipeline():
    """Get the latest chipseq code from github.
    """
    with lcd(env.project_dir):
        lrun("wget --no-check-certificate -r https://github.com/crukci-bioinformatics/chipseq-pipeline/archive/master.zip -O master-pipeline.zip")
        lrun("unzip master-pipeline.zip")
    with lcd(env.chipseq_path):
        lrun("( ( echo '#!/usr/bin/env Rscript' ; echo 'RLIBSVar = \"%s\"' ; sed '1,2d' RScripts/Kick.r ) > RScripts/ChipSeq.r )" % env.r_lib_dir)
        lrun("chmod a+x RScripts/ChipSeq.r")
        
def update_config():
    import ConfigParser
    config = ConfigParser.SafeConfigParser()
    config_file = os.path.join(env.chipseq_config_path, "config.ini")
    if os.path.exists(config_file):
        config.read(config_file)
        inifile = open(config_file, 'w')

        config.set("Executables", "meme", os.path.join(env.bin_dir, "meme/bin/meme-chip"))
        config.set("Executables", "python", os.path.join(env.bin_dir, "python"))
        config.set("Executables", "perl", os.path.join(env.bin_dir, "perl/bin/perl"))
        config.set("Executables", "bwa", os.path.join(env.bin_dir, "bwa"))
        config.set("Executables", "samtools", os.path.join(env.bin_dir, "samtools"))
        config.set("Executables", "picard", os.path.join(env.bin_dir, "picard"))
        config.set("Executables", "rsync", os.path.join(env.bin_dir, "rsync"))
        config.set("Executables", "bedtools", env.bin_dir)
        config.set("Executables", "java", os.path.join(env.lib_dir, "%s/bin/java" % env.java_dir))
        config.set("Executables", "rexec", os.path.join(env.bin_dir, "Rscript"))
        config.set("Executables", "bigwig", os.path.join(env.bin_dir, "bedGraphToBigWig"))
        config.set("Executables", "gtftobed", os.path.join(env.bin_dir, "gtf2bed.pl"))
        config.set("Executables", "macs", os.path.join(env.bin_dir, "macs14"))
        config.set("Executables", "ame", os.path.join(env.bin_dir, "ame"))
        config.set("Executables", "sicer", os.path.join(env.bin_dir, "sicer"))
        config.set("Executables", "tpics", os.path.join(env.chipseq_pipeline, "CRI_TPICS/tpic.r"))
        config.set("Executables", "tpicszeta", os.path.join(env.chipseq_pipeline, "CRI_TPICS/zeta.pl"))
        config.set("Executables", "tpicscreatecoverage", os.path.join(env.chipseq_pipeline, "CRI_TPICS/create_coverate.pl"))

        config.set("Workflow", "executable", os.path.join(env.lib_dir, "workflow-manager/workflow-all-1.4-SNAPSHOT.jar"))
        config.set("Workflow", "taskdirectories", os.path.join(env.chipseq_path, "src/main/tasks"))
        config.set("Workflow", "summaryfile", os.path.join(env.test_dir, "tmp"))
        config.set("Workflow", "lsfoutputdirectory", os.path.join(env.test_dir, "tmp/joboutputs"))
        
        config.set("Libraries", "rlibs", env.r_lib_dir)
        config.set("Libraries", "pythonlibs", os.path.join(env.lib_dir, "python2.7/site-packages/"))
        config.set("Libraries", "perllibs", os.path.join(env.bin_dir, "perl/lib/site_perl/5.18.0/"))
        config.set("Libraries", "javalibs", "")

        config.set("meme parameters", "tfdb", os.path.join(env.annotation_dir, "jaspar_CORE/Jaspar_NonRedunadant.meme"))

        config.set("Genomes", "grch37", os.path.join(env.grch37_dir, "Homo_sapiens.GRCh37.67.dna.toplevel.fa"))
        config.set("Genomes", "hg18", "")
        config.set("Genomes", "mm9", os.path.join(env.mm9_dir, "Mus_musculus.NCBIM37.67.dna.toplevel.fa"))
        
        config.set("Gene Positions", "grch37", ":".join([os.path.join(env.mm9_dir, "Homo_sapiens.GRCh37.67.gtf"), os.path.join(env.mm9_dir, "hsapiens_gene_ensembl__transcript__main.txt")]))
        config.set("Gene Positions", "hg18", "")
        config.set("Gene Positions", "mm9", ":".join([os.path.join(env.mm9_dir, "Mus_musculus.NCBIM37.67.gtf"), os.path.join(env.mm9_dir, "mmusculus_gene_ensembl__transcript__main.txt")]))
        
        config.set("GeneSets", "mm9", "")
        
        config.set("Excluded Regions", "grch37", "No_Excluded")
        config.set("Excluded Regions", "hg18", "No_Excluded")
        config.set("Excluded Regions", "mm9", "No_Excluded")

        config.set("ExcludedRegions", "grch37", "No_Excluded")
        config.set("ExcludedRegions", "hg18", "No_Excluded")
        config.set("ExcludedRegions", "mm9", "No_Excluded")

        config.set("Chromosome Lengths", "grch37", "")
        config.set("Chromosome Lengths", "hg18", "")
        config.set("Chromosome Lengths", "mm9", "")	

        config.set("Sequence Dictionary", "grch37", "")
        config.set("Sequence Dictionary", "hg18", "")
        config.set("Sequence Dictionary", "mm9", "")	

        config.write(inifile)
        inifile.close()

# ================================================================================
# == Install hg19 and mm9 genomes 

def install_data():
    install_genomes()
    configure_meme()

def install_genomes():
	_make_dir(env.grch37_dir)
	grch37_urls = ["ftp://ftp.ensembl.org/pub/release-67/fasta/homo_sapiens/dna/Homo_sapiens.GRCh37.67.dna.toplevel.fa.gz", 
	    "ftp://ftp.ensembl.org/pub/release-67/gtf/homo_sapiens/Homo_sapiens.GRCh37.67.gtf.gz",
	    "ftp://ftp.ensembl.org/pub/release-67/mysql/ensembl_mart_67/hsapiens_gene_ensembl__exon_transcript__dm.txt.gz",
	    "ftp://ftp.ensembl.org/pub/release-67/mysql/ensembl_mart_67/hsapiens_gene_ensembl__transcript__main.txt.gz"]
	with lcd(env.grch37_dir):
	    for url in grch37_urls:
	        _fetch_and_unpack_genome(env.grch37_dir, url)

	_make_dir(env.mm9_dir)
	mm9_urls = ["ftp://ftp.ensembl.org/pub/release-67/fasta/mus_musculus/dna/Mus_musculus.NCBIM37.67.dna.toplevel.fa.gz",
	    "ftp://ftp.ensembl.org/pub/release-67/gtf/mus_musculus/Mus_musculus.NCBIM37.67.gtf.gz", 
	    "ftp://ftp.ensembl.org/pub/release-67/mysql/ensembl_mart_67/mmusculus_gene_ensembl__exon_transcript__dm.txt.gz",
	    "ftp://ftp.ensembl.org/pub/release-67/mysql/ensembl_mart_67/mmusculus_gene_ensembl__transcript__main.txt.gz"]
	with lcd(env.mm9_dir):
	    for url in mm9_urls:
	        _fetch_and_unpack_genome(env.mm9_dir, url)

def configure_meme():
    with lcd(env.annotation_dir):
	    URLForJasparAll =  "http://jaspar.genereg.net/html/DOWNLOAD/ARCHIVE/JASPAR2010/JASPAR_CORE/non_redundant/all_species/FlatFileDir/"
	    lrun('wget -r -nH --cut-dirs=2 --no-parent --reject=\"index.html*\" %s ' % (URLForJasparAll))
	    JasparLocation = os.path.join(env.annotation_dir, "ARCHIVE/JASPAR2010/JASPAR_CORE/non_redundant/all_species/FlatFileDir/") 
	    MemeJasparLocation = os.path.join(env.annotation_dir, "ARCHIVE/JASPAR2010/JASPAR_CORE/Jaspar_NonRedunadant.meme") 
	    ConvertCMD = os.path.join(env.bin_dir, "meme/bin/jaspar2meme  -pfm")
	    lrun("%s %s > %s" % (ConvertCMD,JasparLocation,MemeJasparLocation))
	    

# ================================================================================
# == Install Ikaros ChIP test data

def install_test():
    with lcd(env.project_dir):
        lrun('mv %s .' % os.path.join(env.chipseq_installer, 'chipseq-test'))

def fetch_testdata():
	_make_dir(env.testfq_dir)
	fq_urls = ["ftp://ftp.sra.ebi.ac.uk/vol1/fastq/SRR619/SRR619469/SRR619469.fastq.gz",
	    "ftp://ftp.sra.ebi.ac.uk/vol1/fastq/SRR619/SRR619470/SRR619470.fastq.gz",
	    "ftp://ftp.sra.ebi.ac.uk/vol1/fastq/SRR619/SRR619471/SRR619471.fastq.gz",
	    "ftp://ftp.sra.ebi.ac.uk/vol1/fastq/SRR619/SRR619472/SRR619472.fastq.gz",
	    "ftp://ftp.sra.ebi.ac.uk/vol1/fastq/SRR619/SRR619473/SRR619473.fastq.gz",
	    "ftp://ftp.sra.ebi.ac.uk/vol1/fastq/SRR619/SRR619474/SRR619474.fastq.gz"]
	with cd(env.testfq_dir):
	    for fq_url in fq_urls:
	        _fetch(env.testfq_dir, fq_url)



