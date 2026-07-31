#!/usr/bin/env python3
"""
Competitor Benchmark Script for QuadCA Paper
=============================================
Runs the 6 competitor pairwise test generators on all benchmark configurations
and records test suite size and execution time for each.

Competitors (as evaluated in the paper):
  1. ACTS      — NIST IPOG-based generator (Java)
  2. PICT      — Microsoft pairwise tool (C++)
  3. Jenny     — Lightweight C-based generator
  4. AllPairsPy — Python pairwise library
  5. NWisePy   — Python n-wise generator
  6. TestFlows  — Python TestFlows library

Prerequisites:
  pip install allpairspy nwisepy testflows.combinatorics

  ACTS:  Download from https://csrc.nist.gov/projects/automated-combinatorial-testing-for-software
         Place acts_cmd_*.jar in this directory (or set ACTS_JAR env var).
  PICT:  Install from https://github.com/microsoft/pict
         Ensure 'pict' is on PATH (or set PICT_BIN env var).
  Jenny: Install from https://burtleburtle.net/bob/math/jenny.html
         Ensure 'jenny' is on PATH (or set JENNY_BIN env var).

Usage:
  python run_competitors.py [--configs CONFIG_CSV] [--factors 30|60] [--output OUTPUT_CSV]

Defaults:
  --configs  data/benchmark_30factor_configs.csv
  --factors  30
  --output   competitor_results_30f.csv

Examples:
  # 30-factor benchmark
  python run_competitors.py

  # 60-factor benchmark (only ACTS and PICT survive at this scale)
  python run_competitors.py --configs data/benchmark_60factor_configs.csv --factors 60 --output competitor_results_60f.csv
"""

import subprocess
import time
import csv
import ast
import os
import sys
import argparse
import tempfile
import shutil


# ---------------------------------------------------------------------------
# Tool wrappers — each returns (test_case_count, elapsed_seconds)
# ---------------------------------------------------------------------------

def run_acts(levels, acts_jar):
    """Run ACTS via command-line JAR."""
    if not acts_jar or not os.path.exists(acts_jar):
        return None, None

    n = len(levels)
    # Create ACTS input file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("[System]\n")
        f.write(f"Name: benchmark\n\n")
        f.write("[Parameter]\n")
        for i, lv in enumerate(levels):
            vals = ",".join(str(v) for v in range(lv))
            f.write(f"P{i} (int): {vals}\n")
        f.write("\n[Constraint]\n")
        input_file = f.name

    output_file = input_file + ".out"
    try:
        t0 = time.perf_counter()
        proc = subprocess.run(
            ["java", "-jar", acts_jar, input_file, output_file, "-Ddoi=2"],
            capture_output=True, text=True, timeout=300
        )
        t1 = time.perf_counter()

        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith('#') and not l.startswith('[')]
            # Skip header lines
            data_lines = [l for l in lines if ',' in l or '\t' in l]
            return len(data_lines), t1 - t0
        return None, t1 - t0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None, None
    finally:
        for f in [input_file, output_file]:
            if os.path.exists(f):
                os.unlink(f)


def run_pict(levels, pict_bin="pict"):
    """Run Microsoft PICT."""
    n = len(levels)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for i, lv in enumerate(levels):
            vals = ",".join(str(v) for v in range(lv))
            f.write(f"P{i}: {vals}\n")
        input_file = f.name

    try:
        t0 = time.perf_counter()
        proc = subprocess.run(
            [pict_bin, input_file],
            capture_output=True, text=True, timeout=300
        )
        t1 = time.perf_counter()

        output_lines = [l for l in proc.stdout.strip().split('\n') if l.strip()]
        # First line is header
        count = max(0, len(output_lines) - 1)
        return count, t1 - t0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None, None
    finally:
        if os.path.exists(input_file):
            os.unlink(input_file)


def run_jenny(levels, jenny_bin="jenny"):
    """Run Jenny pairwise generator."""
    n = len(levels)
    # Jenny syntax: jenny <n1> <n2> ... <nk>
    cmd = [jenny_bin] + [str(lv) for lv in levels]
    try:
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        t1 = time.perf_counter()

        output_lines = [l for l in proc.stdout.strip().split('\n') if l.strip()]
        return len(output_lines), t1 - t0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None, None


def run_allpairspy(levels):
    """Run AllPairsPy (Python library)."""
    try:
        from allpairspy import AllPairs
    except ImportError:
        print("  [SKIP] allpairspy not installed. Run: pip install allpairspy")
        return None, None

    parameters = [list(range(lv)) for lv in levels]
    t0 = time.perf_counter()
    result = list(AllPairs(parameters))
    t1 = time.perf_counter()
    return len(result), t1 - t0


