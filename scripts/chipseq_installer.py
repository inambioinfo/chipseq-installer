"""
Created by Anne Pajon on 11 Apr 2013

Copyright (c) 2012 Cancer Research UK - Cambridge Institute.

This source file  is licensed under the Academic  Free License version
3.0 available at http://www.opensource.org/licenses/AFL-3.0.

Permission is  hereby granted  to reproduce, translate,  adapt, alter,
transform, modify, or arrange  this source file (the 'Original Work');
to distribute  or communicate copies of  it under any  license of your
choice that does  not contradict the terms and  conditions; to perform
or display the Original Work publicly.

THE ORIGINAL WORK  IS PROVIDED UNDER THIS LICENSE ON  AN 'AS IS' BASIS
AND WITHOUT  WARRANTY, EITHER  EXPRESS OR IMPLIED,  INCLUDING, WITHOUT
LIMITATION,  THE WARRANTIES  OF  NON-INFRINGEMENT, MERCHANTABILITY  OR
FITNESS FOR A PARTICULAR PURPOSE. THE ENTIRE RISK AS TO THE QUALITY OF
THE ORIGINAL WORK IS WITH YOU.

Ideas taken from:
- https://github.com/chapmanb/bcbb/blob/master/galaxy/galaxy_fabfile.py
- https://github.com/chapmanb/cloudbiolinux

Fabric  deployment file  to set  up a  local Galaxy  instance.  Fabric
(http://docs.fabfile.org) is used to manage the automation of a remote
server.

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
env.project_dir = os.getcwd()
env.tmp_dir = os.path.join(env.project_dir, 'tmp')
env.bin_dir = os.path.join(env.project_dir, 'bin')
env.lib_dir = os.path.join(env.project_dir, 'lib')
env.r_lib_dir = os.path.join(env.project_dir, 'lib/R/library')
env.chipseq_build_path = os.path.join(env.project_dir, 'chipseq-build')
env.chipseq_path = os.path.join(env.project_dir, 'Process10')
env.use_sudo = False

# ================================================================================
# == Host specific setup

def local():
    """Setup environment for local installation on lbio for running chipseq jobs on the cluster.
    """
    env.r_dir = env.project_dir
    env.env_setup = ('env.bashrc')

# ================================================================================
# == Fabric instructions

def deploy():
    """Setup environment, install dependencies and tools
    and deploy chipseq pipeline
    """
    setup_environment()
    install_dependencies()
    install_tools()
    install_chipseq()

# ================================================================================
# == Decorators and context managers

def _if_not_installed(pname):
    """Decorator that checks if a callable program is installed.
    """
    def argcatcher(func):
        def decorator(*args, **kwargs):
            with settings(
                hide('warnings', 'running', 'stdout', 'stderr'),
                warn_only=True):
                result = vlrun(pname)
                if result.return_code == 127:
                    return func(*args, **kwargs)
        return decorator
    return argcatcher

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

# -- Standard build utility simplifiers

def lexists(path):
    return os.path.exists(path)

def vlrun(command):
    """Run a command in a virtual environment. This prefixes the run command with the source command.
    Usage:
        vlrun('pip install tables')
    """
    source = 'source %(project_dir)s/bin/activate && source %(project_dir)s/%(env_setup)s && ' % env
    return lrun(source + command,shell='/bin/bash')    

def _make_dir(path):
    with settings(warn_only=True):
        if lrun("test -d %s" % path).failed:
            lrun("mkdir -p %s" % path)

def _get_expected_file(url):
    tar_file = os.path.split(url)[-1]
    safe_tar = "--pax-option='delete=SCHILY.*,delete=LIBARCHIVE.*'"
    exts = {(".tar.gz", ".tgz") : "tar %s -xzpf" % safe_tar,
            (".tar.bz2",): "tar %s -xjpf" % safe_tar,
            (".zip",) : "unzip"}
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

def _fetch_and_unpack(path, url, need_dir=True):
    tar_file, dir_name, tar_cmd = _get_expected_file(url)
    if not lexists(tar_file):
        lrun("wget --no-check-certificate %s" % url)
        lrun("%s %s" % (tar_cmd, tar_file))
    return _safe_dir_name(path, dir_name, need_dir)

def _configure_make(env, options=None):
    if options:
        lrun("./configure --disable-error --prefix=%s %s" % (env.project_dir, options))
    else:
        lrun("./configure --disable-error --prefix=%s" % (env.project_dir))
    lrun("make")
    lrun("make install")

def _python_build(env, option=None):
    vlrun("python setup.py install")

def _get_install(url, env, make_command, make_options=None):
    """Retrieve source from a URL and install in our system directory.
    """
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        with lcd(dir_name):
            make_command(env, make_options)

def _make_copy(find_cmd=None, premake_cmd=None, do_make=True):
    def _do_work(env,options=None):
        if premake_cmd:
            premake_cmd()
        if do_make:
            lrun("make")
        if find_cmd:
            install_dir = env.bin_dir
            for fname in lrun(find_cmd).split("\n"):
		print fname
		lrun("cp -rf %s %s" % (fname.rstrip("\r"), install_dir))
    return _do_work
    
def setup_environment():
    """Copy adhoc environment variables
    """
    lrun('cp %(chipseq_build_path)s/%(env_setup)s %(project_dir)s/%(env_setup)s' % env)
    _make_dir(env.tmp_dir)

# ================================================================================
# == Required dependencies to install chipseq pipeline

def install_dependencies():
    """Install chipseq dependencies:
    - R & libraries
    - Perl & libraries
    - Python libraries: NumPy, Cython, NumExpr, PyTables, RPy, RPy2, bx-python
    - Rich Bowers' workflow
    """
    install_r()
    install_r_libraries()
    install_perl()
    install_perl_libraries()
    install_python_libraries()
    install_maven()
    #install_workflow()

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
    """Install R 2.15.2
    """
    lrun("mkdir -p %(r_lib_dir)s" % env)
    url = "http://cran.r-project.org/src/base/R-2/R-2.15.0.tar.gz"
    option = "--enable-R-shlib"
    if not lexists(os.path.join(env.r_dir, "bin/R")):
        _get_install(url, env, _configure_make, option)
        # create symlinks in bin for installation on mac only
        if not lexists(os.path.join(env.bin_dir, "R")):
            lrun('ln -fs %(r_dir)s/bin/R %(bin_dir)s/R' % env)
            lrun('ln -fs %(r_dir)s/bin/Rscript %(bin_dir)s/Rscript' % env)

def install_r_libraries():
    """Install R libraries listed in r-libraries.yaml needed to run CRI tools
    plus GenometriCorr & RMySQL_0.9-3
    """
    # Load list of R libraries to install
    config_file = open(os.path.join(env.chipseq_build_path, "scripts/r-libraries.yaml"), 'r')
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
    #install_fn = """
    #repo.installer <- function(repos, install.fn) {
    #  update.or.install <- function(pname) {
    #    if (pname %%in%% installed.packages())
    #      update.packages(lib.loc=c(pname), repos=repos, ask=FALSE,instlib=\"%(r_lib_dir)s\")
    #    else
    #      install.fn(pname,lib=\"%(r_lib_dir)s\")
    #  }
    #}
    #""" % env
    #lrun("echo '%s' >> %s" % (install_fn, out_file))
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
    # Run the script and then get rid of it
    vlrun("%s %s" % (os.path.join(env.bin_dir, "Rscript"),out_file))
    #lrun("rm -f %s" % out_file)

