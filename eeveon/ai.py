import json
import os
import time
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://ollama.eeveon.com/api/generate"
DEFAULT_MODEL = "qwen3-coder:480b-cloud"
DEFAULT_PROVIDER = "ollama"

try:
    DEFAULT_TIMEOUT_S = int(os.getenv("EEVEON_LLM_TIMEOUT", "60"))
except ValueError:
    DEFAULT_TIMEOUT_S = 60

AI_CONFIG_FILE = Path.home() / ".eeveon" / "config" / "ai.json"

DEFAULT_AI_CONFIG = {
    "provider": DEFAULT_PROVIDER,
    "base_url": DEFAULT_BASE_URL,
    "model": DEFAULT_MODEL,
    "timeout_s": DEFAULT_TIMEOUT_S,
    "auto_execute_safe": False,
    "api_key": None,
}

TOOL_SCHEMA = {
    "deploy": {
        "required": {"branch": str, "environment": str},
        "optional": {"canary_percent": int, "dry_run": bool},
    },
    "rollback": {
        "required": {"service": str},
        "optional": {"target_version": str},
    },
    "scale": {
        "required": {"service": str, "replicas": int},
        "optional": {"region": str, "dry_run": bool},
    },
    "pause_automation": {
        "required": {"service": str, "environment": str},
        "optional": {},
    },
    "resume_automation": {
        "required": {"service": str, "environment": str},
        "optional": {},
    },
    "explain": {
        "required": {"command": str},
        "optional": {},
    },
}


def _decrypt_api_key(value):
    if not value or not isinstance(value, str):
        return None
    if value.startswith("ENC:"):
        try:
            from .cli import SecretsManager
        except Exception:
            return None
        return SecretsManager.decrypt("_system_", value[4:])
    return value


def _encrypt_api_key(value):
    if not value or not isinstance(value, str):
        return value
    if value.startswith("ENC:"):
        return value
    try:
        from .cli import SecretsManager
    except Exception:
        return value
    return "ENC:" + SecretsManager.encrypt("_system_", value)


def get_llm_config(provider=None, base_url=None, model=None, timeout_s=None, api_key=None):
    config = load_ai_config()
    env_provider = os.getenv("EEVEON_LLM_PROVIDER")
    env_base_url = os.getenv("EEVEON_LLM_BASE_URL")
    env_model = os.getenv("EEVEON_LLM_MODEL")
    env_timeout = os.getenv("EEVEON_LLM_TIMEOUT")
    env_api_key = os.getenv("EEVEON_LLM_API_KEY")
    if timeout_s is None:
        resolved_timeout = config.get("timeout_s", DEFAULT_TIMEOUT_S)
        if env_timeout:
            try:
                resolved_timeout = int(env_timeout)
            except ValueError:
                pass
    else:
        resolved_timeout = timeout_s
    resolved_provider = provider or env_provider or config.get("provider") or DEFAULT_PROVIDER
    resolved_api_key = api_key or env_api_key or config.get("api_key")
    resolved_api_key = _decrypt_api_key(resolved_api_key)
    return (
        resolved_provider,
        base_url or env_base_url or config.get("base_url") or DEFAULT_BASE_URL,
        model or env_model or config.get("model") or DEFAULT_MODEL,
        resolved_timeout,
        resolved_api_key,
    )


def load_ai_config():
    config = DEFAULT_AI_CONFIG.copy()
    if AI_CONFIG_FILE.exists():
        try:
            data = json.loads(AI_CONFIG_FILE.read_text())
        except json.JSONDecodeError:
            data = {}
        for key in config.keys():
            if key in data:
                config[key] = data[key]
    return config


def save_ai_config(config):
    AI_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = DEFAULT_AI_CONFIG.copy()
    data.update(config or {})
    if data.get("api_key"):
        data["api_key"] = _encrypt_api_key(data["api_key"])
    AI_CONFIG_FILE.write_text(json.dumps(data, indent=2) + "\n")
    return data


