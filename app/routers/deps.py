from __future__ import annotations

from fastapi import Request


def get_db(request: Request):
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def settings(request: Request):
    return request.app.state.settings

