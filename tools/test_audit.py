#!/usr/bin/env python3
"""
GNT — Independent Test-Status Auditor
=======================================
यह इसलिए बना है क्योंकि पहले GNT/ARTG में ऐसा हो चुका है: agent ने कह दिया
"52/52 tests pass" / "certified" — और असल में वो tests सिर्फ़ सतही थे,
या `it.todo`/`assert True` जैसे खोखले stub थे जिनसे कुछ साबित नहीं होता।

नियम: किसी भी chat message में लिखा "tests pass" पर भरोसा मत करो।
सिर्फ़ इस script के output (TEST-STATUS.json) पर भरोसा करो — यह दो चीज़ों
से बनता है जिनमें agent झूठ नहीं बोल सकता:

  1) Jest का अपना --json machine output (असली pass/fail/pending counts,
     Jest खुद तय करता है, agent की narrative नहीं)
  2) हर test file का static "fake-test smell check" — पकड़ता है:
       - it.todo / test.todo          -> कोई असली test है ही नहीं
       - it.skip / xit                -> skip किया हुआ
       - कोई expect() call ही नहीं     -> कुछ साबित नहीं होता, भले "pass" दिखे
       - सिर्फ़ expect(true).toBe(true) जैसा trivial pattern -> "assert True" वाला
         वही धोखा जो पहले GNT/ARTG में मिल चुका है

  Jest भले कहे PASSED, अगर static check कहे "कोई असली assertion नहीं",
  तो verdict बनेगा: FALSE-CONFIDENCE — यही वह चीज़ है जो पहले नहीं पकड़ी गई थी।

Usage (project root, jo NestJS/jest setup वाला हो):
    npx jest --json --outputFile=jest-raw-output.json
    python3 test_audit.py \
        --blueprint m01_purchase.blueprint.yaml \
        --root GNT/modules/M01-purchase \
        --jest-json jest-raw-output.json
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml चाहिए -> pip install pyyaml --break-system-packages")
    sys.exit(1)

TEST_TYPES = {"jest-test", "supertest-api-test", "integration-test"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def sha256_of_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sha256_of_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_blueprint(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# --------------------------------------------------------------------------
# static "fake test" smell-check on a test file's source
# --------------------------------------------------------------------------

TODO_RE = re.compile(r'\b(it|test)\.todo\s*\(')
SKIP_RE = re.compile(r'\b(it|test|describe)\.skip\s*\(|\bxit\s*\(|\bxdescribe\s*\(')
EXPECT_RE = re.compile(r'\bexpect\s*\(')
TRIVIAL_RE = re.compile(
    r'expect\s*\(\s*(true|1|"[^"]*")\s*\)\s*\.\s*(toBe|toEqual)\s*\(\s*(true|1|"[^"]*")\s*\)'
)


LINE_COMMENT_RE = re.compile(r'//.*')
BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/', re.DOTALL)


def strip_comments(src):
    """// aur /* */ comments hata do taaki koi comment ke andar likha
    'expect(' ya 'it.todo(' galti se real code na gina jaaye (yeh bug
    khud test karte waqt mila tha — comment mein explain kiya to wahi
    match ho gaya)."""
    src = BLOCK_COMMENT_RE.sub(" ", src)
    src = LINE_COMMENT_RE.sub(" ", src)
    return src


def static_smell_check(path):
    if not os.path.exists(path):
        return {"exists": False}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw_src = f.read()
    src = strip_comments(raw_src)

    todo_count = len(TODO_RE.findall(src))
    skip_count = len(SKIP_RE.findall(src))
    expect_count = len(EXPECT_RE.findall(src))
    trivial_count = len(TRIVIAL_RE.findall(src))

    if expect_count == 0 and todo_count == 0:
        smell = "NO-ASSERTIONS"          # test "runs" but proves nothing
    elif todo_count > 0 and expect_count == 0:
        smell = "TODO-ONLY"              # koi real test likha hi nahi
    elif expect_count > 0 and expect_count == trivial_count:
        smell = "TRIVIAL-ONLY"           # sirf "assert True" style — GNT/ARTG wali galti
    elif expect_count > 0:
        smell = "HAS-REAL-ASSERTIONS"
    else:
        smell = "UNKNOWN"

    return {
        "exists": True,
        "todo_count": todo_count,
        "skip_count": skip_count,
        "expect_count": expect_count,
        "trivial_count": trivial_count,
        "smell": smell,
        "source_hash": sha256_of_text(raw_src),
    }


# --------------------------------------------------------------------------
# parse Jest's own --json output
# --------------------------------------------------------------------------

def load_jest_json(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    data = json.loads(raw)
    per_file = {}
    for tr in data.get("testResults", []):
        name = tr.get("name", "")
        statuses = [a.get("status") for a in tr.get("assertionResults", [])]
        if any(s == "failed" for s in statuses):
            file_status = "failed"
        elif statuses and all(s == "pending" for s in statuses):
            file_status = "pending"
        elif statuses and all(s == "passed" for s in statuses):
            file_status = "passed"
        elif not statuses:
            file_status = "no-tests-found"
        else:
            file_status = "mixed"
        per_file[name] = {
            "jest_status": file_status,
            "num_tests": len(statuses),
            "num_passed": statuses.count("passed"),
            "num_failed": statuses.count("failed"),
            "num_pending": statuses.count("pending"),
        }
    summary = {
        "numTotalTests": data.get("numTotalTests"),
        "numPassedTests": data.get("numPassedTests"),
        "numFailedTests": data.get("numFailedTests"),
        "numPendingTests": data.get("numPendingTests"),
        "success": data.get("success"),
    }
    return {
        "raw_hash": sha256_of_text(raw),
        "per_file": per_file,
        "summary": summary,
    }


def match_jest_entry(jest_data, rel_path, root):
    """Jest full file paths absolute hote hain; rel_path se match dhoondo."""
    if not jest_data:
        return None
    target_abs = os.path.abspath(os.path.join(root, rel_path))
    for name, info in jest_data["per_file"].items():
        if os.path.abspath(name) == target_abs or name.endswith(rel_path):
            return info
    return None


# --------------------------------------------------------------------------
# combine into one honest verdict per file
# --------------------------------------------------------------------------

def verdict_for(smell_info, jest_info):
    if not smell_info["exists"]:
        return "NOT-FOUND"
    smell = smell_info["smell"]

    if jest_info is None:
        # jest kabhi chala hi nahi is file par
        if smell in ("TODO-ONLY", "NO-ASSERTIONS"):
            return "TODO-ONLY-NOT-RUN"
        return "NOT-RUN"

    js = jest_info["jest_status"]

    if smell == "TODO-ONLY":
        return "TODO-ONLY"
    if smell == "NO-ASSERTIONS":
        return "FALSE-CONFIDENCE" if js == "passed" else js.upper()
    if smell == "TRIVIAL-ONLY":
        return "FALSE-CONFIDENCE-TRIVIAL" if js == "passed" else js.upper()
    if js == "failed":
        return "REAL-FAIL"
    if js == "passed" and smell == "HAS-REAL-ASSERTIONS":
        return "REAL-PASS"
    if js == "pending":
        return "PENDING"
    return f"UNCLEAR({js}/{smell})"


HONEST_PASS = {"REAL-PASS"}


def cmd_audit(args):
    bp = load_blueprint(args.blueprint)
    jest_data = load_jest_json(args.jest_json)

    if jest_data is None:
        print("चेतावनी: कोई --jest-json नहीं दिया / file नहीं मिली।")
        print("असली Jest run के बिना यह सिर्फ़ static smell-check देगा —")
        print("वह भी काफ़ी है fake-test पकड़ने के लिए, पर pass/fail confirm नहीं कर सकता।")
        print("असली तरीका: npx jest --json --outputFile=jest-raw-output.json\n")

    results = {}
    for entry in bp["files"]:
        if entry["type"] not in TEST_TYPES:
            continue
        rel = entry["path"]
        full = os.path.join(args.root, rel)
        smell = static_smell_check(full)
        jest_info = match_jest_entry(jest_data, rel, args.root)
        v = verdict_for(smell, jest_info)
        results[rel] = {
            "purpose": entry.get("purpose", ""),
            "verdict": v,
            "static": smell,
            "jest": jest_info,
        }

    counts = {}
    for r in results.values():
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1

    honest_pass = sum(1 for r in results.values() if r["verdict"] in HONEST_PASS)
    total = len(results)

    report = {
        "checked_at": now_iso(),
        "blueprint_version": bp.get("blueprint_version"),
        "jest_raw_hash": jest_data["raw_hash"] if jest_data else None,
        "jest_summary": jest_data["summary"] if jest_data else None,
        "total_test_files_declared": total,
        "honest_pass_count": honest_pass,
        "verdict_counts": counts,
        "files": results,
    }

    out_path = os.path.join(args.root, "TEST-STATUS.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("==================== TEST-STATUS (honest) ====================")
    print(f"Blueprint में declared test files: {total}")
    print(f"असल में REAL-PASS (genuine assertions, Jest ने pass confirm किया): {honest_pass}")
    print("")
    print("पूरा breakdown:")
    for k, v in sorted(counts.items()):
        flag = "  <-- यहीं दिक्कत थी GNT/ARTG में" if k in (
            "FALSE-CONFIDENCE", "FALSE-CONFIDENCE-TRIVIAL", "TODO-ONLY",
            "TODO-ONLY-NOT-RUN", "NOT-RUN", "NOT-FOUND",
        ) else ""
        print(f"  {k:28s} {v}{flag}")
    print("")
    if honest_pass < total:
        print(f"⚠️  {total - honest_pass}/{total} test files असली pass साबित नहीं करते — नीचे list:")
        for rel, r in results.items():
            if r["verdict"] not in HONEST_PASS:
                print(f"   - {rel}  [{r['verdict']}]  ({r['purpose']})")
    print(f"\nपूरी report (hash-anchored): {out_path}")
    print("नियम: chat में कोई भी 'tests pass' का दावा तब तक मत मानो जब तक")
    print("यह TEST-STATUS.json उस दावे से मेल न खाए।")

    return 0 if honest_pass == total and total > 0 else 1


def main():
    p = argparse.ArgumentParser(description="Independent test-status auditor (never trust chat claims)")
    p.add_argument("--blueprint", required=True)
    p.add_argument("--root", required=True)
    p.add_argument("--jest-json", required=False, help="npx jest --json --outputFile=<this> ka result")
    p.set_defaults(func=cmd_audit)
    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
