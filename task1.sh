#!/bin/bash

hostname
source /home/szha0/anaconda2/etc/profile.d/conda.sh
conda activate test7
export NCCL_SOCKET_IFNAME=ib0
source /home/szha0/.matplotlib/matplotlibrc
python -m multiproc1 train.py --output_directory=output --log_directory=log --hparams=distributed_run=True -c output/blizzard-prosody-exp5/checkpoint_64000 --warm_start

