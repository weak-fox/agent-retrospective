#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_CODEX_HOME = Path.home() / ".codex"
DEFAULT_SOURCE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT_VALUE = str(Path.cwd() / ".agent-retrospective-data")
DEFAULT_OUTPUT_ROOT = Path(
    os.environ.get(
        "AGENT_RETROSPECTIVE_ROOT",
        DEFAULT_DATA_ROOT_VALUE,
    )
)
STATE_DIR_NAME = "state"


CATEGORY_RULES: list[tuple[str, list[str]]] = [
    (
        "训练/评测/CLI",
        [
            "训练",
            "sft",
            "rft",
            "eval",
            "评测",
            "seed",
            "gold",
            "lora",
            "agent candidate",
            "task_blueprint",
        ],
    ),
    (
        "部署/远程运维",
        [
            "kubectl",
            "k8s",
            "部署",
            "nodeport",
            "namespace",
            "helm",
            "镜像",
            "root@",
            "ssh",
            "docker",
            "registry",
        ],
    ),
    (
        "前端/视觉",
        [
            "impeccable",
            "react",
            "前端",
            "网站",
            "html",
            "css",
            "个人介绍",
            "browser",
            "playwright",
        ],
    ),
    (
        "文档/演示/生图",
        [
            "ppt",
            "powerpoint",
            "生图",
            "图片",
            "背景",
            "docx",
            "文档",
            "generated_images",
        ],
    ),
    (
        "工具链/本机环境",
        [
            "安装",
            "gh",
            "gpu",
            "扩展",
            "代理",
            "skill",
        ],
    ),
]


SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"bytes\(\[[0-9,\s]+\]\)\.decode\(\)"), "[REDACTED_SECRET_BYTES]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "sk-[REDACTED_SECRET]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b"), "gh[REDACTED_SECRET]"),
    (re.compile(r"\bAKIA[0-9A-Z]{12,}\b"), "[REDACTED_SECRET]"),
    (
        re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{12,}"),
        r"\1 [REDACTED_SECRET]",
    ),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|apikey|token|secret|password|passwd|pwd|cookie|authorization)"
            r"(\s*[:=]\s*)([^\s,;，；]+)"
        ),
        r"\1\2[REDACTED_SECRET]",
    ),
    (
        re.compile(r"(密码|口令|密钥)(\s*[：:=]?\s*)([^\s,，;；]+)"),
        r"\1\2[REDACTED_SECRET]",
    ),
    (
        re.compile(r"\b(?!root@)([A-Za-z][A-Za-z0-9_.-]{2,})@([A-Za-z0-9_.-]{2,})\b"),
        "[REDACTED_SECRET]",
    ),
    (
        re.compile(r"(?<![A-Za-z0-9_.-])(?!root@)[A-Za-z0-9_.-]{2,}@[A-Za-z0-9_.-]{2,}(?=$|[^A-Za-z0-9_.-])"),
        "[REDACTED_SECRET]",
    ),
]


def compact_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def redact(value: Any) -> str:
    text = "" if value is None else str(value)
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def truncate(value: Any, limit: int = 220) -> str:
    text = compact_ws(redact(value))
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def parse_json_line(line: str) -> dict[str, Any] | None:
    try:
        item = json.loads(line)
    except json.JSONDecodeError:
        return None
    return item if isinstance(item, dict) else None


