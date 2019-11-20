# -*- coding: utf-8 -*-

"""
Container entry script for converting/placing Illumina NGS output.

Requires certain environment variables to be set for operatation:
  - run_path : eg: "/illumina/nextseq_01/NextSeqOutput/XYZ123". Full path should
   be mounted for the container and "XYZ123" would be the run_id to be used.
   Type of run (MiSeq or NextSeq) will be gathered from this path.
  - sample_path: eg: "/analysis/samples". Full path should be mounted for the
  container and reads for each sample will be put under here.
  (eg: /analysis/samples/abc1/reads/read_1.fastq.gz)

Overall function:
 - NextSeq runs will be put through bcl2fastq conversion.
   - A library sheet name "SampleSheet.csv" is expected in run path. This will
   be converted to a usable sample sheet for bcl2fastq.
 - Miseq runs will only get the reads placed in proper sample folder structure.
 - Once the read files are distributed, a flag file (sample.ready) will be
  placed in the root folder of specific sample. This can be used to initiate
  analysis pipelines.
"""

import sys
import re
from os import environ, makedirs
from os.path import basename, join, exists
from subprocess import Popen, PIPE
from glob import glob
from shutil import copyfile
from pathlib import Path

# get necessary details
run_path = environ['run_path']
run_id = basename(run_path)
nextseq = True if 'nextseq' in run_path else False
sample_path = environ['sample_path']

# deal with nextseq runs
if nextseq:

    # convert library sheet to sample sheet
    process_l2s = Popen(['library_to_samplesheet',
                         '--run_parameters', f'{run_path}/RunParameters.xml',
                         '--library_sheet',  f'{run_path}/SampleSheet.csv',
                         '--output', f'{run_path}/SampleSheet_ready.csv',
                         ],
                        stdout=PIPE, stderr=PIPE)
    process_l2s.wait()
    stdout, stderr = process_l2s.communicate()
    # return error message is something went wrong
    if process_l2s.returncode != 0:
        print(f'Library to sample sheet failed with return code '
              f'{process_l2s.returncode}.\n'
              f'Error message:\n{stderr}')
        sys.exit(-1)

    # run bcl2fastq conversion for nextseq data
    process_b2f = Popen(['bcl2fastq',
                         '--runfolder-dir', f'{run_path}',
                         '--sample-sheet', f'{run_path}/SampleSheet_ready.csv',
                         '--processing-threads', '8',
                         '--loading-threads', '4',
                         '--writing-threads', '4'
                         ],
                        stdout=PIPE, stderr=PIPE)
    process_b2f.wait()
    stdout, stderr = process_b2f.communicate()
    # return error message is something went wrong
    if process_b2f.returncode != 0:
        print(f'Bcl2fastq failed with return code '
              f'{process_b2f.returncode}.\n'
              f'Error message:\n{stderr}')
        sys.exit(-1)

# nothing to do for miseq as fastq files are generated by the sequencer

# Place reads (nextseq or miseq) in the samples path
# Find fastq files under run_path and collect sample vs files in a dictionary
p = re.compile('^(.*)(_S[0-9]+)(_L00[1-4])(_R[12])(_[0-9]{3}[\S]*\.fastq\.gz)$')
samples_to_files = dict()
for file in glob(f'{run_path}/**/*.gz', recursive=True):
    fastq = basename(file)
    pm = p1.match(fastq)

    if pm:
        sample = pm.group(1)
        # Ignore undetermined reads
        if sample == "Undetermined":
            continue
        elif sample in samples_to_files:
            samples_to_files[sample].append(file)
        else:
            sample_to_files[sample] = [file]

# copy read files to sample volume (and collect non unique sample ids).
used_sample_ids = list()
for sample, files in samples_to_files.items():
    full_sample_path = join(sample_path, sample)
    # check if sample id is already used
    if exists(full_sample_path):
        used_sample_ids.append(sample)
        continue
    else:
        full_read_path = join(full_sample_path, 'reads', 'fastq')
        makedirs(full_read_path)
        for file in files:
            copyfile(file, full_read_path)
        Path(join(full_sample_path, f'{sample}.ready')).touch()

# finish and report:
if len(used_sample_ids) == 0:
    sys.exit(0)
else:
    print('Run contains samples with previously used IDs:\n',
          '\n'.join([sample for sample in sorted(used_sample_ids)]),
          '\nReads from these are left in run path.')
    sys.exit(1)










