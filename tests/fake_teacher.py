"""Subprocess-level teacher fixture. Never contacts a service."""

import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
if args == ["--version"]:
    print("0.164.0")
elif "--help" in args:
    print(
        "--image --output-schema --ignore-user-config --ephemeral "
        "--restricted --safe-mode --json-schema --tools"
    )
elif args[:2] == ["login", "status"]:
    print("Logged in using ChatGPT")
elif args[:2] == ["auth", "status"]:
    print(json.dumps({"loggedIn": True, "authMethod": "claude.ai", "email": "private@example.com"}))
else:
    prompt = sys.stdin.read()
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("API credential unexpectedly inherited")
    counter = Path(os.environ["GUI_TEST_COUNTER"])
    counter.write_text(str(int(counter.read_text() if counter.exists() else "0") + 1))
    scenario = os.environ.get("GUI_TEST_SCENARIO", "success")
    if scenario == "limit":
        print(json.dumps({"type": "error", "message": "Usage limit reached"}))
        sys.exit(1)
    if scenario == "timeout":
        __import__("time").sleep(60)
    payload = {
        "status": "ok",
        "visual_steps": [
            "The target is in the central toolbar.",
            "Its visible label matches the requested button.",
        ],
        "final_click": {"x": 0.5, "y": 0.5},
        "review_reason": "",
    }
    if scenario == "invalid":
        payload["final_click"] = {"x": 0.95, "y": 0.95}
    if "exec" in args:
        image = Path(args[args.index("--image") + 1])
        assert image.is_file() and "Reference answer" in prompt
        if scenario == "tool":
            print(json.dumps({"type": "item.completed", "item": {"type": "command_execution"}}))
        target = Path(args[args.index("--output-last-message") + 1])
        target.write_text(json.dumps(payload))
        # Private reasoning must not be persisted by the runner.
        print(
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "reasoning", "text": "PRIVATE_REASONING_SENTINEL"},
                }
            )
        )
        print(json.dumps({"type": "turn.completed", "usage": {"output_tokens": 40}}))
    else:
        image = next(Path.cwd().glob("screenshot.*"))
        assert str(image) in prompt
        if scenario == "tool":
            print(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "tool_use", "id": "bad", "name": "Bash", "input": {}}
                            ]
                        },
                    }
                )
            )
        if scenario != "no_image":
            print(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "read-1",
                                    "name": "Read",
                                    "input": {"file_path": str(image)},
                                }
                            ]
                        },
                    }
                )
            )
            print(
                json.dumps(
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "read-1",
                                    "content": [
                                        {
                                            "type": "image",
                                            "source": {"type": "base64", "data": "PRIVATE_IMAGE"},
                                        }
                                    ],
                                }
                            ]
                        },
                    }
                )
            )
        print(
            json.dumps(
                {
                    "type": "result",
                    "is_error": False,
                    "structured_output": payload,
                    "usage": {"output_tokens": 40},
                }
            )
        )
