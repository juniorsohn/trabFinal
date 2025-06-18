#!/bin/bash

ARQUIVO="../data/teste.csv"
BINARIO="./main"
REPETICOES=10

# Algoritmos do Scatter: ID e nome
declare -A ALGORITMOS=(
  [0]="ignore"
  [1]="basic_linear"
  [2]="binomial"
  [3]="linear_nb"
)

# Arquivo de saída
OUT="resultados_scatter.csv"
echo "algoritmo,tempo" > "$OUT"

for id in 0 1 2 3; do
    nome=${ALGORITMOS[$id]}
    echo "Rodando algoritmo $nome (ID $id)..."

    for i in $(seq 1 $REPETICOES); do
        tempo=$(
        mpirun -np 1 \
            --mca coll_tuned_use_dynamic_rules 1 \
            --mca coll_tuned_scatter_algorithm $id \
            $BINARIO $ARQUIVO 2>/dev/null | \
        grep "Tempo total de execução" | awk '{print $(NF-1)}')

        if [[ ! -z "$tempo" ]]; then
            echo "$nome,$tempo" >> "$OUT"
        else
            echo "Falha ao extrair tempo na execução $i (algoritmo $id)"
        fi
    done
done

echo -e "\n Testes concluídos. Resultados salvos em '$OUT'"
