"""Docker build log parser — extracts errors from docker build output."""

def parse_build_error(log: str) -> dict:
    lines = log.splitlines()
    error_lines = [l for l in lines if any(k in l for k in ["ERROR", "error", "failed", "FAILED"])]
    step = next((l for l in lines if l.startswith("Step")), "Unknown step")
    return {"step": step, "errors": error_lines[:20], "raw": log[-3000:]}
