#!/usr/bin/env python3
"""
QuadCA Ablation Study Runner (RQ4)
====================================
Runs QuadCA in two modes on all 30-factor benchmark configurations:
  - Weighted mode  (-w 1): cardinality-aware quadratic weighting (default)
  - Uniform mode   (-w 0): all pair weights = 1

This reproduces the ablation experiment in Section 4.4 of the paper.

Prerequisites:
  Compile QuadCA first:
    gcc -O2 -fopenmp -o QuadCA quadca.c -lm

Usage:
  python run_ablation.py [--configs data/benchmark_30factor_configs.csv]
                         [--exe ./QuadCA]
                         [--output ablation_results.csv]
"""

import subprocess
import time
import csv
import ast
import os
import sys
import argparse


def run_quadca(exe, levels, chunk=100, sweeps=4, weighted=1):
    """Run QuadCA with specified weighting mode. Returns (count, time)."""
    cmd = [exe, "-c", str(chunk), "-s", str(sweeps), "-w", str(weighted), "-l"]
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
    parser = argparse.ArgumentParser(description="Run QuadCA ablation study (weighted vs uniform).")
    parser.add_argument("--configs", default="data/benchmark_30factor_configs.csv")
    parser.add_argument("--exe", default=None)
    parser.add_argument("--output", default="ablation_results.csv")
    args = parser.parse_args()

    if args.exe is None:
        for candidate in ["./QuadCA", "./QuadCA.exe", "QuadCA", "QuadCA.exe"]:
            if os.path.exists(candidate):
                args.exe = candidate
                break
        if args.exe is None:
            print("ERROR: QuadCA executable not found.")
            print("Compile first: gcc -O2 -fopenmp -o QuadCA quadca.c -lm")
            sys.exit(1)

    configs = []
    with open(args.configs, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if row[0].strip():
                configs.append(ast.literal_eval(row[0].strip()))

    print(f"Loaded {len(configs)} configurations ({len(configs[0])} factors each)")
    print(f"Running ablation: weighted (QuadCA-W) vs uniform (QuadCA-U)\n")

    results = []
    for i, levels in enumerate(configs):
        w_count, w_time = run_quadca(args.exe, levels, weighted=1)
        u_count, u_time = run_quadca(args.exe, levels, weighted=0)

        reduction = (u_count - w_count) / u_count * 100 if u_count > 0 else 0

        results.append({
            'config_id': i,
            'weighted_count': w_count,
            'weighted_time': round(w_time, 4),
            'unweighted_count': u_count,
            'unweighted_time': round(u_time, 4),
        })

        if (i + 1) % 10 == 0:
            print(f"  Config {i+1}/{len(configs)} | W={w_count} U={u_count} | "
                  f"reduction={reduction:.1f}%")

    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'config_id', 'weighted_count', 'weighted_time',
            'unweighted_count', 'unweighted_time'
        ])
        writer.writeheader()
        writer.writerows(results)

    w_counts = [r['weighted_count'] for r in results]
    u_counts = [r['unweighted_count'] for r in results]
    mean_reduction = sum((u - w) / u * 100 for w, u in zip(w_counts, u_counts)) / len(results)

    print(f"\n{'='*50}")
    print(f"Ablation Study Complete!")
    print(f"{'='*50}")
    print(f"Mean weighted (QuadCA-W):   {sum(w_counts)/len(w_counts):.1f}")
    print(f"Mean unweighted (QuadCA-U): {sum(u_counts)/len(u_counts):.1f}")
    print(f"Mean reduction:             {mean_reduction:.2f}%")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
