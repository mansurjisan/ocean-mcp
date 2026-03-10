#!/bin/bash
#SBATCH --job-name=ufs-schism
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.out

set -euo pipefail

echo "UFS-Coastal (SCHISM) starting at $(date)"
echo "Run directory: $(pwd)"
echo "Nodes: $SLURM_JOB_NUM_NODES"
echo "Tasks: $SLURM_NTASKS"

# Load required modules (adjust for your HPC)
# module load ufs-coastal

# Run UFS
srun ./ufs_model

echo "UFS-Coastal completed at $(date)"
