# -*- coding: utf-8 -*-
"""
Batch Execution Runner
Executes multiple skills concurrently in Docker containers
"""

import os
import sys
import subprocess
import threading
import time
import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Serialize concurrent appends from worker threads to the JSONL state file.
_STATE_FILE_LOCK = threading.Lock()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config_loader import Config


COMPLETED_STATUSES = {
    "completed",
    "timeout_with_artifacts",
    "timeout_no_output_with_artifacts",
}


def safe_path_component(value: str, fallback: str = "unknown") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._")
    return cleaned or fallback


def parse_task(line: str) -> dict:
    normalized = line.strip()
    parts = normalized.split('|')
    if len(parts) < 3:
        return {
            "valid": False,
            "raw": line,
            "task_id": hashlib.sha256(("invalid|" + normalized).encode("utf-8")).hexdigest()[:16],
            "skill_name": "invalid",
            "repo_id": "unknown",
            "risk_level": "unknown",
        }

    skill_name = parts[0]
    skill_path = parts[1]
    repo_id = parts[3] if len(parts) >= 4 else "unknown"
    risk_level = parts[4] if len(parts) >= 5 else "unknown"
    task_key = "run_queue_v2|" + normalized
    return {
        "valid": True,
        "raw": line,
        "task_id": hashlib.sha256(task_key.encode("utf-8")).hexdigest()[:16],
        "skill_name": skill_name,
        "skill_path": skill_path,
        "repo_id": repo_id,
        "risk_level": risk_level,
        "safe_skill_name": safe_path_component(skill_name),
        "safe_repo_id": safe_path_component(repo_id),
        "safe_risk_level": safe_path_component(risk_level),
    }


def has_nova_report(log_dir: Path) -> bool:
    return any((log_dir / "nova-tracer" / "reports").glob("*.html"))


def record_has_nova_report(config: Config, record: dict) -> bool:
    if record.get("log_dir"):
        log_dir = Path(str(record["log_dir"]))
    else:
        log_dir = latest_log_dir(
            config,
            str(record.get("safe_risk_level", record.get("risk_level", "unknown"))),
            str(record.get("safe_repo_id", record.get("repo_id", "unknown"))),
            str(record.get("safe_skill_name", record.get("skill_name", "unknown"))),
        )
    if not log_dir:
        return False
    return has_nova_report(log_dir)


def load_completed_tasks(
    state_file: Path,
    config: Config | None = None,
    retry_timeout_artifacts: bool | None = None,
) -> set:
    completed = set()
    completed_statuses = set(COMPLETED_STATUSES)
    if retry_timeout_artifacts is None:
        retry_timeout_artifacts = os.environ.get("RETRY_TIMEOUT_ARTIFACTS", "false").lower() == "true"
    if retry_timeout_artifacts:
        completed_statuses = {"completed"}
    if not state_file.exists():
        return completed
    with state_file.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            status = record.get("status")
            task_id = record.get("task_id")
            if not task_id:
                continue
            if status in completed_statuses:
                completed.add(task_id)
            elif (
                status == "timeout"
                and config is not None
                and "timeout_with_artifacts" in completed_statuses
                and record_has_nova_report(config, record)
            ):
                completed.add(task_id)
    return completed


def append_state(state_file: Path, task: dict, status: str, message: str, log_dir: Path | None = None) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "task_id": task["task_id"],
        "status": status,
        "skill_name": task["skill_name"],
        "repo_id": task["repo_id"],
        "risk_level": task["risk_level"],
        "safe_skill_name": task.get("safe_skill_name", safe_path_component(task["skill_name"])),
        "safe_repo_id": task.get("safe_repo_id", safe_path_component(task["repo_id"])),
        "safe_risk_level": task.get("safe_risk_level", safe_path_component(task["risk_level"])),
        "skill_path": task.get("skill_path", ""),
        "message": message,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if log_dir is not None:
        record["log_dir"] = str(log_dir)
    payload = json.dumps(record, ensure_ascii=False) + "\n"
    with _STATE_FILE_LOCK:
        with state_file.open("a", encoding="utf-8") as f:
            f.write(payload)


