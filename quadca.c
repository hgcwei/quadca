#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <time.h>
#include <string.h>
#include <omp.h>

#define MAX_ROWS 50000

// Global variables
int chunk_k = 100;
int sweeps = 4;
int n_factors = 0;
int use_quadratic_weight = 1;  // NEW: 1 = quadratic, 0 = uniform
int *levels_arr;
int *full_offsets;
int *stride_i_arr;
int *stride_j_arr;

#define IDX2D(i, j) ((i) * n_factors + (j))

__thread unsigned int t_seed;

double rand_double() {
    t_seed = t_seed * 1664525 + 1013904223;
    return (double)t_seed / 4294967296.0;
}

double get_column_gain(int* row, int col_idx, int val, bool* covered_1d, double* weights_1d) {
    double gain = 0.0;
    for (int other = 0; other < n_factors; other++) {
        if (other == col_idx) continue;
        int idx = full_offsets[IDX2D(col_idx, other)] + val * stride_i_arr[IDX2D(col_idx, other)] + row[other] * stride_j_arr[IDX2D(col_idx, other)];
        if (!covered_1d[idx]) {
            gain += weights_1d[idx];
        }
    }
    return gain;
}

double count_weighted_gain(int* row, bool* covered_1d, double* weights_1d) {
    double gain = 0.0;
    for (int i = 0; i < n_factors; i++) {
        int vi = row[i];
        for (int j = i + 1; j < n_factors; j++) {
            int idx = full_offsets[IDX2D(i, j)] + vi * stride_i_arr[IDX2D(i, j)] + row[j] * stride_j_arr[IDX2D(i, j)];
            if (!covered_1d[idx]) {
                gain += weights_1d[idx];
            }
        }
    }
    return gain;
}

void pure_greedy_sweep(int* candidate_row, int* best_r, bool* covered_1d, double* weights_1d, int* col_priority_arr) {
    int curr_r[n_factors];
    for (int i = 0; i < n_factors; i++) {
        curr_r[i] = candidate_row[i];
        best_r[i] = candidate_row[i];
    }
    double best_weighted_gain = count_weighted_gain(best_r, covered_1d, weights_1d);
    for (int sweep = 0; sweep < sweeps; sweep++) {
        for (int c_idx = 0; c_idx < n_factors; c_idx++) {
            int c = col_priority_arr[c_idx];
            double max_score = -1e9;
            int best_v = curr_r[c];
            for (int v = 0; v < levels_arr[c]; v++) {
                double gain = get_column_gain(curr_r, c, v, covered_1d, weights_1d);
                double score = gain + (rand_double() * 1e-4);
                if (score > max_score) {
                    max_score = score;
                    best_v = v;
                }
            }
            curr_r[c] = best_v;
        }
        double actual_weighted_gain = count_weighted_gain(curr_r, covered_1d, weights_1d);
        if (actual_weighted_gain >= best_weighted_gain) {
            best_weighted_gain = actual_weighted_gain;
            for (int i = 0; i < n_factors; i++) best_r[i] = curr_r[i];
        }
    }
}

int commit_row(int* row, bool* covered_1d) {
    int new_cov = 0;
    for (int i = 0; i < n_factors; i++) {
        int vi = row[i];
        for (int j = i + 1; j < n_factors; j++) {
            int idx = full_offsets[IDX2D(i, j)] + vi * stride_i_arr[IDX2D(i, j)] + row[j] * stride_j_arr[IDX2D(i, j)];
            if (!covered_1d[idx]) {
                covered_1d[idx] = true;
                new_cov++;
            }
        }
    }
    return new_cov;
}

