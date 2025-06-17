#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>
#include <limits.h>   // para INT_MAX

int cmp_int(const void *a, const void *b) {
    return (*(int*)a - *(int*)b);
}

int main(int argc, char *argv[]) {
    int rank, size;
    int N = 16;             // numero real de elementos
    int total_n;            // N ajustado (com dummies)
    int *data = NULL;       // só no root
    MPI_Init(&argc, &argv);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    if (rank == 0) {
        // Inicializa os dados reais
        data = malloc(sizeof(int) * N);
        srand(0);
        for (int i = 0; i < N; i++) {
            data[i] = rand() % 100;
        }
        // Calcula padding para múltiplo de 'size'
        int rem = N % size;
        int pad = (rem == 0 ? 0 : size - rem);
        total_n = N + pad;

        // Realoca e preenche dummies
        data = realloc(data, sizeof(int) * total_n);
        for (int i = N; i < total_n; i++) {
            data[i] = INT_MAX;  // valor sentinela
        }

        printf("Unsorted array (with %d dummies):\n", pad);
        for (int i = 0; i < total_n; i++) {
            printf("%d ", data[i]);
        }
        printf("\n\n");
    }

    // 1) Broadcast do tamanho ajustado
    MPI_Bcast(&total_n, 1, MPI_INT, 0, MPI_COMM_WORLD);

    // Cada processo calcula quantos elementos receberá
    int local_n = total_n / size;
    int *local = malloc(sizeof(int) * local_n);

    // 2) Scatter dos dados (agora total_n é múltiplo de size)
    MPI_Scatter(data,   local_n, MPI_INT,
                local, local_n, MPI_INT,
                0, MPI_COMM_WORLD);

    // 3) Ordena localmente
    qsort(local, local_n, sizeof(int), cmp_int);

    // … (restante do Sample Sort igual ao código anterior) …
    // 4) Escolha de samples, gather, pivôs, bcast…
    int samples_per_proc = size;
    int *local_samples = malloc(sizeof(int) * samples_per_proc);
    for (int i = 0; i < samples_per_proc; i++) {
        int idx = i * local_n / samples_per_proc;
        local_samples[i] = local[idx];
    }

    int *all_samples = NULL;
    if (rank == 0) all_samples = malloc(sizeof(int) * size * samples_per_proc);
    MPI_Gather(local_samples, samples_per_proc, MPI_INT,
               all_samples, samples_per_proc, MPI_INT,
               0, MPI_COMM_WORLD);

    int *pivots = malloc(sizeof(int) * (size - 1));
    if (rank == 0) {
        qsort(all_samples, size * samples_per_proc, sizeof(int), cmp_int);
        for (int i = 1; i < size; i++) {
            pivots[i - 1] = all_samples[i * samples_per_proc];
        }
    }
    MPI_Bcast(pivots, size - 1, MPI_INT, 0, MPI_COMM_WORLD);

    // 5) Partition em buckets
    int *send_counts  = calloc(size, sizeof(int));
    int *send_offsets = malloc(sizeof(int) * size);
    for (int i = 0; i < local_n; i++) {
        int val = local[i], b = 0;
        while (b < size-1 && val > pivots[b]) b++;
        send_counts[b]++;
    }
    send_offsets[0] = 0;
    for (int i = 1; i < size; i++) {
        send_offsets[i] = send_offsets[i-1] + send_counts[i-1];
    }
    int *send_buffer = malloc(sizeof(int) * local_n);
    int *tmp_counts  = calloc(size, sizeof(int));
    for (int i = 0; i < local_n; i++) {
        int val = local[i], b = 0;
        while (b < size-1 && val > pivots[b]) b++;
        int pos = send_offsets[b] + tmp_counts[b]++;
        send_buffer[pos] = val;
    }

    // 6) All-to-all troca de contagens
    int *recv_counts = malloc(sizeof(int) * size);
    MPI_Alltoall(send_counts, 1, MPI_INT,
                 recv_counts, 1, MPI_INT,
                 MPI_COMM_WORLD);

    // 7) Computa offsets de recebimento
    int *recv_offsets = malloc(sizeof(int) * size);
    recv_offsets[0] = 0;
    for (int i = 1; i < size; i++) {
        recv_offsets[i] = recv_offsets[i-1] + recv_counts[i-1];
    }
    int total_recv = recv_offsets[size-1] + recv_counts[size-1];
    int *recv_buffer = malloc(sizeof(int) * total_recv);

    // 8) All-to-all-v troca de dados dos buckets
    MPI_Alltoallv(send_buffer, send_counts, send_offsets, MPI_INT,
                  recv_buffer, recv_counts, recv_offsets, MPI_INT,
                  MPI_COMM_WORLD);

    // 9) Ordenação final local
    qsort(recv_buffer, total_recv, sizeof(int), cmp_int);

    // 10) Reúne tamanhos (para Gatherv)
    int *gather_counts  = NULL, *gather_offsets = NULL;
    if (rank == 0) gather_counts = malloc(sizeof(int) * size);
    MPI_Gather(&total_recv, 1, MPI_INT,
               gather_counts, 1, MPI_INT,
               0, MPI_COMM_WORLD);

    // 11) Gatherv final (opcional)
    if (rank == 0) {
        gather_offsets = malloc(sizeof(int) * size);
        gather_offsets[0] = 0;
        for (int i = 1; i < size; i++) {
            gather_offsets[i] = gather_offsets[i-1] + gather_counts[i-1];
        }
        free(data);
        data = malloc(sizeof(int) * total_n);
    }
    MPI_Gatherv(recv_buffer, total_recv, MPI_INT,
                data, gather_counts, gather_offsets, MPI_INT,
                0, MPI_COMM_WORLD);

    // 12) Root imprime só os N valores originais, descartando dummies
    if (rank == 0) {
        printf("Sorted array (descartando dummies):\n");
        for (int i = 0; i < N; i++) {
            printf("%d ", data[i]);
        }
        printf("\n");
    }

    // Cleanup (libera tudo)
    free(local);
    free(local_samples);
    free(pivots);
    free(send_counts);
    free(send_offsets);
    free(tmp_counts);
    free(send_buffer);
    free(recv_counts);
    free(recv_offsets);
    free(recv_buffer);
    if (rank == 0) {
        free(data);
        free(all_samples);
        free(gather_counts);
        free(gather_offsets);
    }

    MPI_Finalize();
    return 0;
}
