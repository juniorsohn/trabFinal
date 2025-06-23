#!/bin/bash

<<<<<<< HEAD
ARQUIVO="../data/eventos_maior.csv"
BINARIO="./main"
REPETICOES=10
HOSTS="hosts.txt"
INTERFACE="10.10.40.0/24"
=======
ARQUIVO="../data/eventos.csv"
BINARIO="./main"
REPETICOES=10
HOSTS="hosts.txt"
INTERFACE="10.20.221.0/24"
>>>>>>> 5455d70157b0833ee19c5344b1c5b86e5965c95e
NP=$1 #recebe via linha de comando

# Algoritmos do Scatter: ID e nome
declare -A ALGORITMOS=(
  [0]="ignore"
  [1]="basic_linear"
  [2]="binomial"
  [3]="linear_nb"
)

# Arquivo de saída
<<<<<<< HEAD
OUT="../output/resultados_scatter.csv"
=======
OUT="resultados_scatter.csv"
>>>>>>> 5455d70157b0833ee19c5344b1c5b86e5965c95e

# Se o arquivo ainda não existe, adiciona o cabeçalho
if [[ ! -f "$OUT" ]]; then
    echo "algoritmo,tempo,np" > "$OUT"
fi

for id in 0 1 2 3; do
    nome=${ALGORITMOS[$id]}
    echo "Rodando algoritmo $nome (ID $id) com np=$NP..."

    for i in $(seq 1 $REPETICOES); do
        tempo=$(
        mpirun --machinefile "$HOSTS" \
               --mca btl_tcp_if_include "$INTERFACE" \
               --mca coll_tuned_use_dynamic_rules 1 \
               --mca coll_tuned_scatter_algorithm $id \
               -np $NP \
<<<<<<< HEAD
               "$BINARIO" "$ARQUIVO" 2> run_output.log 2>&1 | \
=======
               "$BINARIO" "$ARQUIVO" 2>/dev/null | \
>>>>>>> 5455d70157b0833ee19c5344b1c5b86e5965c95e
        grep "Tempo total de execução" | awk '{print $(NF-1)}')

        if [[ ! -z "$tempo" ]]; then
            echo "$nome,$tempo,$NP" >> "$OUT"
        else
            echo "Falha ao extrair tempo na execução $i (algoritmo $id)"
        fi
    done
done

echo -e "\n Testes concluídos. Resultados salvos em '$OUT'"