def latest_log_dir(config: Config, risk_level: str, repo_id: str, skill_name: str) -> Path | None:
    base = (
        config.paths.execution_logs_dir
        / safe_path_component(risk_level)
        / safe_path_component(repo_id)
        / safe_path_component(skill_name)
    )
    if not base.exists():
        return None
    dirs = [path for path in base.iterdir() if path.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda path: path.stat().st_mtime)


def claude_has_substantive_output(log_dir: Path) -> bool:
    output_file = log_dir / "claude_output.txt"
    if not output_file.exists():
        return False
    ignored_prefixes = (
        "Warning: Execution timeout",
        "Execution complete",
    )
    for raw in output_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line and not line.startswith(ignored_prefixes):
            return True
    return False


def classify_timeout(log_dir: Path, skill_name: str) -> tuple[bool, str, str]:
    if not log_dir:
        return False, "timeout", f"[{skill_name}] Timed out (code 124, no log directory found)"

    nova_reports = list((log_dir / "nova-tracer" / "reports").glob("*.html"))
    if not nova_reports:
        return False, "timeout", f"[{skill_name}] Timed out (code 124, no NOVA report)"

    if claude_has_substantive_output(log_dir):
        status = "timeout_with_artifacts"
        output_note = "partial Claude output"
    else:
        status = "timeout_no_output_with_artifacts"
        output_note = "no substantive Claude output"

    return (
        True,
        status,
        f"[{skill_name}] Timed out after monitoring artifacts were captured "
        f"({output_note}; nova_report={nova_reports[0]}; log_dir={log_dir})",
    )


