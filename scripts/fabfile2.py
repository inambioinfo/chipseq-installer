"""
Created by Anne Pajon on 11 Apr 2013

Copyright (c) 2012 Cancer Research UK - Cambridge Research Institute.

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
    fab -f scripts/fabfile.py local deploy_chipseq
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

def deploy_chipseq():
    """Deploy chipseq pipeline and install dependencies
    """
    setup_environment()
    install_dependencies()
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
    if url.startswith(("git", "svn", "hg", "cvs")):
        lrun(url)
        base = os.path.basename(url.split()[-1])
        return os.path.splitext(base)[0]
    else:
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

# ================================================================================
# == Required dependencies

def install_dependencies():
    """Install chipseq dependencies
    - Python libraries: NumPy, Cython, NumExpr, PyTables, RPy, RPy2, bx-python
    - R & libraries
    - UCSC tools: liftOver, TwoBitToFa, FaToTwoBit, BedToBigBed, WigToBigWig, BedGraphToBigWig
    - samtools
    - BEDTools

    Not yet implemented:
    - bwa = http://sourceforge.net/projects/bio-bwa/files/latest/download?source=files
    - picard = http://sourceforge.net/projects/picard/files/picard-tools/1.86/picard-tools-1.86.zip/download
    - macs = https://github.com/downloads/taoliu/MACS/MACS-1.4.2-1.tar.gz
    - meme = http://ebi.edu.au/ftp/software/MEME/4.9.0/meme_4.9.0_4.tar.gz
    - ame = http://acb.qfab.org/acb/ame/ame-bin-linux-ubuntu910-x86.tar.gz
    """
    install_r()
    install_r_libraries()
    install_perl()
    install_perl_libraries()
    install_python_libraries()
    install_ucsc_tools()
    install_samtools()
    install_bedtools()
    install_picard()    
    install_bwa()
    install_macs()
    install_meme()
    install_sicer()
    install_maven()
    install_workflow()

def install_python_libraries():
    """Install Python libraries
    """
    vlrun("pip install fluent-logger")
    vlrun("pip install numpy")
    vlrun("pip install cython")
    vlrun("pip install numexpr")
    vlrun("pip install pyyaml")
    vlrun("pip install rpy2")
    vlrun("pip install pysam")
    vlrun("pip install scipy")
    _install_bx_python()
    _install_rpy_lib()

@_if_not_python_lib("bx")
def _install_bx_python():
    """Install bx-python 0.7.1
    """
    url = "http://pypi.python.org/packages/source/b/bx-python/bx-python-0.7.1.tar.gz"
    vlrun("pip install %s" % url)

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

def install_perl_libraries():
    """Install RPy 1.0.3
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
            # copy executables to bin
            #lrun("find . -perm /u=x -type f -exec cp {} %(bin_dir)s \;" % env)

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
         lrun('svn co  svn+ssh://carrol09@uk-cri-lbio01/data/mib-cri/SVNREP/workflow/trunk/ Workflow1.4')
         with lcd("Workflow1.4"):              
             lrun('%s clean install' % (mvnToUse))

    

#@_if_not_installed("samtools")
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

#@_if_not_installed("bedtools")            
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




# ================================================================================
# == chipseq specific

def setup_environment():
    """Copy adhoc environment variables
    """
    lrun('cp %(chipseq_build_path)s/%(env_setup)s %(project_dir)s/%(env_setup)s' % env)
    _make_dir(env.tmp_dir)

def install_chipseq():
    """Checkout the latest chipseq code from svn repository and update.
    """
    update = True
    if env.chipseq_path is not None:
        if not lexists(env.chipseq_path):
            update = False
            with lcd(os.path.split(env.chipseq_path)[0]):
                lrun('svn co  svn://uk-cri-lbio01/pipelines/chipseq/branches/BRANCH05')
        with lcd(env.chipseq_path):
            if update:
                lrun('svn update')


def install_macs():
    """Model-based Analysis for ChIP-Seq.
    http://liulab.dfci.harvard.edu/MACS/
    """
    default_version = "1.4.2"
    version = default_version
    url = "https://github.com/downloads/taoliu/MACS/" \
          "MACS-%s.tar.gz" % version
    work_dir = env.tmp_dir
    dir_name = _fetch_and_unpack(env.tmp_dir, url)
    lrun("echo %s" % dir_name)
    with lcd("MACS-1.4.2"):
        vlrun("python setup.py install")
    lrun("mv MACS-1.4.2 %s" % (env.bin_dir))
    #lrun("rm -rf %s" % ("MACS-1.4.2"))



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


