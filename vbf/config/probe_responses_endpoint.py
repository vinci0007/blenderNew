from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx


def join_url(base_url: str, endpoint_path: str) -> str:
    parsed = urlsplit(str(base_url or "").strip())
    path = str(endpoint_path or "/responses").strip() or "/responses"
    if not path.startswith("/"):
        path = f"/{path}"
    base_segments = [segment for segment in parsed.path.split("/") if segment]
    endpoint_segments = [segment for segment in path.split("/") if segment]
    if base_segments and endpoint_segments and base_segments[-1].lower() == endpoint_segments[0].lower():
        endpoint_segments = endpoint_segments[1:]
    merged_path = "/" + "/".join(base_segments + endpoint_segments)
    return urlunsplit((parsed.scheme, parsed.netloc, merged_path, "", ""))


def summarize_payload(payload: Any) -> str:
    if isinstance(payload, dict):
        if isinstance(payload.get("error"), dict):
            error = payload["error"]
            return json.dumps(
                {
                    "error": {
                        "message": error.get("message"),
                        "type": error.get("type"),
                        "code": error.get("code"),
                    }
                },
                ensure_ascii=False,
            )
        keys = [
            "type",
            "title",
            "status",
            "detail",
            "error_code",
            "error_name",
            "retryable",
            "retry_after",
            "ray_id",
        ]
        compact = {key: payload.get(key) for key in keys if key in payload}
        if compact:
            return json.dumps(compact, ensure_ascii=False)
        return json.dumps({key: payload.get(key) for key in list(payload.keys())[:8]}, ensure_ascii=False)
    text = str(payload)
    return text[:1200]


def post_case(
    *,
    label: str,
    url: str,
    api_key: str,
    user_agent: Optional[str],
    body: Dict[str, Any],
    timeout: float,
) -> None:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if user_agent:
        headers["User-Agent"] = user_agent

    redacted = dict(body)
    print(f"\n=== {label} ===")
    print(f"url={url}")
    print(f"body={json.dumps(redacted, ensure_ascii=False)}")
    started = time.time()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json=body)
    except Exception as exc:
        print(f"transport_error={type(exc).__name__}: {exc}")
        return

    elapsed = time.time() - started
    print(f"status={response.status_code} elapsed={elapsed:.2f}s")
    try:
        payload: Any = response.json()
    except Exception:
        payload = response.text
    print(f"response={summarize_payload(payload)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Temporary Responses endpoint probe for s2a/compatible gateways.")
    parser.add_argument("--base-url", default=os.getenv("VBF_LLM_BASE_URL", "https://s2a.ii.sb"))
    parser.add_argument("--responses-path", default=os.getenv("VBF_LLM_RESPONSES_PATH", "/v1/responses"))
    parser.add_argument("--model", default=os.getenv("VBF_LLM_MODEL", "gpt-5.4"))
    parser.add_argument("--api-key", default=os.getenv("VBF_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument(
        "--user-agent",
        default=os.getenv("VBF_TEST_USER_AGENT", "codex_cli_rs/0.80.0 (Windows 15.7.2; x86_64) Terminal"),
    )
    parser.add_argument("--skip-stream", action="store_true")
    args = parser.parse_args()

    if not args.api_key:
        print("Missing API key. Pass --api-key or set VBF_LLM_API_KEY/OPENAI_API_KEY.", file=sys.stderr)
        return 2

    url = join_url(args.base_url, args.responses_path)
    vbf_probe_messages = [
        {"role": "system", "content": "Return JSON only."},
        {"role": "user", "content": '{"ok": true}'},
    ]
    user_only_messages = [
        {"role": "user", "content": 'Return JSON only. {"ok": true}'},
    ]
    common = {
        "model": args.model,
        "input": user_only_messages,
    }

    cases = [
        (
            "vbf_exact_probe_system_role",
            {
                "model": args.model,
                "input": vbf_probe_messages,
                "temperature": 0.2,
                "tools": [
                    {
                        "type": "function",
                        "name": "load_skill",
                        "description": "Load one skill schema.",
                        "parameters": {
                            "type": "object",
                            "properties": {"skill_name": {"type": "string"}},
                            "required": ["skill_name"],
                        },
                    }
                ],
                "tool_choice": "auto",
                "text": {"format": {"type": "json_object"}},
            },
        ),
        (
            "vbf_probe_user_only_control",
            {
                "model": args.model,
                "input": user_only_messages,
                "temperature": 0.2,
                "tools": [
                    {
                        "type": "function",
                        "name": "load_skill",
                        "description": "Load one skill schema.",
                        "parameters": {
                            "type": "object",
                            "properties": {"skill_name": {"type": "string"}},
                            "required": ["skill_name"],
                        },
                    }
                ],
                "tool_choice": "auto",
                "text": {"format": {"type": "json_object"}},
            },
        ),
        (
            "instructions_field_control",
            {
                "model": args.model,
                "instructions": "Return JSON only.",
                "input": [{"role": "user", "content": '{"ok": true}'}],
                "temperature": 0.2,
                "tools": [
                    {
                        "type": "function",
                        "name": "load_skill",
                        "description": "Load one skill schema.",
                        "parameters": {
                            "type": "object",
                            "properties": {"skill_name": {"type": "string"}},
                            "required": ["skill_name"],
                        },
                    }
                ],
                "tool_choice": "auto",
                "text": {"format": {"type": "json_object"}},
            },
        ),
        (
            "cc_switch_like_minimal_store_false",
            {
                **common,
                "store": False,
            },
        ),
        (
            "openai_responses_json_object",
            {
                **common,
                "text": {"format": {"type": "json_object"}},
                "store": False,
            },
        ),
        (
            "vbf_probe_tools_json_object",
            {
                **common,
                "tools": [
                    {
                        "type": "function",
                        "name": "load_skill",
                        "description": "Load one skill schema.",
                        "parameters": {
                            "type": "object",
                            "properties": {"skill_name": {"type": "string"}},
                            "required": ["skill_name"],
                        },
                    }
                ],
                "tool_choice": "auto",
                "text": {"format": {"type": "json_object"}},
                "store": False,
            },
        ),
    ]
    if not args.skip_stream:
        cases.append(
            (
                "vbf_probe_tools_json_object_stream",
                {
                    **common,
                    "tools": [
                        {
                            "type": "function",
                            "name": "load_skill",
                            "description": "Load one skill schema.",
                            "parameters": {
                                "type": "object",
                                "properties": {"skill_name": {"type": "string"}},
                                "required": ["skill_name"],
                            },
                        }
                    ],
                    "tool_choice": "auto",
                    "text": {"format": {"type": "json_object"}},
                    "stream": True,
                    "store": False,
                },
            )
        )

    for label, body in cases:
        post_case(
            label=label,
            url=url,
            api_key=args.api_key,
            user_agent=args.user_agent,
            body=body,
            timeout=args.timeout,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
