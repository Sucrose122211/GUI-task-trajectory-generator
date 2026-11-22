"""Output checks do not imply independent grounding accuracy."""

import math
import re


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_output(payload, sample, point_tolerance=0.002):
    errors, flags = [], []
    expected = {"status", "visual_steps", "final_click", "review_reason"}
    if not isinstance(payload, dict) or set(payload) != expected:
        return {"valid": False, "errors": ["Unexpected output schema"], "flags": []}
    status = payload["status"]
    steps, reason = payload["visual_steps"], payload["review_reason"]
    if status not in ("ok", "needs_review"):
        errors.append("Unknown status")
    if not isinstance(reason, str):
        errors.append("review_reason must be text")
    if not isinstance(steps, list) or any(not isinstance(s, str) or not s.strip() for s in steps):
        errors.append("visual_steps must be an array of nonempty strings")
        steps = []
    if status == "needs_review":
        if payload["final_click"] is not None or steps or not reason:
            errors.append("needs_review requires empty steps, null click and a reason")
        return {"valid": not errors, "errors": errors, "flags": ["teacher_needs_review"]}
    if not steps:
        errors.append("No visual observations")
    click = payload["final_click"]
    if not isinstance(click, dict) or set(click) != {"x", "y"}:
        errors.append("Missing final_click")
    elif not all(number(v) and 0 <= v <= 1 for v in click.values()):
        errors.append("Click must be finite normalized coordinates")
    else:
        x, y = click["x"], click["y"]
        box = sample["answer"]["bbox"]
        if box:
            x1, y1, x2, y2 = box
            if not (x1 <= x <= x2 and y1 <= y <= y2):
                errors.append("Click is outside target bbox")
        elif math.dist([x, y], sample["answer"]["point"]) > point_tolerance:
            errors.append("Click differs from reference point beyond tolerance")
    text = " ".join(steps)
    if not 2 <= len(steps) <= 6:
        flags.append("step_count_outside_guideline")
    if re.search(r"\b(cropped|zoomed|opened|clicked)\b", text, flags=re.I):
        flags.append("possible_unexecuted_action")
    if re.search(r"\b0\.\d+\b", text):
        flags.append("possible_coordinate_copy")
    if re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", text):
        flags.append("possible_non_english")
    if len({s.lower().strip() for s in steps}) != len(steps):
        flags.append("repeated_steps")
    if reason:
        flags.append("ok_with_review_reason")
    return {"valid": not errors, "errors": errors, "flags": flags}