def run_nwisepy(levels):
    """Run NWisePy (Python library)."""
    try:
        from nwisepy import nwise
    except ImportError:
        print("  [SKIP] nwisepy not installed. Run: pip install nwisepy")
        return None, None

    parameters = [list(range(lv)) for lv in levels]
    t0 = time.perf_counter()
    result = list(nwise(parameters, n=2))
    t1 = time.perf_counter()
    return len(result), t1 - t0


def run_testflows(levels):
    """Run TestFlows combinatorics (Python library)."""
    try:
        from testflows.combinatorics import CoveringArray
    except ImportError:
        print("  [SKIP] testflows.combinatorics not installed. Run: pip install testflows.combinatorics")
        return None, None

    parameters = {f"P{i}": list(range(lv)) for i, lv in enumerate(levels)}
    t0 = time.perf_counter()
    ca = CoveringArray(parameters, strength=2)
    count = len(ca)
    t1 = time.perf_counter()
    return count, t1 - t0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run competitor pairwise tools on benchmark configs.")
    parser.add_argument("--configs", default="data/benchmark_30factor_configs.csv",
                        help="Path to benchmark configuration CSV")
    parser.add_argument("--factors", type=int, default=30, choices=[30, 60],
                        help="Number of factors (30 or 60)")
    parser.add_argument("--output", default=None,
                        help="Output CSV file path")
    args = parser.parse_args()

    if args.output is None:
        args.output = f"competitor_results_{args.factors}f.csv"

    # Locate external tools
    acts_jar = os.environ.get("ACTS_JAR", None)
    if acts_jar is None:
        # Try to find in current directory
        for f in os.listdir('.'):
            if f.startswith('acts') and f.endswith('.jar'):
                acts_jar = f
                break

    pict_bin = os.environ.get("PICT_BIN", "pict")
    jenny_bin = os.environ.get("JENNY_BIN", "jenny")

    # Load configurations
    configs = []
    with open(args.configs, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if row[0].strip():
                configs.append(ast.literal_eval(row[0].strip()))

    print(f"Loaded {len(configs)} configurations ({len(configs[0])} factors each)")
    print(f"Output: {args.output}\n")

    # Define which tools to run
    if args.factors == 60:
        # At 60 factors, only ACTS and PICT survive (Jenny/Python tools fail or timeout)
        tools = {
            'ACTS':  lambda lv: run_acts(lv, acts_jar),
            'PICT':  lambda lv: run_pict(lv, pict_bin),
        }
    else:
        tools = {
            'ACTS':       lambda lv: run_acts(lv, acts_jar),
            'PICT':       lambda lv: run_pict(lv, pict_bin),
            'Jenny':      lambda lv: run_jenny(lv, jenny_bin),
            'AllPairsPy': lambda lv: run_allpairspy(lv),
            'NWisePy':    lambda lv: run_nwisepy(lv),
            'TestFlows':  lambda lv: run_testflows(lv),
        }

    tool_names = list(tools.keys())
    fieldnames = ['config_index']
    for t in tool_names:
        fieldnames += [f'{t}_Count', f'{t}_Time']

    results = []
    for i, levels in enumerate(configs):
        row = {'config_index': i}
        status_parts = []
        for name, func in tools.items():
            count, elapsed = func(levels)
            row[f'{name}_Count'] = count if count is not None else ''
            row[f'{name}_Time'] = round(elapsed, 6) if elapsed is not None else ''
            if count is not None:
                status_parts.append(f"{name}={count}")
            else:
                status_parts.append(f"{name}=FAIL")
        results.append(row)

        if (i + 1) % 10 == 0 or i == 0:
            print(f"  Config {i+1}/{len(configs)}: {', '.join(status_parts)}")

    # Save results
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'='*60}")
    print(f"Competitor Benchmark Complete!")
    print(f"{'='*60}")
    print(f"Configurations: {len(results)}")
    print(f"Tools evaluated: {', '.join(tool_names)}")
    print(f"Results saved to: {args.output}")

    # Print summary statistics
    print(f"\nSummary (mean test suite size):")
    for name in tool_names:
        counts = [r[f'{name}_Count'] for r in results if r[f'{name}_Count'] != '']
        if counts:
            mean_c = sum(counts) / len(counts)
            print(f"  {name:12s}: {mean_c:.1f} rows ({len(counts)}/{len(results)} configs succeeded)")
        else:
            print(f"  {name:12s}: no successful runs")


if __name__ == "__main__":
    main()