def run_task(line: str, config: Config, quiet_log_file: Path | None = None) -> tuple:
    """
    Execute a single skill task.

    Returns: (success, status, message, elapsed_seconds, log_dir)
    When quiet_log_file is provided, suppress per-task prints and redirect
    the subprocess's stdout/stderr to that file. The caller is responsible
    for printing a single status line.
    """
    start = time.monotonic()
    try:
        parts = line.strip().split('|')

        if len(parts) < 3:
            return False, "failed", f"Invalid format: {line}", 0.0, None

        skill_name = parts[0]
        skill_path = parts[1]
        prompt = parts[2]

        if len(parts) >= 6:
            repo_id = parts[3]
            risk_level = parts[4]
            top_level = parts[5]
        else:
            repo_id = "unknown"
            risk_level = "unknown"

        if quiet_log_file is None:
            print(f"\n{'='*60}")
            print(f"Starting: {skill_name} ({repo_id}/{risk_level})")
            print(f"{'='*60}")
            sys.stdout.flush()

        executor_script = os.environ.get("SKILL_EXECUTOR", "hostauth")
        if executor_script == "hostauth":
            executor_script = "run_skill_hostauth.sh"

        if executor_script not in {"run_skill.sh", "run_skill_hostauth.sh"}:
            return False, "failed", f"Unsupported SKILL_EXECUTOR: {executor_script}", time.monotonic() - start, None

        task_id = parse_task(line)["task_id"]
        run_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}_{task_id}"
        safe_skill_name = safe_path_component(skill_name)
        safe_repo_id = safe_path_component(repo_id)
        safe_risk_level = safe_path_component(risk_level)
        log_dir = config.paths.execution_logs_dir / safe_risk_level / safe_repo_id / safe_skill_name / run_id

        # Build command
        cmd = [
            str(Path(__file__).parent / executor_script),
            skill_name,
            skill_path,
            prompt,
            safe_repo_id,
            safe_risk_level,
            "false"  # in_place_log
        ]

        # Set environment
        env = os.environ.copy()
        if executor_script == "run_skill.sh":
            if quiet_log_file is None:
                print("Using legacy API-token executor")
            env.setdefault("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

        env["PROJECT_ROOT"] = str(config.root_dir)
        env["EXECUTION_LOGS_DIR"] = str(config.paths.execution_logs_dir)
        env["EXEC_TIMEOUT"] = os.environ.get(
            "EXEC_TIMEOUT",
            str(config.get('executor.timeout', 900))
        )
        env["DOCKER_IMAGE"] = os.environ.get(
            "DOCKER_IMAGE",
            str(config.get('executor.docker_image', 'claude-skill-sandbox'))
        )
        env["USE_NOVA"] = os.environ.get(
            "USE_NOVA",
            str(config.get('executor.use_nova', True)).lower()
        )
        env["NOVA_BLOCK"] = os.environ.get(
            "NOVA_BLOCK",
            str(config.get('executor.nova_block', False)).lower()
        )
        env["NOVA_PROFILE"] = os.environ.get(
            "NOVA_PROFILE",
            str(config.get('executor.nova_profile', 'record'))
        )
        env["RUN_ID"] = run_id

        # Execute (redirect to log file in quiet mode)
        if quiet_log_file is not None:
            with quiet_log_file.open("w", encoding="utf-8") as f:
                result = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT, text=True)
        else:
            result = subprocess.run(cmd, env=env, stdout=None, stderr=None, text=True)

        elapsed = time.monotonic() - start

        if result.returncode == 0:
            if quiet_log_file is None:
                print(f"\nSuccess: {skill_name}")
                sys.stdout.flush()
            return True, "completed", f"[{skill_name}] Success", elapsed, log_dir
        elif result.returncode == 124:
            success, status, message = classify_timeout(log_dir, skill_name)
            if quiet_log_file is None:
                if success:
                    print(f"\nTimed out with monitoring artifacts: {skill_name}")
                else:
                    print(f"\nTimed out: {skill_name} (exit code: 124)")
                sys.stdout.flush()
            return success, status, message, elapsed, log_dir
        else:
            if quiet_log_file is None:
                print(f"\nFailed: {skill_name} (exit code: {result.returncode})")
                sys.stdout.flush()
            return False, "failed", f"[{skill_name}] Failed (code {result.returncode})", elapsed, log_dir

    except Exception as e:
        if quiet_log_file is None:
            print(f"\nError: {str(e)}")
            sys.stdout.flush()
        return False, "failed", f"Exception: {str(e)}", time.monotonic() - start, None


