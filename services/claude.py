"""Run versioned prompt files through headless Claude Code (`claude -p`), on the Claude subscription.

A prompt is prompts/<name>.v<N>.md: TOML front matter between +++ lines, then the body with
{{placeholders}}. Its output schema is prompts/<name>.v<N>.schema.json. Results are cached by
hash of (prompt version, model, rendered input), so a dry-run followed by --apply calls Claude once.
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

from services.retry import RetryableError, with_retries

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"
CACHE = ROOT / "cache" / "llm"
WORKDIR = ROOT / "cache" / "claude-cwd"  # empty cwd, so the project's CLAUDE.md and commands aren't loaded
SYSTEM = PROMPTS / "_system.md"


class ClaudeError(Exception):
    pass


@dataclass
class Prompt:
    name: str
    version: int
    meta: dict
    body: str
    schema: dict

    @property
    def id(self):
        return f"{self.name}.v{self.version}"


@dataclass
class Result:
    output: dict
    prompt: str
    model: str
    cost_usd: float = 0.0
    tokens: int = 0
    cached: bool = False
    raw: dict = field(default_factory=dict, repr=False)


def load_prompt(name, version=None, root=PROMPTS):
    """Load prompts/<name>.v<version>.md, or the highest version when version is None."""
    if version is None:
        found = sorted(int(m.group(1)) for p in root.glob(f"{name}.v*.md")
                       if (m := re.fullmatch(rf"{re.escape(name)}\.v(\d+)\.md", p.name)))
        if not found:
            raise ClaudeError(f"No prompt file prompts/{name}.v*.md")
        version = found[-1]
    path = root / f"{name}.v{version}.md"
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^\+\+\+\n(.*?)\n\+\+\+\n(.*)$", text, re.S)
    if not m:
        raise ClaudeError(f"{path.name}: missing +++ front matter")
    schema_path = root / f"{name}.v{version}.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return Prompt(name, version, tomllib.loads(m.group(1)), m.group(2).strip() + "\n", schema)


def render(template, inputs):
    def sub(m):
        key = m.group(1)
        if key not in inputs:
            raise ClaudeError(f"Prompt placeholder {{{{{key}}}}} has no input")
        v = inputs[key]
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=2)
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", sub, template)


def find_binary(configured=""):
    for candidate in (configured, os.environ.get("CLAUDE_BIN", "")):
        if candidate and Path(candidate).exists():
            return candidate
    on_path = shutil.which("claude")
    if on_path:
        return on_path
    bundled = sorted(glob.glob(os.path.expanduser(
        "~/.vscode-server/extensions/anthropic.claude-code-*/resources/native-binary/claude")))
    if bundled:
        return bundled[-1]
    raise ClaudeError("Claude Code CLI not found. Install it (https://claude.com/claude-code) "
                      "or set CLAUDE_BIN in .env to the claude binary.")


def parse_output(stdout):
    """Pull (structured output, cost, tokens) out of `claude -p --output-format json`."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        raise RetryableError(f"claude returned non-JSON: {stdout[:200]!r}")
    if isinstance(data, list):  # some versions print the event list
        data = next((d for d in reversed(data) if d.get("type") == "result"), {})
    if data.get("is_error"):
        message = str(data.get("result") or data.get("subtype"))
        if any(s in message.lower() for s in ("login", "auth", "credit", "oauth")):
            raise ClaudeError(f"Claude Code isn't signed in ({message}). Run `claude` once and /login, "
                              "or set CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`) in .env.")
        raise RetryableError(f"claude error: {message[:300]}")
    output = data.get("structured_output")
    if output is None:
        text = (data.get("result") or "").strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        try:
            output = json.loads(text)
        except json.JSONDecodeError:
            raise RetryableError(f"result isn't JSON: {text[:200]!r}")
    usage = data.get("usage") or {}
    tokens = sum(usage.get(k) or 0 for k in ("input_tokens", "output_tokens",
                                              "cache_creation_input_tokens", "cache_read_input_tokens"))
    return output, float(data.get("total_cost_usd") or 0.0), tokens, data


class Claude:
    def __init__(self, settings, runner=subprocess.run, cache_dir=CACHE, prompts_dir=PROMPTS, use_cache=True,
                 sleep=time.sleep):
        self.settings = settings
        self.runner = runner
        self.cache_dir = Path(cache_dir)
        self.prompts_dir = Path(prompts_dir)
        self.use_cache = use_cache
        self.sleep = sleep
        self.cost_usd = 0.0
        self.tokens = 0
        self.calls = 0
        self._bin = None

    @property
    def binary(self):
        if self._bin is None:
            self._bin = find_binary(self.settings.get("claude.bin", ""))
        return self._bin

    def model_for(self, prompt):
        task = prompt.meta.get("task", prompt.name)
        return self.settings.get(f"claude.models.{task}") or self.settings["claude.models.default"]

    def run(self, name, inputs, version=None):
        prompt = load_prompt(name, version, self.prompts_dir)
        model = self.model_for(prompt)
        message = render(prompt.body, inputs)
        key = hashlib.sha256(json.dumps([prompt.id, model, message], ensure_ascii=False).encode()).hexdigest()
        cached = self.cache_dir / f"{key[:2]}/{key}.json"
        if self.use_cache and cached.exists():
            hit = json.loads(cached.read_text(encoding="utf-8"))
            return Result(hit["output"], prompt.id, model, cached=True)

        validator = jsonschema.Draft202012Validator(prompt.schema)
        system = SYSTEM.read_text(encoding="utf-8") if SYSTEM.exists() else ""
        tools = ",".join(prompt.meta.get("tools", []))
        cmd = [self.binary, "-p", "--output-format", "json", "--model", model,
               "--tools", tools, "--no-session-persistence",
               "--json-schema", json.dumps(prompt.schema),
               "--max-budget-usd", str(self.settings.get("claude.budget_usd_per_call", 1.0))]
        if tools:
            cmd += ["--allowedTools", tools]
        if system:
            cmd += ["--system-prompt", system]
        WORKDIR.mkdir(parents=True, exist_ok=True)
        attempt = {"n": 0}

        def once():
            attempt["n"] += 1
            text = message if attempt["n"] == 1 else (
                message + "\n\nYour previous answer was not valid against the JSON schema. Return only valid JSON.")
            try:
                proc = self.runner(cmd, input=text, capture_output=True, text=True, cwd=WORKDIR,
                                   timeout=self.settings.get("claude.timeout_s", 600))
            except subprocess.TimeoutExpired:
                raise RetryableError("claude timed out")
            if proc.returncode != 0 and not proc.stdout.strip():
                raise RetryableError(f"claude exited {proc.returncode}: {proc.stderr.strip()[-300:]}")
            output, cost, tokens, raw = parse_output(proc.stdout)
            self.cost_usd += cost
            self.tokens += tokens
            self.calls += 1
            errors = sorted(validator.iter_errors(output), key=lambda e: e.path)
            if errors:
                raise RetryableError(f"schema: {errors[0].message} at {list(errors[0].path)}")
            return Result(output, prompt.id, model, cost, tokens, raw=raw)

        try:
            result = with_retries(once, self.settings.get("claude.max_attempts", 2), sleep=self.sleep)
        except RetryableError as e:
            raise ClaudeError(f"{prompt.id} failed: {e}")
        if self.use_cache:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps({"prompt": prompt.id, "model": model, "output": result.output},
                                         ensure_ascii=False, indent=2), encoding="utf-8")
        return result
