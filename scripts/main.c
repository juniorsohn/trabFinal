#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>

int cmp_int(const void *a, const void *b) {
    return (*(int*)a - *(int*)b);
}

int main(int argc, char *argv[]) {
    int rank, size;
    int N = 16;           // total number of elements
    int *data = NULL;     // only used on root
    MPI_Init(&argc, &argv);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    if (rank == 0) {
        // Allocate and initialize data on root
        data = malloc(sizeof(int) * N);
        srand(0);
        for (int i = 0; i < N; i++) {
            data[i] = rand() % 100;
        }
        printf("Unsorted array:\n");
        for (int i = 0; i < N; i++) {
            printf("%d ", data[i]);
        }
        printf("\n\n");
    }

    // 1) Broadcast N so all procs know how many elements
    MPI_Bcast(&N, 1, MPI_INT, 0, MPI_COMM_WORLD);

    // Compute local size (assume exactly divisible for simplicity)
    int local_n = N / size;
    int *local = malloc(sizeof(int) * local_n);

    // 2) Scatter the data into each process
    MPI_Scatter(data, local_n, MPI_INT,
                local,   local_n, MPI_INT,
                0, MPI_COMM_WORLD);

    // 3) Local sort
    qsort(local, local_n, sizeof(int), cmp_int);

    // 4) Choose samples: pick one sample per process segment
    int samples_per_proc = size;
    int *local_samples = malloc(sizeof(int) * samples_per_proc);
    for (int i = 0; i < samples_per_proc; i++) {
        int idx = i * local_n / samples_per_proc;
        local_samples[i] = local[idx];
    }

    // 5) Gather all samples on root
    int *all_samples = NULL;
    if (rank == 0) {
        all_samples = malloc(sizeof(int) * size * samples_per_proc);
    }
    MPI_Gather(local_samples, samples_per_proc, MPI_INT,
               all_samples, samples_per_proc, MPI_INT,
               0, MPI_COMM_WORLD);

    // 6) Root sorts samples and picks pivots
    int *pivots = malloc(sizeof(int) * (size - 1));
    if (rank == 0) {
        qsort(all_samples, size * samples_per_proc, sizeof(int), cmp_int);
        for (int i = 1; i < size; i++) {
            pivots[i - 1] = all_samples[i * samples_per_proc];
        }
    }

    // 7) Broadcast pivots to all processes
    MPI_Bcast(pivots, size - 1, MPI_INT, 0, MPI_COMM_WORLD);

    // 8) Partition local array into buckets
    int *send_counts = calloc(size, sizeof(int));
    int *send_offsets = malloc(sizeof(int) * size);
    // First pass to count
    for (int i = 0; i < local_n; i++) {
        int val = local[i];
        int b = 0;
        while (b < size - 1 && val > pivots[b]) b++;
        send_counts[b]++;
    }
    // Compute offsets
    send_offsets[0] = 0;
    for (int i = 1; i < size; i++) {
        send_offsets[i] = send_offsets[i - 1] + send_counts[i - 1];
    }
    // Fill buckets array
    int *send_buffer = malloc(sizeof(int) * local_n);
    int *tmp_counts = calloc(size, sizeof(int));
    for (int i = 0; i < local_n; i++) {
        int val = local[i];
        int b = 0;
        while (b < size - 1 && val > pivots[b]) b++;
        int pos = send_offsets[b] + tmp_counts[b];
        send_buffer[pos] = val;
        tmp_counts[b]++;
    }

    // 9) All-to-all exchange bucket sizes
    int *recv_counts = malloc(sizeof(int) * size);
    MPI_Alltoall(send_counts, 1, MPI_INT,
                 recv_counts, 1, MPI_INT,
                 MPI_COMM_WORLD);

    // 10) Compute receive offsets and total recv size
    int *recv_offsets = malloc(sizeof(int) * size);
    recv_offsets[0] = 0;
    for (int i = 1; i < size; i++) {
        recv_offsets[i] = recv_offsets[i - 1] + recv_counts[i - 1];
    }
    int total_recv = recv_offsets[size - 1] + recv_counts[size - 1];
    int *recv_buffer = malloc(sizeof(int) * total_recv);

    // 11) All-to-all-v exchange data
    MPI_Alltoallv(send_buffer, send_counts, send_offsets, MPI_INT,
                  recv_buffer, recv_counts, recv_offsets, MPI_INT,
                  MPI_COMM_WORLD);

    // 12) Final local sort of received data
    qsort(recv_buffer, total_recv, sizeof(int), cmp_int);

    // 13) Gather final segments back to root (optional)
    int *gather_counts = NULL, *gather_offsets = NULL;
    if (rank == 0) {
        gather_counts  = malloc(sizeof(int) * size);
    }
    MPI_Gather(&total_recv, 1, MPI_INT,
               gather_counts, 1, MPI_INT,
               0, MPI_COMM_WORLD);
    if (rank == 0) {
        gather_offsets = malloc(sizeof(int) * size);
        gather_offsets[0] = 0;
        for (int i = 1; i < size; i++) {
            gather_offsets[i] = gather_offsets[i - 1] + gather_counts[i - 1];
        }
        // reuse data buffer to collect final
        free(data);
        data = malloc(sizeof(int) * N);
    }
    MPI_Gatherv(recv_buffer, total_recv, MPI_INT,
                data, gather_counts, gather_offsets, MPI_INT,
                0, MPI_COMM_WORLD);

    // 14) Root prints the sorted array
    if (rank == 0) {
        printf("Globally sorted array:\n");
        for (int i = 0; i < N; i++) {
            printf("%d ", data[i]);
        }
        printf("\n");
    }

    // Cleanup
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
        free(all_samples);
        free(gather_counts);
        free(gather_offsets);
        free(data);
    }

    MPI_Finalize();
    return 0;
}
