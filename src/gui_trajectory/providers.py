"""Official CLI subprocess adapters; no credentials or private reasoning are stored."""

import json
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path

from .io import read_json

RESOURCE = Path(__file__).parent / "resources"
SCHEMA = read_json(RESOURCE / "teacher.schema.json")
AUTH_ENV = {
    "OPENAI_API_KEY",
    "CODEX_API_KEY",
    "CODEX_ACCESS_TOKEN",
    "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
}


class ProviderError(RuntimeError):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def subscription_env():
    return {key: value for key, value in os.environ.items() if key not in AUTH_ENV}


def process(command, *, cwd=None, prompt=None, timeout=30):
    try:
        child = subprocess.Popen(
            command,
            cwd=cwd,
            env=subscription_env(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise ProviderError("setup", "Required teacher CLI is not installed") from exc
    try:
        stdout, stderr = child.communicate(prompt, timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
        if isinstance(exc, KeyboardInterrupt):
            raise
        raise ProviderError("timeout", "Teacher CLI exceeded the per-sample timeout") from exc
    return child.returncode, stdout, stderr


def decode_events(stdout):
    events = []
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def classify_failure(text):
    value = text.lower()
    if any(
        t in value
        for t in (
            "usage limit",
            "usage_limit",
            "hit your limit",
            "rate limit",
            "rate_limit",
            "quota",
            "limit reached",
            "resets at",
            "too many requests",
            "exceeded your",
            "out of extra usage",
        )
    ):
        return "limit"
    if any(
        t in value
        for t in (
            "not logged in",
            "authentication",
            "unauthorized",
            "oauth",
            "sign in",
            "please login",
        )
    ):
        return "auth"
    if any(
        t in value
        for t in (
            "model not found",
            "model is not available",
            "unsupported model",
            "model does not exist",
            "do not have access to",
        )
    ):
        return "setup"
    return "execution"


def doctor(provider, binary=None):
    binary = binary or provider
    if not shutil.which(binary):
        return {"provider": provider, "ready": False, "reason": "CLI not installed"}
    try:
        code, stdout, _ = process([binary, "--version"])
        match = re.search(r"\d+\.\d+\.\d+", stdout)
        version = match.group(0) if match else "unknown"
        if code:
            raise ProviderError("setup", "CLI version check failed")
        if provider == "codex":
            code, stdout, stderr = process([binary, "login", "status"])
            ready = code == 0 and "logged in using chatgpt" in (stdout + stderr).lower()
            method = "chatgpt" if ready else "unconfirmed"
            required = ("--image", "--output-schema", "--ignore-user-config", "--ephemeral")
            _, help_text, _ = process([binary, "exec", "--help"])
        else:
            code, stdout, _ = process([binary, "auth", "status", "--json"])
            status = json.loads(stdout)
            method = status.get("authMethod", "unconfirmed")
            ready = code == 0 and status.get("loggedIn") is True and method == "claude.ai"
            required = ("--restricted", "--safe-mode", "--json-schema", "--tools")
            _, help_text, _ = process([binary, "--help"])
        missing = [flag for flag in required if flag not in help_text]
        return {
            "provider": provider,
            "version": version,
            "auth_method": method,
            "ready": ready and not missing,
            "reason": "Missing CLI flags: " + ", ".join(missing)
            if missing
            else ("ready" if ready else "Subscription login not confirmed"),
        }
    except (ProviderError, ValueError, TypeError):
        return {"provider": provider, "ready": False, "reason": "Authentication check failed"}


def screenshot(work):
    images = list(work.glob("screenshot.*"))
    if len(images) != 1:
        raise ValueError("Expected one teacher screenshot")
    return images[0]


def codex_command(binary, model, work, *, reasoning_effort=None):
    command = [
        binary,
        "exec",
        "--ignore-user-config",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--config",
        'forced_login_method="chatgpt"',
        "--config",
        'model_provider="openai"',
        "--config",
        'web_search="disabled"',
        "--config",
        "features.shell_tool=false",
        "--config",
        "project_doc_max_bytes=0",
        "--image",
        str(screenshot(work)),
        "--output-schema",
        str(work / "schema.json"),
        "--output-last-message",
        str(work / "final.json"),
        "--json",
    ]
    if model:
        command.extend(["--model", model])
    if reasoning_effort:
        command.extend(["--config", f'model_reasoning_effort="{reasoning_effort}"'])
    return [*command, "-"]


def claude_command(binary, model, work):
    return [
        binary,
        "--safe-mode",
        "--restricted",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--disable-slash-commands",
        "--no-session-persistence",
        "--tools",
        "Read",
        "--allowedTools",
        "Read",
        "--permission-mode",
        "dontAsk",
        "--output-format",
        "stream-json",
        "--verbose",
        "--json-schema",
        json.dumps(SCHEMA),
        "-p",
    ] + (["--model", model] if model else [])


def has_image(value):
    if isinstance(value, dict):
        return value.get("type") == "image" or any(has_image(v) for v in value.values())
    return isinstance(value, list) and any(has_image(v) for v in value)


def inspect_claude(events, work):
    reads, delivered, audit = set(), False, []
    payload, metadata, observed_models = None, {}, set()
    for event in events:
        if isinstance(event.get("model"), str):
            observed_models.add(event["model"])
        for block in event.get("message", {}).get("content", []):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                name = block.get("name")
                if name == "Read":
                    path = block.get("input", {}).get("file_path", "")
                    if (work / path).resolve() != screenshot(work).resolve():
                        raise ProviderError("tool_policy", "Claude read an unexpected file")
                    reads.add(block.get("id"))
                    audit.append({"tool": "Read", "file": screenshot(work).name})
                elif name != "StructuredOutput":
                    raise ProviderError("tool_policy", "Claude used an unexpected tool")
            if block.get("type") == "tool_result" and block.get("tool_use_id") in reads:
                if not block.get("is_error") and (
                    has_image(block.get("content")) or has_image(event.get("tool_use_result"))
                ):
                    delivered = True
        if event.get("type") == "result":
            if event.get("is_error"):
                kind = classify_failure(str(event.get("result", event.get("errors", ""))))
                raise ProviderError(kind, f"Claude reported a {kind} failure")
            payload = event.get("structured_output")
            metadata = {
                key: event[key] for key in ("usage", "num_turns", "duration_ms") if key in event
            }
            observed_models.update(event.get("modelUsage", {}))
    if not delivered:
        raise ProviderError("image_delivery", "Claude image delivery was not confirmed")
    if payload is None:
        raise ProviderError("output", "Claude returned no structured output")
    metadata["observed_models"] = sorted(observed_models)
    return payload, metadata, audit


def invoke(provider, model, work, prompt, *, timeout=300, binary=None, reasoning_effort=None):
    binary = binary or provider
    if provider == "claude":
        command = claude_command(binary, model, work)
        prompt = f"Read the image file {screenshot(work)} using Read.\n\n" + prompt
    else:
        command = codex_command(binary, model, work, reasoning_effort=reasoning_effort)
    code, stdout, stderr = process(command, cwd=work, prompt=prompt, timeout=timeout)
    events = decode_events(stdout)
    failure = code != 0 or any(e.get("type") in ("error", "turn.failed") for e in events)
    if failure:
        kind = classify_failure(stdout + stderr)
        raise ProviderError(kind, f"{provider} reported a {kind} failure")
    if provider == "claude":
        return inspect_claude(events, work)
    audit, metadata = [{"image": "initial_attachment"}], {"observed_models": []}
    model_match = re.search(r"(?m)^model:\s*([a-zA-Z0-9._:/-]+)", stderr)
    if model_match:
        metadata["observed_models"] = [model_match.group(1)]
    for event in events:
        item = event.get("item", {})
        if item and item.get("type") not in ("agent_message", "reasoning"):
            raise ProviderError("tool_policy", "Codex used an unexpected tool")
        if event.get("type") == "turn.completed":
            metadata["usage"] = event.get("usage", {})
    if not (work / "final.json").is_file():
        raise ProviderError("output", "Codex did not write its final structured output")
    try:
        payload = read_json(work / "final.json")
    except ValueError as exc:
        raise ProviderError("output", "Codex final output was not valid JSON") from exc
    return payload, metadata, audit