def main():
    parser = argparse.ArgumentParser(description="Batch Skill Execution Runner")
    parser.add_argument("task_file", help="Task queue file path")
    parser.add_argument("--workers", type=int, default=3, help="Concurrent workers (default: 3)")
    parser.add_argument("--sequential", action="store_true", help="Sequential mode")
    parser.add_argument("--config", default=None, help="Config file path")
    parser.add_argument("--limit", type=int, default=0, help="Maximum pending tasks to execute; 0 means all")
    parser.add_argument("--state-file", default=None, help="JSONL state file for completed/failed task records")
    args = parser.parse_args()
    args.workers = max(1, args.workers)

    # Load configuration
    config = Config(args.config)

    task_file = Path(args.task_file)
    if not task_file.exists():
        print(f"Error: Task file not found: {task_file}")
        sys.exit(1)

    with open(task_file, 'r') as f:
        lines = [l.strip() for l in f if l.strip()]

    tasks = [parse_task(line) for line in lines]
    valid_tasks = [task for task in tasks if task["valid"]]
    invalid_tasks = [task for task in tasks if not task["valid"]]
    if invalid_tasks:
        print(f"Error: found {len(invalid_tasks)} malformed queue entr{'y' if len(invalid_tasks) == 1 else 'ies'}")
        for task in invalid_tasks[:10]:
            print(f"  {task['raw']}")
        if len(invalid_tasks) > 10:
            print(f"  ... {len(invalid_tasks) - 10} more")
        sys.exit(1)

    state_file = Path(args.state_file) if args.state_file else task_file.with_name(task_file.stem + "_state.jsonl")
    completed = load_completed_tasks(state_file, config)
    pending_tasks = [task for task in valid_tasks if task["task_id"] not in completed]
    skipped_count = len(valid_tasks) - len(pending_tasks)

    if args.limit > 0:
        pending_tasks = pending_tasks[:args.limit]

    total = len(pending_tasks)
    workers = args.workers
    sequential = args.sequential

    print(f"\n{'='*60}")
    print(f"Batch Execution Runner")
    print(f"{'='*60}")
    print(f"Queue tasks: {len(valid_tasks)}")
    print(f"Completed skipped: {skipped_count}")
    print(f"Pending selected: {total}" + (f" (limit={args.limit})" if args.limit > 0 else ""))
    print(f"State file: {state_file}")
    print(f"Mode: {'Sequential' if sequential else f'Concurrent (workers={workers})'}")
    print(f"{'='*60}\n")

    if total == 0:
        print("No pending tasks to execute.")
        return

    # Resolve quiet mode: auto (default) goes quiet when total exceeds threshold.
    quiet_setting = os.environ.get("EXEC_QUIET", "auto").lower()
    try:
        quiet_threshold = int(os.environ.get("EXEC_QUIET_THRESHOLD", "10") or "10")
    except ValueError:
        quiet_threshold = 10
    if quiet_setting == "auto":
        quiet_mode = total > quiet_threshold
    else:
        quiet_mode = quiet_setting in {"true", "1", "yes"}

    log_dir = Path(__file__).resolve().parent.parent / "logs" / "exec"
    if quiet_mode:
        log_dir.mkdir(parents=True, exist_ok=True)
        print(f"Quiet mode: per-skill subprocess output captured under {log_dir}/")

    def _log_file_for(task: dict) -> Path:
        safe = task["skill_name"].replace("/", "_").replace(" ", "_")[:80] or "skill"
        return log_dir / f"{int(time.time())}_{task['task_id']}_{safe}.log"

    def _print_status(idx: int, task: dict, success: bool, status: str, elapsed: float, log_file: Path | None) -> None:
        mins, secs = divmod(int(elapsed), 60)
        line = (
            f"[{idx}/{total}] {task['repo_id']}/{task['skill_name']} "
            f"({task['risk_level']}) -> {status} ({mins}m{secs:02d}s)"
        )
        if log_file is not None and not success:
            line += f"  log: {log_file}"
        print(line)
        sys.stdout.flush()

    results = []

    if sequential:
        # Sequential execution
        for i, task in enumerate(pending_tasks, 1):
            log_file = _log_file_for(task) if quiet_mode else None
            if not quiet_mode:
                print(f"\nProgress: [{i}/{total}]")
            success, status, msg, elapsed, run_log_dir = run_task(task["raw"], config, quiet_log_file=log_file)
            if quiet_mode:
                _print_status(i, task, success, status, elapsed, log_file)
            append_state(state_file, task, status, msg, run_log_dir)
            results.append(success)
            time.sleep(1)
    else:
        # Concurrent execution
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for task in pending_tasks:
                log_file = _log_file_for(task) if quiet_mode else None
                fut = executor.submit(run_task, task["raw"], config, log_file)
                futures[fut] = (task, log_file)
                time.sleep(2)  # Stagger submissions

            completed_count = 0
            for future in as_completed(futures):
                task, log_file = futures[future]
                success, status, msg, elapsed, run_log_dir = future.result()
                completed_count += 1
                if quiet_mode:
                    _print_status(completed_count, task, success, status, elapsed, log_file)
                append_state(state_file, task, status, msg, run_log_dir)
                results.append(success)

    # Summary
    success_count = sum(results)
    print("\n" + "="*60)
    print("Execution Complete")
    print("="*60)
    print(f"Total attempted: {total}")
    print(f"Success: {success_count}")
    print(f"Failed: {total - success_count}")
    print("="*60)

    if success_count < total and os.environ.get("ALLOW_EXECUTION_FAILURES", "false").lower() != "true":
        sys.exit(1)


if __name__ == "__main__":
    main()