def build_prompt(request):
    tools_list = [
        "deploy: args {branch, environment, canary_percent?, dry_run?} (environment must match pipeline name)",
        "rollback: args {service, target_version?} (service must match pipeline name)",
        "scale: args {service, replicas, region?, dry_run?}",
        "pause_automation: args {service, environment}",
        "resume_automation: args {service, environment}",
        "explain: args {command}",
    ]
    return (
        "You are EEveon. Respond ONLY with valid JSON matching this schema exactly "
        "(no extra keys): "
        "{\"tool\":\"<tool>\",\"args\":{...},\"safety\":{\"requires_confirmation\":true|false,"
        "\"reason\":\"\"}}. Allowed tools: "
        + "; ".join(tools_list)
        + ". Request: "
        + request
    )


def call_llm(prompt, provider, base_url, model, timeout_s, api_key=None):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if provider == "ollama":
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
    elif provider in ["openai", "openai-compatible"]:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
    else:
        raise ValueError(f"unsupported_provider:{provider}")

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base_url, data=data, headers=headers)
    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8")
    end = time.time()
    parsed = json.loads(body)

    if provider == "ollama":
        response_text = parsed.get("response", "")
    else:
        choices = parsed.get("choices") or []
        response_text = ""
        if choices:
            response_text = (choices[0].get("message") or {}).get("content", "")

    return response_text, parsed, end - start


def validate_tool_call(response_text):
    try:
        data = json.loads(response_text)
    except Exception as exc:
        return False, None, f"invalid_json: {exc}"

    if not isinstance(data, dict):
        return False, None, "schema_error: root_not_object"

    expected_keys = {"tool", "args", "safety"}
    if set(data.keys()) != expected_keys:
        return False, None, f"schema_error: keys={sorted(data.keys())}"

    tool = data.get("tool")
    if tool not in TOOL_SCHEMA:
        return False, None, f"tool_not_allowed: {tool!r}"

    args = data.get("args")
    if not isinstance(args, dict):
        return False, None, "schema_error: args_not_object"

    safety = data.get("safety")
    if not isinstance(safety, dict):
        return False, None, "schema_error: safety_not_object"

    safety_keys = {"requires_confirmation", "reason"}
    if set(safety.keys()) != safety_keys:
        return False, None, "schema_error: safety_keys"
    if not isinstance(safety["requires_confirmation"], bool):
        return False, None, "schema_error: requires_confirmation_not_bool"
    if not isinstance(safety["reason"], str):
        return False, None, "schema_error: reason_not_string"

    required = TOOL_SCHEMA[tool]["required"]
    optional = TOOL_SCHEMA[tool]["optional"]
    allowed_args = set(required.keys()) | set(optional.keys())

    for key in required:
        if key not in args:
            return False, None, f"schema_error: missing_required_arg:{key}"

    for key in args:
        if key not in allowed_args:
            return False, None, f"schema_error: unexpected_arg:{key}"

    for key, val in args.items():
        expected_type = required.get(key) or optional.get(key)
        if expected_type is not None and not isinstance(val, expected_type):
            return False, None, f"schema_error: arg_type:{key}"

    if "canary_percent" in args:
        if not (0 <= args["canary_percent"] <= 100):
            return False, None, "schema_error: canary_percent_range"

    if "replicas" in args:
        if args["replicas"] < 1:
            return False, None, "schema_error: replicas_range"

    return True, data, ""


def run_nl_request(request, provider=None, base_url=None, model=None, timeout_s=None, api_key=None):
    provider, base_url, model, timeout_s, api_key = get_llm_config(
        provider=provider,
        base_url=base_url,
        model=model,
        timeout_s=timeout_s,
        api_key=api_key,
    )
    prompt = build_prompt(request)
    try:
        response_text, raw_response, latency = call_llm(
            prompt, provider, base_url, model, timeout_s, api_key=api_key
        )
    except Exception as exc:
        return {
            "ok": False,
            "data": None,
            "error": f"llm_call_failed:{exc}",
            "raw": "",
            "latency_s": 0.0,
            "model": model,
            "base_url": base_url,
            "provider": provider,
        }

    ok, data, error = validate_tool_call(response_text)
    return {
        "ok": ok,
        "data": data,
        "error": error,
        "raw": response_text,
        "raw_response": raw_response,
        "latency_s": latency,
        "model": model,
        "base_url": base_url,
        "provider": provider,
    }
