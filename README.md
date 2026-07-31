# QuadCA: High-Compression Pairwise Test Generation

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**QuadCA** (Quadratic-weighted Covering Array generator) is a high-performance pairwise test generator that combines three key innovations:

1. **O(1) Cache-Aligned Memory Mapping** — Flattens pairwise coverage state into a contiguous 1D array for cache-friendly access
2. **Cardinality-Aware Quadratic Weighting** — Assigns static weights $W_{i,j} = (L_i \cdot L_j)^2$ to prioritize high-cardinality parameter pairs
3. **OpenMP-Accelerated Multi-Start Greedy Sweeps** — Parallel chunk-based candidate evaluation with thread-local micro-randomness

## Key Results

On 100 heterogeneous 30-factor benchmarks, QuadCA produces the **smallest test suites** among 7 tools:

| Tool | Mean Suite Size | Reduction vs QuadCA |
|------|:-:|:-:|
| **QuadCA** | **933.1** | — |
| ACTS | 973.7 | +4.0% |
| PICT | 1088.1 | +14.1% |
| Jenny | 1088.8 | +14.3% |
| AllPairsPy | 1230.3 | +23.9% |
| TestFlows | 1249.4 | +25.0% |
| NWisePy | 1522.2 | +38.1% |

All comparisons are statistically significant ($p < 10^{-16}$, Wilcoxon signed-rank test).

## Repository Structure

```
QuadCA/
├── README.md                          # This file
├── quadca.c                           # QuadCA source code (C + OpenMP)
├── run_quadca_timing.py               # Run QuadCA on 30-factor benchmarks
├── run_quadca_60factors.py            # Run QuadCA on 60-factor benchmarks
├── run_competitors.py                 # Run all 6 competitor tools
├── run_ablation.py                    # Ablation study: weighted vs uniform
├── run_param_sensitivity.py           # Parameter sensitivity grid search
├── data/
│   ├── benchmark_30factor_configs.csv # 100 benchmark configs (30 factors)
│   ├── benchmark_60factor_configs.csv # 100 benchmark configs (60 factors)
│   ├── rq1_30factor_results.csv       # RQ1: 7-tool comparison results
│   ├── rq2_60factor_results.csv       # RQ2: 60-factor scalability results
│   ├── rq3_param_sensitivity.csv      # RQ3: Parameter sensitivity data
│   ├── rq4_ablation_results.csv       # RQ4: Ablation study data
│   └── statistical_tests.csv          # Wilcoxon test results
└── paper/
    ├── quadca_scp.tex                 # LaTeX source
    ├── quadca_scp.pdf                 # Compiled paper
    └── *.png                          # Figures
```

## Quick Start

### 1. Compile QuadCA

```bash
# Linux / macOS
gcc -O2 -fopenmp -o QuadCA quadca.c -lm

# Windows (MinGW)
gcc -O2 -fopenmp -o QuadCA.exe quadca.c -lm
```

**Requirements:** GCC with OpenMP support (`-fopenmp`).

### 2. Run QuadCA

```bash
# Basic usage: specify parameter levels after -l
./QuadCA -l 3 3 3 4 4 5

# With custom parameters
./QuadCA -c 100 -s 4 -l 3 3 3 4 4 5

# Ablation: uniform weighting (no quadratic weights)
./QuadCA -w 0 -l 3 3 3 4 4 5
```

**Command-line options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-l L1 L2 ...` | (required) | Number of levels for each parameter |
| `-c K` | 100 | Chunk size (number of random seeds per row) |
| `-s S` | 4 | Number of column-wise optimization sweeps |
| `-w 0\|1` | 1 | Weighting mode: 1 = quadratic, 0 = uniform |

**Output:** QuadCA prints `count,time` to stdout and writes the full test suite to `generated_test_cases.csv`.

### 3. Run a Quick Example

```bash
# Compile
gcc -O2 -fopenmp -o QuadCA quadca.c -lm

# Generate pairwise test suite for 6 parameters with levels [3,3,3,4,4,5]
./QuadCA -l 3 3 3 4 4 5