def iso_from_epoch(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(seconds, timezone.utc).astimezone().isoformat(timespec="seconds")


def iso_from_epoch_ms(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        ms = float(value)
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(ms / 1000, timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def get_session_id(path: Path, payload_id: str = "") -> str:
    if payload_id:
        return payload_id
    match = re.search(
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        path.name,
    )
    return match.group(1) if match else path.stem


def extract_payload_text(payload: dict[str, Any]) -> str:
    for key in ("message", "text", "output_text"):
        if isinstance(payload.get(key), str):
            return payload[key]
    parts: list[str] = []
    content = payload.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                for key in ("text", "input_text", "output_text"):
                    if isinstance(item.get(key), str):
                        parts.append(item[key])
            elif isinstance(item, str):
                parts.append(item)
    return "\n".join(parts)


def clean_user_message(text: str) -> str:
    cleaned = re.sub(r"<environment_context>.*?</environment_context>", "", text, flags=re.S)
    return compact_ws(cleaned)


def load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"schema_version": SCHEMA_VERSION, "sessions": {}}
    with state_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return {"schema_version": SCHEMA_VERSION, "sessions": {}}
    data.setdefault("sessions", {})
    return data


def load_jsonl_by_id(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            item = parse_json_line(line)
            if not item:
                continue
            session_id = item.get("session_id")
            if isinstance(session_id, str):
                records[session_id] = item
    return records


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    tmp.replace(path)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")


def append_unique_run(path: Path, record: dict[str, Any]) -> None:
    records: list[dict[str, Any]] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                item = parse_json_line(line)
                report_path = item.get("run_report_path") if item else None
                report_exists = isinstance(report_path, str) and Path(report_path).exists()
                if item and report_exists and report_path != record.get("run_report_path"):
                    records.append(item)
    records.append(record)
    write_jsonl(path, records)


def load_threads(codex_home: Path) -> dict[str, dict[str, Any]]:
    db_path = codex_home / "state_5.sqlite"
    if not db_path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        query = """
            select id, rollout_path, created_at, updated_at, created_at_ms, updated_at_ms,
                   source, model_provider, cwd, title, sandbox_policy, approval_mode,
                   tokens_used, archived, archived_at, git_sha, git_branch, git_origin_url,
                   cli_version, first_user_message, agent_nickname, agent_role, memory_mode,
                   model, reasoning_effort, thread_source, preview
            from threads
        """
        for row in conn.execute(query):
            created = iso_from_epoch_ms(row["created_at_ms"]) or iso_from_epoch(row["created_at"])
            updated = iso_from_epoch_ms(row["updated_at_ms"]) or iso_from_epoch(row["updated_at"])
            rows[row["id"]] = {
                "id": row["id"],
                "rollout_path": row["rollout_path"],
                "created_at": created,
                "updated_at": updated,
                "source": row["source"],
                "model_provider": row["model_provider"],
                "cwd": redact(row["cwd"]),
                "title": truncate(row["title"], 500),
                "sandbox_policy": row["sandbox_policy"],
                "approval_mode": row["approval_mode"],
                "tokens_used": row["tokens_used"] or 0,
                "archived": bool(row["archived"]),
                "archived_at": iso_from_epoch(row["archived_at"]),
                "git_sha": row["git_sha"],
                "git_branch": row["git_branch"],
                "git_origin_url": redact(row["git_origin_url"]),
                "cli_version": row["cli_version"],
                "first_user_message": truncate(row["first_user_message"], 800),
                "agent_nickname": row["agent_nickname"],
                "agent_role": row["agent_role"],
                "memory_mode": row["memory_mode"],
                "model": row["model"],
                "reasoning_effort": row["reasoning_effort"],
                "thread_source": row["thread_source"],
                "preview": truncate(row["preview"], 500),
            }
    finally:
        conn.close()
    return rows


def load_session_index(codex_home: Path) -> dict[str, dict[str, Any]]:
    index_path = codex_home / "session_index.jsonl"
    rows: dict[str, dict[str, Any]] = {}
    if not index_path.exists():
        return rows
    with index_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            item = parse_json_line(line)
            if not item or not isinstance(item.get("id"), str):
                continue
            rows[item["id"]] = {
                "thread_name": truncate(item.get("thread_name"), 300),
                "updated_at": item.get("updated_at", ""),
            }
    return rows


def image_counts(codex_home: Path) -> dict[str, int]:
    root = codex_home / "generated_images"
    counts: dict[str, int] = {}
    if not root.exists():
        return counts
    for child in root.iterdir():
        if child.is_dir():
            counts[child.name] = len(list(child.glob("*.png")))
    return counts


def scan_session_files(codex_home: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    sources = [
        ("active", codex_home / "sessions"),
        ("archived", codex_home / "archived_sessions"),
    ]
    for source, root in sources:
        if not root.exists():
            continue
        for path in root.rglob("*.jsonl"):
            session_id = get_session_id(path)
            stat = path.stat()
            entry = {
                "session_id": session_id,
                "source": source,
                "path": str(path),
                "mtime_ns": stat.st_mtime_ns,
                "size_bytes": stat.st_size,
            }
            previous = result.get(session_id)
            if not previous or entry["mtime_ns"] >= previous["mtime_ns"]:
                result[session_id] = entry
    return result


def parse_arguments(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def classify(summary: dict[str, Any]) -> list[str]:
    text = " ".join(
        [
            str(summary.get("title", "")),
            str(summary.get("cwd", "")),
            " ".join(summary.get("user_intents", [])),
            " ".join(summary.get("command_samples", [])),
        ]
    ).lower()
    scores: Counter[str] = Counter()
    for category, needles in CATEGORY_RULES:
        for needle in needles:
            if needle.lower() in text:
                scores[category] += 1
    if not scores:
        return ["综合/答疑"]
    return [category for category, _ in scores.most_common(3)]


def derive_signals(summary: dict[str, Any]) -> list[str]:
    signals: list[str] = []
    event_counts = summary.get("event_counts", {})
    response_counts = summary.get("response_counts", {})
    function_counts = summary.get("function_call_counts", {})
    tokens = int(summary.get("tokens_used") or 0)
    tool_calls = sum(int(v) for v in function_counts.values())

    if tokens >= 50_000_000:
        signals.append("超长上下文任务，需要阶段性状态文档和明确验收点。")
    if event_counts.get("context_compacted", 0):
        signals.append("发生上下文压缩，适合在中途沉淀 checkpoint。")
    if event_counts.get("turn_aborted", 0) or event_counts.get("thread_rolled_back", 0):
        signals.append("出现中断/回滚信号，后续应更早锁定边界和完成标准。")
    if event_counts.get("patch_apply_end", 0):
        signals.append("包含代码修改，复盘时应记录测试命令和验收结果。")
    if event_counts.get("image_generation_end", 0) or response_counts.get("image_generation_call", 0):
        signals.append("包含视觉生成，后续 prompt 应提前写清风格、版式和验收样例。")
    if event_counts.get("web_search_end", 0):
        signals.append("依赖外部资料，结论应保留来源和日期。")
    if tool_calls >= 100:
        signals.append("工具调用密集，适合先拆分只读审计、实现、验证三段。")
    if summary.get("user_message_count", 0) >= 10:
        signals.append("多轮澄清明显，适合在开局写出目标、约束、非目标和完成定义。")
    return signals


def summarize_session(
    entry: dict[str, Any],
    thread_meta: dict[str, Any],
    index_meta: dict[str, Any],
    generated_image_count: int,
) -> dict[str, Any]:
    path = Path(entry["path"])
    session_meta: dict[str, Any] = {}
    turn_context: dict[str, Any] = {}
    type_counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    response_counts: Counter[str] = Counter()
    function_counts: Counter[str] = Counter()
    user_messages: list[str] = []
    agent_messages: list[str] = []
    command_samples: list[str] = []

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            item = parse_json_line(line)
            if not item:
                continue
            item_type = item.get("type")
            if isinstance(item_type, str):
                type_counts[item_type] += 1

            payload = item.get("payload")
            if not isinstance(payload, dict):
                continue

            if item_type == "session_meta":
                session_meta = {
                    "id": payload.get("id"),
                    "timestamp": payload.get("timestamp"),
                    "cwd": redact(payload.get("cwd")),
                    "originator": payload.get("originator"),
                    "cli_version": payload.get("cli_version"),
                    "source": payload.get("source"),
                    "thread_source": payload.get("thread_source"),
                    "model_provider": payload.get("model_provider"),
                    "git_branch": payload.get("git", {}).get("branch")
                    if isinstance(payload.get("git"), dict)
                    else None,
                    "repository_url": redact(payload.get("git", {}).get("repository_url"))
                    if isinstance(payload.get("git"), dict)
                    else None,
                }
                continue

            if item_type == "turn_context":
                turn_context = {
                    "cwd": redact(payload.get("cwd")),
                    "model": payload.get("model"),
                    "approval_policy": payload.get("approval_policy"),
                    "current_date": payload.get("current_date"),
                    "timezone": payload.get("timezone"),
                }
                continue

            if item_type == "event_msg":
                event_type = payload.get("type")
                if isinstance(event_type, str):
                    event_counts[event_type] += 1
                if event_type == "user_message":
                    text = truncate(clean_user_message(extract_payload_text(payload)), 500)
                    if text:
                        user_messages.append(text)
                elif event_type == "agent_message":
                    text = truncate(extract_payload_text(payload), 260)
                    if text:
                        agent_messages.append(text)
                continue

            if item_type == "response_item":
                response_type = payload.get("type")
                if isinstance(response_type, str):
                    response_counts[response_type] += 1
                if response_type == "function_call":
                    name = payload.get("name")
                    if isinstance(name, str):
                        function_counts[name] += 1
                    args = parse_arguments(payload.get("arguments"))
                    cmd = args.get("cmd")
                    if name == "exec_command" and isinstance(cmd, str) and len(command_samples) < 12:
                        command_samples.append(truncate(cmd, 260))
                elif response_type == "message":
                    role = payload.get("role")
                    raw_text = extract_payload_text(payload)
                    text = truncate(clean_user_message(raw_text) if role == "user" else raw_text, 260)
                    if role == "user" and text:
                        user_messages.append(text)
                    elif role == "assistant" and text:
                        agent_messages.append(text)

    session_id = str(entry["session_id"])
    title = (
        thread_meta.get("title")
        or index_meta.get("thread_name")
        or (user_messages[0] if user_messages else "")
        or path.name
    )
    created_at = (
        thread_meta.get("created_at")
        or parse_iso(str(session_meta.get("timestamp") or "")) and parse_iso(str(session_meta.get("timestamp") or "")).isoformat(timespec="seconds")
        or ""
    )
    updated_at = thread_meta.get("updated_at") or index_meta.get("updated_at") or ""
    cwd = thread_meta.get("cwd") or session_meta.get("cwd") or turn_context.get("cwd") or ""

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "source": entry["source"],
        "source_path": redact(entry["path"]),
        "mtime_ns": entry["mtime_ns"],
        "size_bytes": entry["size_bytes"],
        "title": truncate(title, 500),
        "cwd": redact(cwd),
        "created_at": created_at,
        "updated_at": updated_at,
        "archived": bool(thread_meta.get("archived", entry["source"] == "archived")),
        "tokens_used": int(thread_meta.get("tokens_used") or 0),
        "model": thread_meta.get("model") or turn_context.get("model") or "",
        "reasoning_effort": thread_meta.get("reasoning_effort") or "",
        "approval_mode": thread_meta.get("approval_mode") or turn_context.get("approval_policy") or "",
        "sandbox_policy": thread_meta.get("sandbox_policy") or "",
        "git_branch": thread_meta.get("git_branch") or session_meta.get("git_branch") or "",
        "git_origin_url": thread_meta.get("git_origin_url") or session_meta.get("repository_url") or "",
        "generated_image_count": generated_image_count,
        "line_type_counts": dict(type_counts),
        "event_counts": dict(event_counts),
        "response_counts": dict(response_counts),
        "function_call_counts": dict(function_counts),
        "user_message_count": len(user_messages),
        "agent_message_count": len(agent_messages),
        "user_intents": user_messages[:8],
        "assistant_updates": agent_messages[:5],
        "command_samples": command_samples,
    }
    summary["categories"] = classify(summary)
    summary["signals"] = derive_signals(summary)
    return summary


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        values = [str(value).replace("\n", " ") for value in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def primary_intent(summary: dict[str, Any]) -> str:
    intents = summary.get("user_intents") or []
    if intents:
        return truncate(intents[0], 120)
    return truncate(summary.get("title", ""), 120)


def count_by_category(summaries: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for summary in summaries:
        categories = summary.get("categories") or ["综合/答疑"]
        counts[categories[0]] += 1
    return counts


def token_sum_by_category(summaries: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for summary in summaries:
        categories = summary.get("categories") or ["综合/答疑"]
        counts[categories[0]] += int(summary.get("tokens_used") or 0)
    return counts


def date_only(value: str) -> str:
    parsed = parse_iso(value)
    return parsed.date().isoformat() if parsed else ""


def iso_week_key(value: str) -> str:
    parsed = parse_iso(value)
    if not parsed:
        return ""
    year, week, _ = parsed.isocalendar()
    return f"{year}-W{week:02d}"


def year_key(value: str) -> str:
    parsed = parse_iso(value)
    return str(parsed.year) if parsed else ""


def build_main_review(summaries: list[dict[str, Any]], run: dict[str, Any]) -> str:
    sorted_by_created = sorted(summaries, key=lambda item: item.get("created_at") or "")
    sorted_by_tokens = sorted(summaries, key=lambda item: int(item.get("tokens_used") or 0), reverse=True)
    category_counts = count_by_category(summaries)
    category_tokens = token_sum_by_category(summaries)
    workspace_counts: Counter[str] = Counter(summary.get("cwd", "") for summary in summaries if summary.get("cwd"))
    date_counts: Counter[str] = Counter(date_only(summary.get("created_at", "")) for summary in summaries)
    signal_counts: Counter[str] = Counter()
    for summary in summaries:
        for signal in summary.get("signals", []):
            signal_counts[signal] += 1

    first = sorted_by_created[0].get("created_at", "") if sorted_by_created else ""
    last = sorted_by_created[-1].get("created_at", "") if sorted_by_created else ""
    total_tokens = sum(int(summary.get("tokens_used") or 0) for summary in summaries)
    image_sessions = sum(1 for summary in summaries if summary.get("generated_image_count", 0))
    patch_sessions = sum(1 for summary in summaries if summary.get("event_counts", {}).get("patch_apply_end", 0))

    category_rows = []
    for category, count in category_counts.most_common():
        category_rows.append([category, count, f"{category_tokens[category] / 1_000_000:.1f}M"])

    workspace_rows = [
        [truncate(cwd, 72), count]
        for cwd, count in workspace_counts.most_common(10)
    ]
    top_session_rows = [
        [
            summary.get("created_at", "")[:16],
            f"{int(summary.get('tokens_used') or 0) / 1_000_000:.1f}M",
            truncate(summary.get("title", ""), 90),
            ", ".join(summary.get("categories", [])[:2]),
        ]
        for summary in sorted_by_tokens[:12]
    ]
    recent_rows = [
        [
            summary.get("updated_at", "")[:16],
            truncate(summary.get("title", ""), 80),
            ", ".join(summary.get("categories", [])[:2]),
            primary_intent(summary),
        ]
        for summary in sorted(summaries, key=lambda item: item.get("updated_at") or "", reverse=True)[:12]
    ]

    day_rows = [[day, count] for day, count in sorted(date_counts.items()) if day]
    signal_rows = [[signal, count] for signal, count in signal_counts.most_common(12)]

    return "\n\n".join(
        [
            "# Agent Retrospective 总览",
            f"生成时间：{run['run_at']}\n\n数据范围：{first[:16]} 到 {last[:16]}\n\n本次扫描：{run['total_sessions']} 个 session，新增 {run['new_sessions']} 个，变更 {run['changed_sessions']} 个，活跃跳过 {run.get('volatile_sessions', 0)} 个，未变更 {run['unchanged_sessions']} 个。",
            "## 1. 总体画像",
            "\n".join(
                [
                    f"- 总线程数：{len(summaries)}。",
                    f"- 累计 token 记录值：{total_tokens / 1_000_000:.1f}M。",
                    f"- 有代码修改信号的 session：{patch_sessions}。",
                    f"- 有图片生成记录的 session：{image_sessions}。",
                    "- 主要使用方式不是简单问答，而是把 agent 当作长期协作执行器：读代码、拆任务、生成候选、部署验证、视觉产出和问题排障并行出现。",
                ]
            ),
            "## 2. 主题分布",
            markdown_table(["主题", "Session 数", "Token 记录值"], category_rows),
            "## 3. 工作区分布",
            markdown_table(["工作区", "Session 数"], workspace_rows),
            "## 4. 每日节奏",
            markdown_table(["日期", "Session 数"], day_rows),
            "## 5. 高消耗任务",
            markdown_table(["创建时间", "Token", "标题", "主题"], top_session_rows),
            "## 6. 工作流复盘",
            "\n".join(
                [
                    "- 高消耗任务通常集中在跨仓库、跨工具或跨环境工作，最需要提前固定目标、边界、验收标准和状态记录。",
                    "- 多个 session 是只读审计、候选生成、局部实现、部署验证的分工形态。这种模式有效，但需要统一的任务台账，否则容易在长上下文里重复解释背景。",
                    "- 视觉、文档和演示类任务的效率瓶颈通常不是生成本身，而是风格边界、素材边界和验收样例是否提前说清。",
                    "- 真实环境排障类任务依赖外部状态。后续应要求 agent 输出“已执行命令、关键输出、最终状态、残余风险”，避免只留下过程片段。",
                    "- 当任务超过半天或跨多个仓库时，应先让 agent 生成一个 `目标/非目标/输入/输出/验收/风险` 的短 spec，再进入实现。",
                ]
            ),
            "## 7. 技术能力图谱",
            "\n".join(
                [
                    "- 强项：能把代码阅读、数据准备、实现、验证和环境操作放在同一个目标链里推进。",
                    "- 强项：善于让 agent 生成候选、审计覆盖、制作可视化导览，这适合做复杂系统的快速认知压缩。",
                    "- 待加强：长任务的状态固化。建议每个大任务维护 `CURRENT_STATE.md` 或 issue 风格台账，记录已完成、下一步、验证命令。",
                    "- 待加强：密钥和环境信息的输入方式。建议以后把 secret 放在本机环境变量或临时文件，prompt 里只写变量名。",
                    "- 待加强：视觉任务的验收标准。建议提前给出参考图、禁用风格、页面数/比例/字体/颜色边界。",
                ]
            ),
            "## 8. Agent 使用手册",
            "\n".join(
                [
                    "- 开复杂任务：先说目标、仓库、相关路径、真实环境、允许修改范围、验收命令。",
                    "- 做训练/评测或批量数据任务：先让 agent 只读审计 schema、入口、质量门禁，再让子任务分别生成候选、实现和验证。",
                    "- 做部署/排障：要求每一步记录命令、输出摘要、判断依据和回滚点。",
                    "- 做视觉/文档/演示：先生成 1 页或 1 个组件方向样例，通过后再批量扩展。",
                    "- 做复盘：显式触发 `$agent-retrospective`，让它只处理新增/变更 session，并结合历史结论更新总览。",
                ]
            ),
            "## 9. 高频信号",
            markdown_table(["信号", "出现次数"], signal_rows) if signal_rows else "暂无明显高频信号。",
            "## 10. 最近 Session 证据索引",
            markdown_table(["更新时间", "标题", "主题", "首要意图"], recent_rows),
            "## 11. 30 天改进计划",
            "\n".join(
                [
                    "- 每个大任务开始前写 6 行：目标、非目标、输入、输出、验收、风险。",
                    "- 每次让 agent 动生产/远端环境前，要求先输出将执行命令和回滚策略。",
                    "- 每个长链路 session 都要求生成 `input -> work -> verify -> report` 的状态表。",
                    "- 每周触发一次 `$agent-retrospective`，看主题分布、重复卡点和 action item 是否下降。",
                    "- 所有 secret 不进 prompt：只传变量名、配置路径或让 Codex读取本机已有安全上下文。",
                ]
            ),
        ]
    ) + "\n"


def build_run_report(changed: list[dict[str, Any]], summaries: list[dict[str, Any]], run: dict[str, Any]) -> str:
    changed_rows = [
        [
            summary.get("updated_at", "")[:16],
            summary["session_id"],
            truncate(summary.get("title", ""), 78),
            ", ".join(summary.get("categories", [])[:2]),
        ]
        for summary in changed
    ]
    category_counts = count_by_category(changed)
    category_rows = [[category, count] for category, count in category_counts.most_common()]
    top_signals: Counter[str] = Counter()
    for summary in changed:
        for signal in summary.get("signals", []):
            top_signals[signal] += 1
    signal_rows = [[signal, count] for signal, count in top_signals.most_common(10)]

    if changed:
        change_section = markdown_table(["更新时间", "Session ID", "标题", "主题"], changed_rows)
    else:
        change_section = "本次没有发现新增或变更 session；报告仅重新汇总历史状态。"

    return "\n\n".join(
        [
            f"# Agent 增量复盘报告 {run['run_at'][:16]}",
            f"- 扫描 session：{run['total_sessions']}。\n- 新增：{run['new_sessions']}。\n- 变更：{run['changed_sessions']}。\n- 活跃跳过：{run.get('volatile_sessions', 0)}。\n- 未变更：{run['unchanged_sessions']}。",
            "## 本次变化",
            change_section,
            "## 本次主题分布",
            markdown_table(["主题", "Session 数"], category_rows) if category_rows else "无新增主题。",
            "## 新增/变更信号",
            markdown_table(["信号", "出现次数"], signal_rows) if signal_rows else "无新增信号。",
            "## 与历史结合后的判断",
            "\n".join(
                [
                    f"- 当前知识库共保留 {len(summaries)} 个 session 摘要。",
                    "- 如果本次变更集中在同一工作区，优先更新该项目的状态文档和验收清单。",
                    "- 如果本次无新增，说明增量索引可复用；下一次触发会继续基于 `.agent-retrospective-data/state/state.json` 判断差异。",
                    "- 活跃跳过表示 session 文件还在最近几分钟内变化，脚本保留旧摘要并更新指纹，避免反复重算当前线程。",
                ]
            ),
        ]
    ) + "\n"


def build_period_report(
    summaries: list[dict[str, Any]],
    run: dict[str, Any],
    period_title: str,
    period_key: str,
) -> str:
    category_counts = count_by_category(summaries)
    category_tokens = token_sum_by_category(summaries)
    rows = [
        [category, count, f"{category_tokens[category] / 1_000_000:.1f}M"]
        for category, count in category_counts.most_common()
    ]
    session_rows = [
        [
            summary.get("created_at", "")[:16],
            truncate(summary.get("title", ""), 86),
            ", ".join(summary.get("categories", [])[:2]),
            primary_intent(summary),
        ]
        for summary in sorted(summaries, key=lambda item: item.get("created_at") or "")
    ]
    signal_counts: Counter[str] = Counter()
    for summary in summaries:
        for signal in summary.get("signals", []):
            signal_counts[signal] += 1
    signal_rows = [[signal, count] for signal, count in signal_counts.most_common(10)]

    return "\n\n".join(
        [
            f"# {period_title} Agent 复盘：{period_key}",
            f"生成时间：{run['run_at']}\n\n覆盖 session：{len(summaries)}。",
            "## 主题分布",
            markdown_table(["主题", "Session 数", "Token 记录值"], rows) if rows else "当前周期暂无 session。",
            "## 关键 session",
            markdown_table(["创建时间", "标题", "主题", "首要意图"], session_rows[:40]) if session_rows else "当前周期暂无 session。",
            "## 高频工作流信号",
            markdown_table(["信号", "出现次数"], signal_rows) if signal_rows else "当前周期暂无明显信号。",
            "## 下周期建议",
            "\n".join(
                [
                    "- 继续把长任务拆成只读审计、实现、验证、复盘四段。",
                    "- 对跨仓库任务维护一个稳定的状态文件，减少每次重新解释上下文。",
                    "- 对真实环境操作保留命令摘要、验证输出和回滚点。",
                ]
            ),
        ]
    ) + "\n"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(content)
    tmp.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incrementally review local agent sessions.")
    parser.add_argument("--codex-home", type=Path, default=DEFAULT_CODEX_HOME)
    parser.add_argument(
        "--output-root",
        "--repo-root",
        dest="output_root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory where retrospective state and Markdown reports are written.",
    )
    parser.add_argument("--force", action="store_true", help="Reprocess every discovered session.")
    parser.add_argument("--exclude-session", action="append", default=[], help="Session id to skip.")
    parser.add_argument(
        "--volatile-seconds",
        type=int,
        default=300,
        help="Do not reprocess already-summarized sessions modified in this recent window.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    codex_home: Path = args.codex_home.expanduser().resolve()
    output_root: Path = args.output_root.expanduser().resolve()
    state_dir = output_root / STATE_DIR_NAME
    state_path = state_dir / "state.json"
    summaries_path = state_dir / "session_summaries.jsonl"
    runs_path = state_dir / "review_runs.jsonl"

    now = datetime.now().astimezone()
    now_ns = time.time_ns()
    run_id = now.strftime("%Y-%m-%d-%H%M%S")
    run_at = now.isoformat(timespec="seconds")

    state = load_state(state_path)
    previous_sessions = state.get("sessions", {})
    previous_summaries = load_jsonl_by_id(summaries_path)
    threads = load_threads(codex_home)
    session_index = load_session_index(codex_home)
    images = image_counts(codex_home)
    session_files = scan_session_files(codex_home)

    excluded = set(args.exclude_session or [])
    all_summaries_by_id: dict[str, dict[str, Any]] = {}
    changed_summaries: list[dict[str, Any]] = []
    new_count = 0
    changed_count = 0
    unchanged_count = 0
    volatile_count = 0
    new_state_sessions: dict[str, dict[str, Any]] = {}

    for session_id, entry in sorted(session_files.items()):
        if session_id in excluded:
            continue
        fingerprint = {
            "path": entry["path"],
            "mtime_ns": entry["mtime_ns"],
            "size_bytes": entry["size_bytes"],
            "source": entry["source"],
            "schema_version": SCHEMA_VERSION,
        }
        previous = previous_sessions.get(session_id)
        existing_summary = previous_summaries.get(session_id)
        is_new = previous is None
        is_recent = now_ns - int(entry["mtime_ns"]) < max(args.volatile_seconds, 0) * 1_000_000_000
        is_volatile = (
            not args.force
            and not is_new
            and existing_summary is not None
            and previous != fingerprint
            and is_recent
        )
        is_changed = not is_volatile and (
            args.force or is_new or previous != fingerprint or existing_summary is None
        )

        if is_changed:
            summary = summarize_session(
                entry,
                threads.get(session_id, {}),
                session_index.get(session_id, {}),
                images.get(session_id, 0),
            )
            changed_summaries.append(summary)
            if is_new:
                new_count += 1
            else:
                changed_count += 1
        else:
            summary = existing_summary
            if is_volatile:
                volatile_count += 1
            else:
                unchanged_count += 1

        all_summaries_by_id[session_id] = summary
        new_state_sessions[session_id] = fingerprint

    summaries = sorted(all_summaries_by_id.values(), key=lambda item: item.get("created_at") or item["session_id"])
    run_report_path = output_root / "reports" / "runs" / f"{now.strftime('%Y-%m-%d-%H%M')}.md"
    week_key = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
    year = str(now.year)
    weekly_path = output_root / "reports" / "weekly" / f"{week_key}.md"
    yearly_path = output_root / "reports" / "yearly" / f"{year}.md"
    main_path = output_root / "agent_retrospective.md"

    run = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_at": run_at,
        "codex_home": str(codex_home),
        "output_root": str(output_root),
        "total_sessions": len(summaries),
        "new_sessions": new_count,
        "changed_sessions": changed_count,
        "unchanged_sessions": unchanged_count,
        "volatile_sessions": volatile_count,
        "excluded_sessions": sorted(excluded),
        "changed_session_ids": [summary["session_id"] for summary in changed_summaries],
        "main_review_path": str(main_path),
        "run_report_path": str(run_report_path),
        "weekly_report_path": str(weekly_path),
        "yearly_report_path": str(yearly_path),
    }

    write_jsonl(summaries_path, summaries)
    append_unique_run(runs_path, run)
    write_text(main_path, build_main_review(summaries, run))
    write_text(run_report_path, build_run_report(changed_summaries, summaries, run))

    weekly_summaries = [summary for summary in summaries if iso_week_key(summary.get("created_at", "")) == week_key]
    yearly_summaries = [summary for summary in summaries if year_key(summary.get("created_at", "")) == year]
    write_text(weekly_path, build_period_report(weekly_summaries, run, "周度", week_key))
    write_text(yearly_path, build_period_report(yearly_summaries, run, "年度", year))

    state_out = {
        "schema_version": SCHEMA_VERSION,
        "last_run_at": run_at,
        "codex_home": str(codex_home),
        "output_root": str(output_root),
        "sessions": new_state_sessions,
        "last_run": run,
    }
    write_json(state_path, state_out)

    print(json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