int main(int argc, char *argv[]) {
    if (argc < 3) {
        printf("Usage: %s [-c chunk] [-s sweeps] [-w 0|1] -l L0 L1 ... Ln\n", argv[0]);
        printf("  -w 0: uniform weighting (all weights = 1)\n");
        printf("  -w 1: quadratic weighting (weight = (Li*Lj)^2) [default]\n");
        return 1;
    }

    // First pass: count levels
    bool parsing_levels = false;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-c") == 0 || strcmp(argv[i], "-s") == 0 || strcmp(argv[i], "-w") == 0) {
            i++;
            parsing_levels = false;
        } else if (strcmp(argv[i], "-l") == 0) {
            parsing_levels = true;
        } else if (parsing_levels) {
            n_factors++;
        }
    }

    if (n_factors < 2) {
        fprintf(stderr, "Error: need at least 2 factors.\n");
        return 1;
    }

    levels_arr = (int*)malloc(n_factors * sizeof(int));

    // Second pass: extract values
    int factor_idx = 0;
    parsing_levels = false;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-c") == 0) {
            if (i + 1 < argc) chunk_k = atoi(argv[++i]);
            parsing_levels = false;
        } else if (strcmp(argv[i], "-s") == 0) {
            if (i + 1 < argc) sweeps = atoi(argv[++i]);
            parsing_levels = false;
        } else if (strcmp(argv[i], "-w") == 0) {
            if (i + 1 < argc) use_quadratic_weight = atoi(argv[++i]);
            parsing_levels = false;
        } else if (strcmp(argv[i], "-l") == 0) {
            parsing_levels = true;
        } else if (parsing_levels) {
            levels_arr[factor_idx++] = atoi(argv[i]);
        }
    }

    // Allocate global matrices
    full_offsets = (int*)malloc(n_factors * n_factors * sizeof(int));
    stride_i_arr = (int*)malloc(n_factors * n_factors * sizeof(int));
    stride_j_arr = (int*)malloc(n_factors * n_factors * sizeof(int));

    // Column priority (descending by level count)
    int* col_priority_arr = (int*)malloc(n_factors * sizeof(int));
    for (int i = 0; i < n_factors; i++) col_priority_arr[i] = i;
    for (int i = 0; i < n_factors - 1; i++) {
        for (int j = i + 1; j < n_factors; j++) {
            if (levels_arr[col_priority_arr[i]] < levels_arr[col_priority_arr[j]]) {
                int temp = col_priority_arr[i];
                col_priority_arr[i] = col_priority_arr[j];
                col_priority_arr[j] = temp;
            }
        }
    }

    // Pre-compute offsets
    int total_combinations = 0;
    for (int i = 0; i < n_factors; i++) {
        for (int j = i + 1; j < n_factors; j++) {
            full_offsets[IDX2D(i, j)] = full_offsets[IDX2D(j, i)] = total_combinations;
            stride_i_arr[IDX2D(i, j)] = stride_j_arr[IDX2D(j, i)] = levels_arr[j];
            stride_j_arr[IDX2D(i, j)] = stride_i_arr[IDX2D(j, i)] = 1;
            total_combinations += levels_arr[i] * levels_arr[j];
        }
    }

    bool* covered_1d = (bool*)calloc(total_combinations, sizeof(bool));
    double* weights_1d = (double*)malloc(total_combinations * sizeof(double));
    double* pair_base_weight = (double*)malloc(total_combinations * sizeof(double));
    int* all_final_rows = (int*)malloc(MAX_ROWS * n_factors * sizeof(int));

    // Initialize base weights — KEY ABLATION POINT
    for (int i = 0; i < n_factors; i++) {
        for (int j = i + 1; j < n_factors; j++) {
            double w;
            if (use_quadratic_weight) {
                w = (double)(levels_arr[i] * levels_arr[j]);
                w = w * w;  // (Li * Lj)^2
            } else {
                w = 1.0;    // Uniform weighting
            }
            int offset = full_offsets[IDX2D(i, j)];
            for (int a = 0; a < levels_arr[i]; a++) {
                for (int b = 0; b < levels_arr[j]; b++) {
                    pair_base_weight[offset + a * levels_arr[j] + b] = w;
                }
            }
        }
    }

    int rows_count = 0;
    int covered_count = 0;

    double start_t = omp_get_wtime();

    while (covered_count < total_combinations && rows_count < MAX_ROWS) {
        for (int idx = 0; idx < total_combinations; idx++) {
            weights_1d[idx] = covered_1d[idx] ? 0.0 : pair_base_weight[idx];
        }

        int final_best_row[n_factors];
        double final_best_gain = -1.0;

        #pragma omp parallel
        {
            t_seed = time(NULL) ^ omp_get_thread_num() ^ rand();
            double local_best_gain = -1.0;
            int local_best_row[n_factors];

            #pragma omp for nowait
            for (int attempt = 0; attempt < chunk_k; attempt++) {
                int seed_row[n_factors];
                for (int i = 0; i < n_factors; i++) {
                    t_seed = t_seed * 1664525 + 1013904223;
                    seed_row[i] = (t_seed >> 16) % levels_arr[i];
                }
                int opt_row[n_factors];
                pure_greedy_sweep(seed_row, opt_row, covered_1d, weights_1d, col_priority_arr);
                double gain = count_weighted_gain(opt_row, covered_1d, weights_1d);
                if (gain > local_best_gain) {
                    local_best_gain = gain;
                    for (int i = 0; i < n_factors; i++) local_best_row[i] = opt_row[i];
                }
            }

            #pragma omp critical
            {
                if (local_best_gain > final_best_gain) {
                    final_best_gain = local_best_gain;
                    for (int i = 0; i < n_factors; i++) final_best_row[i] = local_best_row[i];
                }
            }
        }

        if (final_best_gain > 0) {
            covered_count += commit_row(final_best_row, covered_1d);
            for (int i = 0; i < n_factors; i++) {
                all_final_rows[rows_count * n_factors + i] = final_best_row[i];
            }
            rows_count++;
        }
    }

    double end_t = omp_get_wtime();

    // Output: just print rows_count and time for scripting
    printf("%d,%.4f\n", rows_count, end_t - start_t);

    // Also write CSV
    FILE *fp = fopen("generated_test_cases.csv", "w");
    if (fp != NULL) {
        for (int i = 0; i < n_factors; i++) {
            fprintf(fp, "P%d", i);
            if (i < n_factors - 1) fprintf(fp, ",");
        }
        fprintf(fp, "\n");
        for (int r = 0; r < rows_count; r++) {
            for (int c = 0; c < n_factors; c++) {
                fprintf(fp, "%d", all_final_rows[r * n_factors + c]);
                if (c < n_factors - 1) fprintf(fp, ",");
            }
            fprintf(fp, "\n");
        }
        fclose(fp);
    }

    free(levels_arr);
    free(full_offsets);
    free(stride_i_arr);
    free(stride_j_arr);
    free(col_priority_arr);
    free(covered_1d);
    free(weights_1d);
    free(pair_base_weight);
    free(all_final_rows);

    return 0;
}