# Output: "count,time" e.g. "23,0.0012"
# Full suite saved to generated_test_cases.csv
```

## Reproducing Paper Experiments

### RQ1: 30-Factor Benchmark (7-Tool Comparison)

```bash
# 1. Run QuadCA on all 100 configurations
python run_quadca_timing.py

# 2. Run all 6 competitors
python run_competitors.py

# Pre-computed results are in data/rq1_30factor_results.csv
```

### RQ2: 60-Factor Scalability

```bash
# Run QuadCA on 60-factor configurations
python run_quadca_60factors.py

# Run competitors (only ACTS and PICT survive at this scale)
python run_competitors.py --configs data/benchmark_60factor_configs.csv \
                          --factors 60 --output competitor_results_60f.csv

# Pre-computed results are in data/rq2_60factor_results.csv
```

### RQ3: Parameter Sensitivity

```bash
# Grid search over K ∈ {1,5,10,50,100,200,300,500} × S ∈ {1,2,3,4,5,6}
# WARNING: This runs 4,800 QuadCA invocations and takes several hours
python run_param_sensitivity.py

# Pre-computed results are in data/rq3_param_sensitivity.csv
```

### RQ4: Ablation Study (Weighted vs Uniform)

```bash
# Run QuadCA with and without quadratic weighting on all 100 configs
python run_ablation.py

# Pre-computed results are in data/rq4_ablation_results.csv
```

## Installing Competitor Tools

### Python tools (pip)

```bash
pip install allpairspy nwisepy testflows.combinatorics
```

### ACTS (Java)

1. Download from [NIST ACTS](https://csrc.nist.gov/projects/automated-combinatorial-testing-for-software)
2. Place the JAR file in the project directory, or set `ACTS_JAR` environment variable:
   ```bash
   export ACTS_JAR=/path/to/acts_cmd_3.2.jar
   ```

### PICT (C++)

```bash
# Ubuntu/Debian
sudo apt-get install pict

# Or build from source
git clone https://github.com/microsoft/pict.git
cd pict && cmake . && make
export PICT_BIN=/path/to/pict
```

### Jenny (C)

1. Download from [Jenny homepage](https://burtleburtle.net/bob/math/jenny.html)
2. Compile: `gcc -O2 -o jenny jenny.c`
3. Add to PATH or set `JENNY_BIN` environment variable

## Data Format

### Benchmark Configuration CSV

Each row contains a Python-style list of parameter levels:

```csv
Levels_List_Python,TestCase_Count
"[13, 10, 20, 11, 28, 28, 2, 25, ...]",939
```

### Results CSV

```csv
config_index,QuadCA_Count,QuadCA_Time_s
0,939,2.345678
1,1004,2.891234
...
```

## Algorithm Overview

```
Input:  Parameter levels L = [L₁, L₂, ..., Lₙ]
Output: Pairwise covering array (test suite)

1. Initialize coverage array (1D, O(1) indexing)
2. Compute static weights: W(i,j) = (Lᵢ × Lⱼ)²
3. While uncovered pairs remain:
   a. Generate K random seed rows
   b. For each seed, run S column-wise greedy sweeps
      (OpenMP parallel, thread-local LCG for tie-breaking)
   c. Select the row with maximum weighted coverage gain
   d. Commit row and update coverage state
4. Return test suite
```

## Citation

If you use QuadCA in your research, please cite:

```bibtex
@article{wei2025quadca,
  title   = {QuadCA: High-Compression Pairwise Test Generation via
             Cache-Aligned Memory Mapping and Cardinality-Aware
             Quadratic Weighting},
  author  = {Wei, Chao and He, Jiaxin and Sun, Weifeng and
             Yang, Sitong and Bao, Wanying},
  journal = {Science of Computer Programming},
  year    = {2025},
  note    = {Submitted}
}
```

## Authors

- **Chao Wei** (Corresponding author) — weichao.2022@hbut.edu.cn
- Jiaxin He
- Weifeng Sun
- Sitong Yang
- Wanying Bao

School of Computer Science and Artificial Intelligence, Hubei University of Technology, Wuhan, China

## License

This project is released under the MIT License. See [LICENSE](LICENSE) for details.
