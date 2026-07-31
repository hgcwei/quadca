#!/usr/bin/env python3
"""
QuadCA Parameter Sensitivity Study (RQ3)
==========================================
Runs QuadCA with a grid of (chunk_size K, sweep_count S) settings
on all 30-factor benchmark configurations.

Grid: K ∈ {1, 5, 10, 50, 100, 200, 300, 500} × S ∈ {1, 2, 3, 4, 5, 6}
Total: 48 settings × 100 configurations = 4,800 runs

Prerequisites:
  Compile QuadCA first:
    gcc -O2 -fopenmp -o QuadCA quadca.c -lm

Usage:
  python run_param_sensitivity.py [--configs data/benchmark_30factor_configs.csv]
                                   [--exe ./QuadCA]
                                   [--output param_sensitivity.csv]
"""

import subprocess
import time
import csv
import ast
import os
import sys
import argparse
import itertools


CHUNK_VALUES = [1, 5, 10, 50, 100, 200, 300, 500]
SWEEP_VALUES = [1, 2, 3, 4, 5, 6]


def run_quadca(exe, levels, chunk, sweeps):
    """Run QuadCA with given parameters. Returns (count, time)."""
    cmd = [exe, "-c", str(chunk), "-s", str(sweeps), "-l"]
    cmd += [str(lv) for lv in levels]

    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    t1 = time.perf_counter()

    stdout = proc.stdout.strip()
    if ',' in stdout:
        count = int(stdout.split(',')[0])
    else:
        count = len([l for l in stdout.split('\n') if l.strip()])
    return count, t1 - t0


def main():
    parser = argparse.ArgumentParser(description="Run QuadCA parameter sensitivity grid search.")
    parser.add_argument("--configs", default="data/benchmark_30factor_configs.csv")
    parser.add_argument("--exe", default=None)
    parser.add_argument("--output", default="param_sensitivity.csv")
    args = parser.parse_args()

    if args.exe is None:
        for candidate in ["./QuadCA", "./QuadCA.exe", "QuadCA", "QuadCA.exe"]:
            if os.path.exists(candidate):
                args.exe = candidate
                break
        if args.exe is None:
            print("ERROR: QuadCA executable not found.")
            sys.exit(1)

    configs = []
    with open(args.configs, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if row[0].strip():
                configs.append(ast.literal_eval(row[0].strip()))

    grid = list(itertools.product(CHUNK_VALUES, SWEEP_VALUES))
    total_runs = len(grid) * len(configs)
    print(f"Loaded {len(configs)} configurations")
    print(f"Parameter grid: {len(CHUNK_VALUES)} K × {len(SWEEP_VALUES)} S = {len(grid)} settings")
    print(f"Total runs: {total_runs}\n")

    results = []
    run_count = 0
    for k, s in grid:
        counts = []
        times = []
        for levels in configs:
            count, elapsed = run_quadca(args.exe, levels, k, s)
            counts.append(count)
            times.append(elapsed)
            run_count += 1

        results.append({
            'chunk': k,
            'sweep': s,
            'mean_count': round(sum(counts) / len(counts), 2),
            'std_count': round((sum((c - sum(counts)/len(counts))**2 for c in counts) / len(counts))**0.5, 2),
            'mean_time': round(sum(times) / len(times), 4),
            'std_time': round((sum((t - sum(times)/len(times))**2 for t in times) / len(times))**0.5, 4),
        })
        print(f"  K={k:>3d}, S={s} | mean_count={results[-1]['mean_count']:.1f} | "
              f"mean_time={results[-1]['mean_time']:.3f}s | "
              f"progress={run_count}/{total_runs}")

    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'chunk', 'sweep', 'mean_count', 'std_count', 'mean_time', 'std_time'
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'='*50}")
    print(f"Parameter Sensitivity Complete!")
    print(f"{'='*50}")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
