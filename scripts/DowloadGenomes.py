

url_checsumsHG19 = "ftp://ftp.ensembl.org/pub/release-67/fasta/homo_sapiens/dna/CHECKSUMS"
url_wholegenomefastaHG19 = "ftp://ftp.ensembl.org/pub/release-67/fasta/homo_sapiens/dna/Homo_sapiens.GRCh37.67.dna.toplevel.fa.gz"
url_genesAsGTFHG19 = "ftp://ftp.ensembl.org/pub/release-67/gtf/homo_sapiens/Homo_sapiens.GRCh37.67.gtf.gz"
url_EnsemblToGeneHG19 = "ftp://ftp.ensembl.org/pub/release-67/mysql/ensembl_mart_67/hsapiens_gene_ensembl__gene__main.txt.gz"
url_EnsembleToExonTranscriptHG19 = "ftp://ftp.ensembl.org/pub/release-67/mysql/ensembl_mart_67/hsapiens_gene_ensembl__exon_transcript__dm.txt.gz"

url_checsumsMM10 = ftp://ftp.ensembl.org/pub/release-67/fasta/mus_musculus/dna/CHECKSUMS"
url_wholegenomefastaMM10 = ftp://ftp.ensembl.org/pub/release-67/fasta/mus_musculus/dna/Mus_musculus.NCBIM37.67.dna.toplevel.fa.gz"
url_genesAsGTFMM10 = "ftp://ftp.ensembl.org/pub/release-67/gtf/mus_musculus/Mus_musculus.NCBIM37.67.gtf.gz"
url_EnsemblToGeneMM10 = "ftp://ftp.ensembl.org/pub/release-67/mysql/ensembl_mart_67/mmusculus_gene_ensembl__exon_transcript__dm.txt.gz"
url_EnsembleToExonTranscriptMM10 = "ftp://ftp.ensembl.org/pub/release-67/mysql/ensembl_mart_67/mmusculus_gene_ensembl__gene__main.txt.gz"

with cd(work_dir):
    lrun("wget %s -O %s" % (url, os.path.split(url_wholegenomefastaHG19)[-1]))
    lrun("unzip %s -o %s" % (url, os.path.split(url_wholegenomefastaHG19)[-1]))
    lrun("wget %s -O %s" % (url, os.path.split(url_genesAsGTFHG19)[-1]))
    lrun("unzip %s -o %s" % (url, os.path.split(url_genesAsGTFHG19)[-1]))
    lrun("wget %s -O %s" % (url, os.path.split(url_EnsemblToGeneHG19)[-1]))
    lrun("unzip %s -o %s" % (url, os.path.split(url_EnsemblToGeneHG19)[-1]))
    lrun("wget %s -O %s" % (url, os.path.split(url_EnsembleToExonTranscriptHG19)[-1]))
    lrun("unzip %s -o %s" % (url, os.path.split(url_EnsembleToExonTranscriptHG19)[-1]))    

with cd(work_dir):
    lrun("wget %s -O %s" % (url, os.path.split(url_wholegenomefastaMM10)[-1]))
    lrun("unzip %s -o %s" % (url, os.path.split(url_wholegenomefastaMM10)[-1]))
    lrun("wget %s -O %s" % (url, os.path.split(url_genesAsGTFMM10)[-1]))
    lrun("unzip %s -o %s" % (url, os.path.split(url_genesAsGTFMM10)[-1]))
    lrun("wget %s -O %s" % (url, os.path.split(url_EnsemblToGeneMM10)[-1]))
    lrun("unzip %s -o %s" % (url, os.path.split(url_EnsemblToGeneMM10)[-1]))
    lrun("wget %s -O %s" % (url, os.path.split(url_EnsembleToExonTranscriptMM10)[-1]))
    lrun("unzip %s -o %s" % (url, os.path.split(url_EnsembleToExonTranscriptMM10)[-1]))    

