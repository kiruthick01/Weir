"""Send synthetic approval requests to a running local Weir instance.

Examples::

    python scripts/simulate_requests.py --duration 60 --ramp
    python scripts/simulate_requests.py --rate 5 --approver-email alice.approver@example.com
"""

from __future__ import annotations

import argparse
import json
import random
import time
import urllib.error
import urllib.request
import uuid


SEEDED_APPROVERS = [
    "alice.approver@example.com",
    "bob.approver@example.com",
    "carol.approver@example.com",
    "dave.approver@example.com",
    "erin.approver@example.com",
]

REQUEST_CLASSES = [
    ("procurement_low_value", 1000),
    ("procurement_high_value", None),
    ("access_request_standard", None),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic Weir approval traffic")
    parser.add_argument("--rate", type=float, default=1.0, help="requests per second")
    parser.add_argument("--duration", type=float, default=120.0, help="run duration in seconds")
    parser.add_argument("--api-url", default="http://localhost:8080")
    parser.add_argument("--approver-email", default=None)
    parser.add_argument("--ramp", action="store_true", help="increase traffic gradually over the run")
    args = parser.parse_args()
    if args.rate <= 0 or args.duration <= 0:
        parser.error("--rate and --duration must be positive")
    if args.approver_email is not None and args.approver_email not in SEEDED_APPROVERS:
        parser.error("--approver-email must be one of the seeded approvers")
    return args


def make_payload(request_class: str, threshold: int | None) -> dict:
    if threshold is not None:
        # Deliberately produce values on both sides of the low-value boundary.
        amount = random.choice(
            [
                random.randint(50, threshold),
                random.randint(threshold + 1, threshold * 5),
            ]
        )
    else:
        amount = random.randint(100, 10000)
    return {
        "amount": amount,
        "currency": "USD",
        "description": f"synthetic {request_class.replace('_', ' ')} request",
        "demo": True,
    }


def post_request(api_url: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/v1/requests",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8"))
        except Exception:
            detail = {"detail": str(error)}
        return {"status": error.code, "detail": detail}
    except Exception as error:
        return {"status": "error", "detail": str(error)}


def main() -> None:
    args = parse_args()
    started = time.monotonic()
    sent = 0
    approver_index = 0

    print(
        f"Simulating traffic: base_rate={args.rate:g}/s, "
        f"duration={args.duration:g}s, ramp={args.ramp}"
    )
    if args.ramp:
        # Intentionally no simulated approver actions happen here: the queue
        # must build naturally so the demo visibly reaches Elevated/Critical.
        print("Ramp mode: requests are deliberately left undecided to build pressure.")

    while True:
        elapsed = time.monotonic() - started
        if elapsed >= args.duration:
            break

        progress = min(1.0, elapsed / args.duration)
        rate = args.rate * (1.0 + 9.0 * progress) if args.ramp else args.rate
        class_name, threshold = random.choice(REQUEST_CLASSES)
        approver_email = args.approver_email or SEEDED_APPROVERS[approver_index % len(SEEDED_APPROVERS)]
        approver_index += 1
        body = {
            "source_system": "weir-simulator",
            "external_ref": f"sim-{uuid.uuid4()}",
            "request_class": class_name,
            "approver_email": approver_email,
            "payload": make_payload(class_name, threshold),
        }
        result = post_request(args.api_url, body)
        print(
            f"[{sent + 1:04d}] status={result.get('status')} "
            f"pressure_state={result.get('pressure_state', '-')}",
            flush=True,
        )
        sent += 1

        interval = 1.0 / rate
        next_due = started + elapsed + interval
        time.sleep(max(0.0, next_due - time.monotonic()))

    print(f"Simulation complete: sent={sent}")


if __name__ == "__main__":
    main()

