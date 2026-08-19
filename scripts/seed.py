"""Seed a small, repeatable local dataset for Weir demos.

Run from the repository root with: ``python scripts/seed.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make ``app`` importable when this file is executed directly from scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import ApproverModel, RequestClassModel, create_session_factory
from app.settings import Settings


APPROVERS = [
    {"email": "alice.approver@example.com", "name": "Alice Approver", "backup": "bob.approver@example.com"},
    {"email": "bob.approver@example.com", "name": "Bob Approver", "backup": "alice.approver@example.com"},
    {"email": "carol.approver@example.com", "name": "Carol Approver", "backup": "dave.approver@example.com"},
    {"email": "dave.approver@example.com", "name": "Dave Approver", "backup": "carol.approver@example.com"},
    {"email": "erin.approver@example.com", "name": "Erin Approver", "backup": "alice.approver@example.com"},
]

REQUEST_CLASSES = [
    {
        "name": "procurement_low_value",
        "max_wait_seconds": 300,
        "auto_approve_threshold": 1000,
        "risk_tier": "low",
    },
    {
        "name": "procurement_high_value",
        "max_wait_seconds": 1800,
        "auto_approve_threshold": None,
        "risk_tier": "high",
    },
    {
        "name": "access_request_standard",
        "max_wait_seconds": 600,
        "auto_approve_threshold": None,
        "risk_tier": "medium",
    },
]


def main() -> None:
    settings = Settings()
    session_factory, engine = create_session_factory(settings.database_url)
    session = session_factory()
    created_approvers = 0
    updated_approvers = 0
    created_classes = 0
    updated_classes = 0

    try:
        approvers: dict[str, ApproverModel] = {}
        for item in APPROVERS:
            approver = session.scalar(
                select(ApproverModel).where(ApproverModel.email == item["email"])
            )
            if approver is None:
                approver = ApproverModel(
                    email=item["email"],
                    name=item["name"],
                )
                session.add(approver)
                session.flush()
                created_approvers += 1
            else:
                updated_approvers += 1
                approver.name = item["name"]
            approvers[item["email"]] = approver

        for item in APPROVERS:
            approvers[item["email"]].backup_approver_id = approvers[item["backup"]].id

        for item in REQUEST_CLASSES:
            request_class = session.get(RequestClassModel, item["name"])
            if request_class is None:
                request_class = RequestClassModel(**item)
                session.add(request_class)
                created_classes += 1
            else:
                updated_classes += 1
                request_class.max_wait_seconds = item["max_wait_seconds"]
                request_class.auto_approve_threshold = item["auto_approve_threshold"]
                request_class.risk_tier = item["risk_tier"]

        session.commit()
        print(
            "Seed complete: "
            f"approvers created={created_approvers}, updated={updated_approvers}; "
            f"request_classes created={created_classes}, updated={updated_classes}"
        )
        print("Backup pairs: Alice <-> Bob, Carol <-> Dave, Erin -> Alice")
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()