def install_meme():
    """BWA:  aligns short nucleotide sequences against a long reference sequence.
    http://bio-bwa.sourceforge.net/
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

       
def install_picard():
    version = "1.96"
    url = 'http://downloads.sourceforge.net/project/picard/picard-tools/%s/picard-tools-%s.zip' % (version, version)
    pkg_name = 'picard'
    #install_dir = env.system_install
    #install_cmd = env.safe_sudo if env.use_sudo else env.safe_run
    install_dir = env.tmp_dir
    #if not env.safe_exists(install_dir):
    #lrun("mkdir -p %s" % install_dir)
    #with _make_tmp_dir() as work_dir:
    work_dir = env.tmp_dir
    PicardDir = os.path.join(env.bin_dir,"picard")
    lrun("mkdir -p %s" % PicardDir )
    with cd(work_dir):
        lrun("wget %s -O %s" % (url, os.path.split(url)[-1]))
        lrun("unzip -o %s" % (os.path.split(url)[-1]))
        lrun("mv picard-tools-%s/*.jar %s" % (version, PicardDir))
    #_update_default(env, install_dir)
    # set up the jars directory
    #jar_dir = os.path.join(bin_dir, 'picard')
    #if not env.safe_exists(jar_dir):
    #    install_cmd("mkdir -p %s" % jar_dir)
    #tool_dir = os.path.join(env.galaxy_tools_dir, pkg_name, 'default')
    #install_cmd('ln --force --symbolic %s/*.jar %s/.' % (tool_dir, jar_dir))
    #lrun('chown --recursive %s' % (PicardDir))

@_if_not_installed(None)
def install_fastx_toolkit(env):
    version = env.tool_version
    gtext_version = "0.6.1"
    url_base = "http://hannonlab.cshl.edu/fastx_toolkit/"
    fastx_url = "%sfastx_toolkit-%s.tar.bz2" % (url_base, version)
    gtext_url = "%slibgtextutils-%s.tar.bz2" % (url_base, gtext_version)
    pkg_name = 'fastx_toolkit'
    install_dir = os.path.join(env.galaxy_tools_dir, pkg_name, version)
    with _make_tmp_dir() as work_dir:
        with cd(work_dir):
            env.safe_run("wget %s" % gtext_url)
            env.safe_run("tar -xjvpf %s" % (os.path.split(gtext_url)[-1]))
            install_cmd = env.safe_sudo if env.use_sudo else env.safe_run
            with cd("libgtextutils-%s" % gtext_version):
                env.safe_run("./configure --prefix=%s" % (install_dir))
                env.safe_run("make")
                install_cmd("make install")
            env.safe_run("wget %s" % fastx_url)
            env.safe_run("tar -xjvpf %s" % os.path.split(fastx_url)[-1])
            with cd("fastx_toolkit-%s" % version):
                env.safe_run("export PKG_CONFIG_PATH=%s/lib/pkgconfig; ./configure --prefix=%s" % (install_dir, install_dir))
                env.safe_run("make")
                install_cmd("make install")
    
    
    @_if_not_installed("fastqc")
    def install_fastqc(env):
        """ This tool is installed in Galaxy's jars dir """
        version = env.tool_version
        url = 'http://www.bioinformatics.bbsrc.ac.uk/projects/fastqc/fastqc_v%s.zip' % version
        pkg_name = 'FastQC'
        install_dir = os.path.join(env.galaxy_jars_dir)
        install_cmd = env.safe_sudo if env.use_sudo else env.safe_run
        if not env.safe_exists(install_dir):
            install_cmd("mkdir -p %s" % install_dir)
        with cd(install_dir):
            install_cmd("wget %s -O %s" % (url, os.path.split(url)[-1]))
            install_cmd("unzip -u %s" % (os.path.split(url)[-1]))
            install_cmd("rm %s" % (os.path.split(url)[-1]))
            with cd(pkg_name):
                install_cmd('chmod 755 fastqc')
            install_cmd('chown --recursive %s:%s %s' % (env.galaxy_user, env.galaxy_user, pkg_name))
