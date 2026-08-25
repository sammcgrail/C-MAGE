#!/bin/bash
#
# Submit the whole C-MAGE pipeline to SGE, on a node with a GPU.
#
# Run this from the repository root:
#
#   qsub MERMaid/pipeline_sub.sh
#   qsub MERMaid/pipeline_sub.sh --pdfs /path/to/papers --separated no
#
# Arguments are passed through to run_pipeline.sh unchanged.
#
# run_pipeline.sh submits itself through this script when it finds a queue and
# no local GPU, so it is rarely run by hand any more.
#
# Add your own address if you want mail:  #$ -M you@nd.edu  and  #$ -m abe
#
#$ -q gpu
#$ -l gpu_card=1
#$ -pe smp 1
#$ -N cmage
#$ -cwd
#$ -j y

# No `module load` here on purpose. Each environment carries the CUDA it needs,
# so a system one only competes with it: loading cuda/11.8 with cudnn/8.9.3,
# which is a CUDA 12 build, is what used to abort stage 2 partway through.
exec ./run_pipeline.sh "$@"