def install_perl_libraries():
    """Install perl library HTML Template
    """
    urlHTMLTemplate = "http://search.cpan.org/CPAN/authors/id/W/WO/WONKO/HTML-Template-2.94.tar.gz"
    perl = os.path.join(env.bin_dir,"perl-5.18.0","bin","perl")
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, urlHTMLTemplate)
	tmp_HTMLTemplate = os.path.join(env.tmp_dir,"HTML-Template-2.94")        
        with lcd(tmp_HTMLTemplate):
            lrun("%s Makefile.PL"  % (perl))
            lrun("make")
            vlrun("make install")

def install_perl():
    """Install perl
    """
    url = "http://www.cpan.org/src/5.0/perl-5.18.0.tar.gz"
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        install_dir = os.path.join(env.bin_dir,"perl-5.18.0")
        tmp_perl = os.path.join(env.tmp_dir,"perl-5.18.0")
        lrun("mkdir -p %s" % install_dir)
        with lcd(tmp_perl):
            lrun("sh Configure -de -Dprefix='%s'" % (install_dir))
            lrun("make")
            lrun("make install")

def install_maven():
    url = "http://mirror.gopotato.co.uk/apache/maven/maven-3/3.1.0/binaries/apache-maven-3.1.0-bin.tar.gz"
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        lrun("mv apache-maven-3.1.0 %s" % (env.bin_dir))
        
