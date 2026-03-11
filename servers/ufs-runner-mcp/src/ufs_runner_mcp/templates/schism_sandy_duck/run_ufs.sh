#!/bin/bash
#SBATCH --job-name={{job_name}}
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.out
#SBATCH --nodes={{nodes}}
#SBATCH --ntasks-per-node={{tasks_per_node}}
#SBATCH --time={{wall_minutes}}
#SBATCH --exclusive

set -eux
echo -n " $( date +%s )," > job_timestamp.txt

set +x
MACHINE_ID=${MACHINE_ID:-ursa}
source ./module-setup.sh
module use $PWD/modulefiles
module load modules.fv3
module list
set -x

ulimit -s unlimited

echo "Model started: $(date)"

export OMP_STACKSIZE=512M
export KMP_AFFINITY=scatter
export OMP_NUM_THREADS=1
export ESMF_RUNTIME_PROFILE=ON
export ESMF_RUNTIME_PROFILE_OUTPUT="SUMMARY"
export I_MPI_EXTRA_FILESYSTEM=ON
export FI_MLX_INJECT_LIMIT=0

# Create output directories
mkdir -p {{output_dir}} {{restart_dir}}

sync && sleep 1

srun --label -n {{total_tasks}} ./ufs_model

echo "Model ended: $(date)"
echo -n " $( date +%s )," >> job_timestamp.txt
