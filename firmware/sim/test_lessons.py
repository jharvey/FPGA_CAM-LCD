#!/usr/bin/env python3
"""Run the six lesson scripts of doc/lessons/examples: each checks its own result and exits with 0.

    python firmware/sim/test_lessons.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.abspath(os.path.join(HERE, "..", "..", "doc", "lessons", "examples"))
fail = 0
for name in sorted(n for n in os.listdir(EX) if n.startswith("lesson") and n.endswith(".py")):
    r = subprocess.run([sys.executable, os.path.join(EX, name)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    last = [x for x in r.stdout.strip().split("\n") if x.strip()][-1] if r.stdout.strip() else ""
    print("%s  %-22s %s" % ("PASS" if r.returncode == 0 else "FAIL", name, last[:110]))
    fail += r.returncode != 0
plan = os.path.join(EX, "lesson5_plan.svg")
if os.path.exists(plan):
    os.remove(plan)                     # made by lesson 5: not kept in the repository
print("ALL CHECKS PASSED" if not fail else "%d CHECK(S) FAILED" % fail)
sys.exit(1 if fail else 0)
