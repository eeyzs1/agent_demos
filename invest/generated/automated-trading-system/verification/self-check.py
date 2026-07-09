#!/usr/bin/env python3
"""
Self-Check Loop: Execute → Check → Reflect → Fix.

Runs verification, uses error-capture for structured analysis,
applies retry strategy from retry-config, and re-runs.
Maximum 3 iterations to prevent infinite loops.

Usage:
    python verification/self-check.py [--project-root <dir>] [--max-iterations 3]
"""

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

# Ensure UTF-8 stdout/stderr on Windows (prevents UnicodeEncodeError with emoji)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def load_retry_config(project_root: Path) -> dict:
    retry_file = project_root / "feedback" / "retry-config.yaml"
    if not retry_file.exists():
        return {}
    with open(retry_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_error_capture(project_root: Path, error_output: str, source: str) -> list:
    error_capture = project_root / "feedback" / "error-capture.py"
    if not error_capture.exists():
        return []
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
        tmp.write(error_output)
        tmp_path = tmp.name
    try:
        proc = subprocess.run(
            [sys.executable, str(error_capture), "--error-output", tmp_path, "--source", source],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if proc.returncode == 0 and proc.stdout.strip():
            data = yaml.safe_load(proc.stdout) or {}
            return data.get("errors", [])
    except Exception:
        pass
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return []


def run_verification(project_root: Path) -> dict:
    result = {"passed": True, "errors": []}

    consistency_script = project_root / "verification" / "consistency-check.py"
    if consistency_script.exists():
        proc = subprocess.run(
            [sys.executable, str(consistency_script), "--project-root", str(project_root)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            result["passed"] = False
            combined = proc.stdout + proc.stderr
            result["errors"].append({"source": "consistency-check", "output": combined})
            captured = run_error_capture(project_root, combined, "consistency-check")
            if captured:
                result["errors"][-1]["parsed_errors"] = captured

    # Check ruff availability before running — if not installed, skip lint
    # with a warning rather than failing on a "command not found" error.
    ruff_check = subprocess.run(
        ["python", "-m", "ruff", "--version"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if ruff_check.returncode != 0:
        print("⚠️  ruff not installed — skipping lint check. Install with: pip install ruff")
    else:
        lint_result = subprocess.run(
            ["python", "-m", "ruff", "check", str(project_root / "src")],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(project_root),
        )
        if lint_result.returncode != 0:
            result["passed"] = False
            result["errors"].append({"source": "lint", "output": lint_result.stdout})
            captured = run_error_capture(project_root, lint_result.stdout, "lint")
            if captured:
                result["errors"][-1]["parsed_errors"] = captured

    return result


def reflect_on_errors(errors: list, retry_config: dict) -> list:
    fixes = []
    for error in errors:
        source = error.get("source", "unknown")
        output = error.get("output", "")
        parsed = error.get("parsed_errors", [])

        if parsed:
            for pe in parsed:
                error_type = pe.get("type", "unknown")
                fix_hint = pe.get("fix_hint", "")
                strategy = _get_retry_strategy(error_type, retry_config)
                fixes.append({"type": strategy, "action": fix_hint, "source": source, "error_type": error_type})
        elif "unused import" in output:
            fixes.append({"type": "auto_fix", "action": "remove_unused_imports", "source": source})
        elif "undefined name" in output:
            fixes.append({"type": "manual_fix", "action": "add_missing_import_or_definition", "source": source})
        else:
            fixes.append({"type": "manual_fix", "action": "investigate_and_fix", "source": source, "detail": output[:200]})

    return fixes


def _get_retry_strategy(error_type: str, retry_config: dict) -> str:
    strategies = retry_config.get("strategies", {})
    for strategy_name, strategy_data in strategies.items():
        if error_type in strategy_data.get("error_types", []):
            return strategy_data.get("strategy", "manual_fix")
    return "manual_fix"


def self_check_loop(project_root: Path, max_iterations: int) -> dict:
    history = []
    retry_config = load_retry_config(project_root)

    for iteration in range(1, max_iterations + 1):
        print(f"\n--- Self-Check Iteration {iteration}/{max_iterations} ---")
        result = run_verification(project_root)
        history.append({"iteration": iteration, "result": result})

        if result["passed"]:
            print(f"✅ All checks passed at iteration {iteration}")
            return {"passed": True, "iterations": iteration, "history": history}

        print(f"❌ Checks failed. Errors: {len(result['errors'])}")
        fixes = reflect_on_errors(result["errors"], retry_config)
        print(f"   Proposed fixes: {len(fixes)}")
        for fix in fixes:
            print(f"   - [{fix['type']}] {fix['action']}")

    print(f"\n⚠️  Self-check loop exhausted ({max_iterations} iterations)")
    return {"passed": False, "iterations": max_iterations, "history": history}


def verify_acceptance_criterion(project_root: Path, task_id: str) -> dict:
    """Verify a single task card's evidence satisfies its acceptance criteria.

    Called by runtime-hooks HOOK_AC_VERIFY after a subagent reports completion.
    Reads planning/dispatch-results/<task_id>.yaml (the output card) and checks:
      1. output.status == 'completed' (or 'needs_human_review' is acceptable
         only when input.requires_human_review was true)
      2. every self_check_evidence entry has passed == true
      3. every input.success_criteria has a matching evidence entry

    Supports two card formats:
      - Grouped (task-card-schema v1): card has `input` and `output` sub-dicts
      - Flat (legacy samples): status/evidence at top level, no success_criteria

    Returns {"passed": bool, "reasons": [str]}.
    """
    result = {"passed": False, "reasons": []}
    card_path = project_root / "planning" / "dispatch-results" / f"{task_id}.yaml"
    if not card_path.exists():
        result["reasons"].append(f"dispatch-results/{task_id}.yaml not found — subagent has not produced an output card yet")
        return result

    with open(card_path, "r", encoding="utf-8") as f:
        card = yaml.safe_load(f) or {}

    # Grouped format (task-card-schema v1) vs flat legacy format
    if "input" in card or "output" in card:
        inp = card.get("input") or {}
        out = card.get("output") or {}
        status = out.get("status")
        evidence = out.get("self_check_evidence") or []
        criteria = inp.get("success_criteria") or []
        requires_review = bool(inp.get("requires_human_review", False))
    else:
        # Flat legacy format: top-level status + evidence, no input section.
        # 主动从 dispatch-plan.yaml 取回对应 task_id 的 input card
        # （dispatcher 写入的扁平 input card 含 success_criteria），做覆盖校验。
        # 这样扁平格式下也能做 success_criteria 覆盖检查，不再静默跳过。
        status = card.get("status")
        evidence = card.get("self_check_evidence") or []
        criteria = []
        requires_review = False
        plan_path = project_root / "planning" / "dispatch-plan.yaml"
        if plan_path.exists():
            try:
                with open(plan_path, "r", encoding="utf-8") as pf:
                    plan = yaml.safe_load(pf) or {}
                for tc in (plan.get("task_cards") or []):
                    if isinstance(tc, dict) and tc.get("task_id") == task_id:
                        criteria = tc.get("success_criteria") or []
                        requires_review = bool(tc.get("requires_human_review", False))
                        break
            except Exception:
                pass  # dispatch-plan 不可读时降级为只校验 status + evidence

    # 1. status check
    acceptable = ["completed"]
    if requires_review:
        acceptable.append("needs_human_review")
    if status not in acceptable:
        result["reasons"].append(
            f"output.status='{status}' not in {acceptable} "
            f"(requires_human_review={requires_review})"
        )
        return result

    # 2. all evidence passed
    failed_evidence = [e for e in evidence if not e.get("passed", False)]
    if failed_evidence:
        result["reasons"].append(
            f"{len(failed_evidence)} evidence entries have passed=false — "
            f"first: {failed_evidence[0].get('criterion', '?')}"
        )
        return result

    # 3. success_criteria coverage (only when input section present)
    if criteria:
        covered_criteria = {e.get("criterion", "") for e in evidence}
        uncovered = [c for c in criteria if c not in covered_criteria]
        if uncovered:
            result["reasons"].append(
                f"{len(uncovered)} success_criteria have no matching evidence: "
                f"{uncovered[:3]}"
            )
            return result

    result["passed"] = True
    cov = f", {len(criteria)} criteria covered" if criteria else " (no success_criteria to cover)"
    result["reasons"].append(
        f"task_id={task_id} status={status}{cov}"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description="Self-Check Loop")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--max-iterations", type=int, default=3, help="Maximum check iterations")
    parser.add_argument("--verify-ac", default=None, metavar="TASK_ID",
                        help="Verify a single task card's evidence (called by HOOK_AC_VERIFY). "
                             "TASK_ID like 'WU001-01' reads planning/dispatch-results/WU001-01.yaml.")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()

    if args.verify_ac:
        result = verify_acceptance_criterion(project_root, args.verify_ac)
        print(f"\n=== AC Verification: {args.verify_ac} ===")
        for r in result["reasons"]:
            print(f"  - {r}")
        if result["passed"]:
            print("  Result: PASS")
            sys.exit(0)
        print("  Result: FAIL")
        sys.exit(1)

    result = self_check_loop(project_root, args.max_iterations)

    if not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
