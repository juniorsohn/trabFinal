#!/bin/bash
#
#SBATCH --job-name=scatterTest           # nome do job
#SBATCH --nodes=7                        # número de nós desejados
#SBATCH --ntasks=96                      # total de processos MPI (ranks)
#SBATCH --cpus-per-task=1                # CPUs por tarefa; ajuste se for multithread
#SBATCH --time=01:00:00                  # tempo máximo de execução
#SBATCH --output=saida_scatter_%j.log    # arquivo de saída padrão (%j = jobid)
#SBATCH --error=erro_scatter_%j.log      # arquivo de erro
# Outras diretivas SLURM que precisar, ex: --partition, --account, etc.

# 1) Variáveis de ambiente SLURM
# SLURM_JOB_NODELIST: lista de nós alocados
# SLURM_NTASKS: número total de tasks (ranks MPI)
# SLURM_NTASKS_PER_NODE: quantas tasks por nó
# Exemplos de uso e referência em documentação SLURM :contentReference[oaicite:0]{index=0}.

# 2) Parâmetros do seu experimento
ARQUIVO="../data/eventos_maior.csv"
BINARIO="./main"
REPETICOES=10
INTERFACE="10.10.40.0/24"
# NP = número de processos MPI; garantimos que corresponde à alocação SLURM
NP=$SLURM_NTASKS

# Algoritmos do Scatter: ID e nome
declare -A ALGORITMOS=(
  [0]="ignore"
  [1]="basic_linear"
  [2]="binomial"
  [3]="linear_nb"
)

# Arquivo de saída; crie diretório se necessário antes de submeter
OUT="../output/resultados_scatter.csv"
if [[ ! -f "$OUT" ]]; then
    echo "algoritmo,tempo,np" > "$OUT"
fi

# 3) (Opcional) Gerar hostfile dinamicamente se seu MPI não detectar SLURM automaticamente.
# Se Open MPI estiver compilado com suporte a SLURM/PMIx/PMI, normalmente não é necessário.
# Mas, caso queira usar hostfile para suas opções MPI antigas:
# scontrol show hostnames $SLURM_NODELIST > hosts.txt

# 4) Loop de execuções
for id in 0 1 2 3; do
    nome=${ALGORITMOS[$id]}
    echo "Rodando algoritmo $nome (ID $id) com np=$NP..."
    for i in $(seq 1 $REPETICOES); do
        # Exemplo de uso de mpirun mantendo suas opções anteriores:
        # Se quiser usar hostfile gerado:
        # tempo=$(mpirun --hostfile hosts.txt \
        #               --mca btl_tcp_if_include "$INTERFACE" \
        #               --mca coll_tuned_use_dynamic_rules 1 \
        #               --mca coll_tuned_scatter_algorithm $id \
        #               -np $NP \
        #               "$BINARIO" "$ARQUIVO" 2> run_output.log | \
        #               grep "Tempo total de execução" | awk '{print $(NF-1)}')
        #
        # Se MPI detecta SLURM automaticamente, basta:
        tempo=$(
          mpirun --mca btl_tcp_if_include "$INTERFACE" \
                 --mca coll_tuned_use_dynamic_rules 1 \
                 --mca coll_tuned_scatter_algorithm $id \
                 -np $NP \
                 "$BINARIO" "$ARQUIVO" 2> run_output.log | \
          grep "Tempo total de execução" | awk '{print $(NF-1)}'
        )
        if [[ -n "$tempo" ]]; then
            echo "$nome,$tempo,$NP" >> "$OUT"
        else
            echo "Falha ao extrair tempo na execução $i (algoritmo $id)"
            # Opcional: salvar log para debug, ex:
            # cp run_output.log logs/run_${nome}_${i}_job${SLURM_JOB_ID}.log
        fi
    done
done

echo -e "\nTestes concluídos. Resultados salvos em '$OUT'"
