#!/usr/bin/env python3
"""
QuadCA Benchmark Runner — 60-Factor Experiment
================================================
Runs QuadCA on all 100 configurations from the 60-factor benchmark suite
and records test suite size and execution time.

Prerequisites:
  Compile QuadCA first:
    gcc -O2 -fopenmp -o QuadCA quadca.c -lm

Usage:
  python run_quadca_60factors.py [--configs data/benchmark_60factor_configs.csv]
                                 [--exe ./QuadCA]
                                 [--output quadca_results_60f.csv]
"""

import subprocess
import time
import csv
import ast
import os
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description="Run QuadCA on 60-factor benchmark configs.")
    parser.add_argument("--configs", default="data/benchmark_60factor_configs.csv",
                        help="Path to benchmark configuration CSV")
    parser.add_argument("--exe", default=None,
                        help="Path to QuadCA executable (default: auto-detect)")
    parser.add_argument("--output", default="quadca_results_60f.csv",
                        help="Output CSV file path")
    parser.add_argument("--chunk", type=int, default=100,
                        help="Chunk size K (default: 100)")
    parser.add_argument("--sweeps", type=int, default=4,
                        help="Number of sweeps S (default: 4)")
    args = parser.parse_args()

    # Auto-detect executable
    if args.exe is None:
        for candidate in ["./QuadCA", "./QuadCA.exe", "QuadCA", "QuadCA.exe"]:
            if os.path.exists(candidate):
                args.exe = candidate
                break
        if args.exe is None:
            print("ERROR: QuadCA executable not found.")
            print("Compile first: gcc -O2 -fopenmp -o QuadCA quadca.c -lm")
            sys.exit(1)

    # Load configurations
    configs = []
    with open(args.configs, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if row[0].strip():
                configs.append(ast.literal_eval(row[0].strip()))

    print(f"Loaded {len(configs)} configurations ({len(configs[0])} factors each)")
    print(f"QuadCA executable: {args.exe}")
    print(f"Parameters: K={args.chunk}, S={args.sweeps}")
    print(f"Output: {args.output}\n")

    results = []
    for i, levels in enumerate(configs):
        cmd = [args.exe, "-c", str(args.chunk), "-s", str(args.sweeps), "-l"] + [str(lv) for lv in levels]

        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        t1 = time.perf_counter()
        elapsed = t1 - t0

        stdout = proc.stdout.strip()
        if ',' in stdout:
            parts = stdout.split(',')
            test_count = int(parts[0])
        else:
            output_lines = [l for l in stdout.split('\n') if l.strip()]
            test_count = len(output_lines)

        results.append({
            'config_index': i,
            'QuadCA_Count': test_count,
            'QuadCA_Time_s': round(elapsed, 6)
        })

        if (i + 1) % 10 == 0:
            avg_time = sum(r['QuadCA_Time_s'] for r in results) / len(results)
            avg_count = sum(r['QuadCA_Count'] for r in results) / len(results)
            print(f"  Config {i+1}/{len(configs)} | count={test_count} | "
                  f"time={elapsed:.3f}s | avg_count={avg_count:.1f} | avg_time={avg_time:.3f}s")

    # Save results
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['config_index', 'QuadCA_Count', 'QuadCA_Time_s'])
        writer.writeheader()
        writer.writerows(results)

    counts = [r['QuadCA_Count'] for r in results]
    times = [r['QuadCA_Time_s'] for r in results]
    print(f"\n{'='*50}")
    print(f"QuadCA 60-Factor Benchmark Complete!")
    print(f"{'='*50}")
    print(f"Configurations: {len(results)}")
    print(f"Mean test cases: {sum(counts)/len(counts):.1f}")
    print(f"Mean time: {sum(times)/len(times):.4f}s")
    print(f"Total time: {sum(times):.2f}s")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
