#!/usr/bin/env python3
"""
ctxfill — read how full a Claude Code session's context window is, from its transcript.

Nothing inside a Claude Code session reports its own context size to the model. The number
is on disk anyway: every assistant turn is appended to the session's transcript
(~/.claude/projects/<folder-slug>/<session-id>.jsonl) with a `usage` block, and

    context = input_tokens + cache_read_input_tokens + cache_creation_input_tokens

of the LAST such record is exactly what the next turn will carry.
This tool finds that record and prints it, for humans, scripts, status lines and hooks.

Only the standard library. Python 3.8+.

Usage
  ctxfill                       newest session of the current folder
  ctxfill <session-id>          that session (searched under ~/.claude/projects)
  ctxfill <transcript.jsonl>    that file
  ctxfill <folder>              newest session of that folder
  ctxfill --all [folder]        every session of the folder, newest first
  ctxfill --json ...            machine-readable
  ctxfill --hook                read a Claude Code hook's JSON from stdin (uses transcript_path)
  ctxfill --hook --stop-at 80   as a Stop hook: when the window is >= 80 % full, print the
                                 hook JSON that makes Claude keep going with a reason
                                 (e.g. "run /goodnight"); otherwise print nothing
  --window N                     context window size in tokens (default: $CTXFILL_WINDOW or 1000000)
  --1m / --200k                  shorthands for --window 1000000 / 200000
  --quiet                        no reminder line about the assumed window
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

HOME = os.path.expanduser("~")
PROJECTS_DIR = os.path.join(HOME, ".claude", "projects")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
DEFAULT_WINDOW = int(os.environ.get("CTXFILL_WINDOW", "1000000"))  # most Claude Code plans today; override below


# ---------- finding the transcript ----------

def slug_for_folder(path):
    """Claude Code names a project dir by replacing every non-alphanumeric char of the absolute path with '-'."""
    path = os.path.abspath(path)
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def transcripts_in(project_dir):
    try:
        names = [n for n in os.listdir(project_dir) if n.endswith(".jsonl")]
    except OSError:
        return []
    paths = [os.path.join(project_dir, n) for n in names]
    paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return paths


def find_by_session_id(sid):
    try:
        dirs = os.listdir(PROJECTS_DIR)
    except OSError:
        return None
    for d in dirs:
        p = os.path.join(PROJECTS_DIR, d, sid + ".jsonl")
        if os.path.isfile(p):
            return p
    return None


def resolve_target(target):
    """Return (list_of_transcript_paths, description)."""
    if target is None:
        target = os.getcwd()
    if os.path.isfile(target) and target.endswith(".jsonl"):
        return [target], target
    if UUID_RE.match(target):
        p = find_by_session_id(target)
        return ([p] if p else []), "session " + target
    if os.path.isdir(target):
        pd = os.path.join(PROJECTS_DIR, slug_for_folder(target))
        return transcripts_in(pd), "folder " + os.path.abspath(target)
    return [], target


# ---------- reading the record ----------

def read_last_usage(path):
    """Walk the transcript; return a dict for the last assistant record that has usage, plus compaction hints."""
    last = None
    prev_ctx = None
    compactions = []
    first_ts = None
    with open(path, "rb") as f:
        for raw in f:
            if b'"usage"' not in raw:
                continue
            try:
                rec = json.loads(raw)
            except ValueError:
                continue
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message") or {}
            usage = msg.get("usage") or {}
            if "input_tokens" not in usage:
                continue
            ctx = (usage.get("input_tokens", 0)
                   + usage.get("cache_read_input_tokens", 0)
                   + usage.get("cache_creation_input_tokens", 0))
            if ctx == 0:
                continue  # empty/error records carry zero usage; they are not turns
            ts = rec.get("timestamp")
            if first_ts is None:
                first_ts = ts
            if prev_ctx is not None and ctx < prev_ctx * 0.5 and prev_ctx > 20000:
                compactions.append({"at": ts, "from": prev_ctx, "to": ctx})
            prev_ctx = ctx
            last = {
                "session_id": rec.get("sessionId") or os.path.basename(path)[:-6],
                "model": msg.get("model"),
                "timestamp": ts,
                "context_tokens": ctx,
                "input_tokens": usage.get("input_tokens", 0),
                "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
                "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            }
    if last is None:
        return None
    last["transcript"] = path
    last["first_timestamp"] = first_ts
    last["compactions"] = compactions
    return last


def with_window(info, window):
    info = dict(info)
    info["window"] = window
    info["percent"] = round(100.0 * info["context_tokens"] / window, 1) if window else None
    return info


# ---------- output ----------

def short_ts(ts):
    if not ts:
        return "?"
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ts


def human_line(info):
    sid = info["session_id"][:8]
    pct = f"{info['percent']:.1f}%" if info.get("percent") is not None else "?"
    line = (f"{sid}  {info['model'] or '?':<20} {info['context_tokens']:>9,} tokens  "
            f"{pct:>6} of {info['window']:,}  last turn {short_ts(info['timestamp'])}")
    if info.get("percent") is not None and info["percent"] > 100:
        line += "  <- exceeds the assumed window; pass --window N or set CTXFILL_WINDOW"
    if info["compactions"]:
        c = info["compactions"][-1]
        line += f"  (compacted {len(info['compactions'])}x, last at {short_ts(c['at'])}: {c['from']:,} -> {c['to']:,})"
    return line


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ctxfill", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("target", nargs="?", help="session id, transcript .jsonl, or project folder (default: current folder)")
    ap.add_argument("--all", action="store_true", help="list every session of the folder, newest first")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW, help=f"context window in tokens (default {DEFAULT_WINDOW:,}; env CTXFILL_WINDOW)")
    ap.add_argument("--1m", dest="one_m", action="store_true", help="window = 1,000,000")
    ap.add_argument("--200k", dest="two_hundred_k", action="store_true", help="window = 200,000")
    ap.add_argument("--quiet", "-q", action="store_true", help="suppress the reminder about the assumed window")
    ap.add_argument("--hook", action="store_true", help="read hook JSON from stdin; use its transcript_path")
    ap.add_argument("--stop-at", type=float, default=None, metavar="PCT",
                    help="with --hook: when percent >= PCT, print Stop-hook JSON that blocks stopping with a reason")
    ap.add_argument("--reason", default="Context window is at {percent}% ({tokens:,} of {window:,} tokens). Wrap up now: save state to disk and run the close ceremony.",
                    help="reason template for --stop-at ({percent}, {tokens}, {window})")
    args = ap.parse_args(argv)
    window = 1_000_000 if args.one_m else (200_000 if args.two_hundred_k else args.window)
    window_explicit = args.one_m or args.two_hundred_k or args.window != DEFAULT_WINDOW or "CTXFILL_WINDOW" in os.environ

    if args.hook:
        try:
            hook = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            hook = {}
        path = hook.get("transcript_path")
        if not path or not os.path.isfile(path):
            # a hook must never break the session: say nothing, exit 0
            return 0
        info = read_last_usage(path)
        if info is None:
            return 0
        info = with_window(info, window)
        if args.stop_at is not None:
            if info["percent"] is not None and info["percent"] >= args.stop_at:
                reason = args.reason.format(percent=info["percent"], tokens=info["context_tokens"], window=info["window"])
                print(json.dumps({"decision": "block", "reason": reason}))
            return 0
        print(json.dumps(info) if args.json else human_line(info))
        return 0

    paths, desc = resolve_target(args.target)
    if not paths:
        print(f"ctxfill: no transcript found for {desc}", file=sys.stderr)
        return 2
    if not args.all:
        paths = paths[:1]
    infos = []
    for p in paths:
        info = read_last_usage(p)
        if info is not None:
            infos.append(with_window(info, window))
    if not infos:
        print(f"ctxfill: no usage records yet in {desc}", file=sys.stderr)
        return 2
    if not window_explicit and not args.quiet and not args.json:
        print(f"(window assumed {window:,} tokens; different plan? --window N, --200k, or export CTXFILL_WINDOW=N)", file=sys.stderr)
    if args.json:
        print(json.dumps(infos if args.all else infos[0], indent=2))
    else:
        if args.all:
            print(f"{len(infos)} session(s) for {desc}:")
        for info in infos:
            print(human_line(info))
        if not args.all and len(paths) == 1 and args.target is None:
            pd = os.path.join(PROJECTS_DIR, slug_for_folder(os.getcwd()))
            n = len(transcripts_in(pd))
            if n > 1:
                print(f"(newest of {n} sessions in this folder; pass a session id or --all to pick another)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