def install_workflow():
    """Checkout the latest chipseq code from svn repository and update.
    """
    mvnToUse = os.path.join(env.bin_dir,"apache-maven-3.1.0","bin","mvn")
    with lcd(env.tmp_dir):
         lrun('svn co  svn://uk-cri-lbio01/workflow/trunk/ Workflow1.4')
         with lcd("Workflow1.4"):              
             lrun('%s clean install' % (mvnToUse))

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
        _fetch_and_unpack(env.tmp_dir, url, False)
        with lcd("bedtools-2.17.0"):
            lrun("make clean")
            lrun("make all")
            lrun("find bin/. -perm /u=x -type f -exec cp {} %(bin_dir)s \;" % env)

def install_picard():
    version = "1.96"
    url = 'http://downloads.sourceforge.net/project/picard/picard-tools/%s/picard-tools-%s.zip' % (version, version)
    pkg_name = 'picard'
    install_dir = env.tmp_dir
    work_dir = env.tmp_dir
    PicardDir = os.path.join(env.bin_dir, "picard")
    lrun("mkdir -p %s" % PicardDir)
    with cd(work_dir):
        lrun("wget %s -O %s" % (url, os.path.split(url)[-1]))
        lrun("unzip -o %s" % (os.path.split(url)[-1]))
        lrun("mv picard-tools-%s/*.jar %s" % (version, PicardDir))

def install_bwa():
    """BWA:  aligns short nucleotide sequences against a long reference sequence.
    http://bio-bwa.sourceforge.net/
    """
    version = "0.7.5a"
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
    """Model-based Analysis for ChIP-Seq.
    http://liulab.dfci.harvard.edu/MACS/
    """
    default_version = "1.4.2"
    version = default_version
    url = "https://github.com/downloads/taoliu/MACS/MACS-%s.tar.gz" % version
    work_dir = env.tmp_dir
    dir_name = _fetch_and_unpack(env.tmp_dir, url)
    with lcd("MACS-1.4.2"):
        vlrun("python setup.py install")
    lrun("mv MACS-1.4.2 %s" % (env.bin_dir))
    #lrun("rm -rf %s" % ("MACS-1.4.2"))

def install_meme():
    """
    """
    majorversion = "4.9.0"
    minorversion = "4"
    version  = majorversion+"_"+minorversion
    url = "http://ebi.edu.au/ftp/software/MEME/%s/meme_%s.tar.gz" % (majorversion,version)
    memetmp = os.path.join(env.tmp_dir,"meme"+"_"+majorversion)
    memebin = os.path.join(env.bin_dir,"meme"+"_"+majorversion)
    with lcd(env.tmp_dir):
        dir_name = _fetch_and_unpack(env.tmp_dir, url)
        with lcd(memetmp):
           lrun("./configure --prefix=%s --with-url='http://meme.nbcr.net/meme'" % (memebin))
           lrun("make")
           lrun("make install")      
           
def install_sicer():
   url = "http://home.gwu.edu/~wpeng/SICER_V1.1.tgz"
   with lcd(env.tmp_dir):
      dir_name = _fetch_and_unpack(env.tmp_dir, url)
      lrun("mv SICER_V1.1 %s" % (env.bin_dir))          

# ================================================================================
# == Install chipseq pipeline
      
def install_chipseq():
    """Checkout the latest chipseq code from public svn repository and update.
    """
    update = True
    if env.chipseq_path is not None:
        if not lexists(env.chipseq_path):
            update = False
            with lcd(os.path.split(env.chipseq_path)[0]):
                lrun('svn co svn://uk-cri-lbio01/pipelines/chipseq/branches/BRANCH05')
        with lcd(env.chipseq_path):
            if update:
                lrun('svn update')



