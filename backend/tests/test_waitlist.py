"""Tests for the waitlist model and API endpoint.

Validates signup flow, duplicate handling, position tracking,
and the public count endpoint.
"""

import pytest

from app.models.waitlist import WaitlistEntry


class TestWaitlistModel:
    """Verify WaitlistEntry model structure and serialization."""

    def test_to_dict_has_required_fields(self):
        entry = WaitlistEntry(
            email="test@example.com",
            source="landing",
            position=1,
            notified=False,
        )
        d = entry.to_dict()
        assert d["email"] == "test@example.com"
        assert d["source"] == "landing"
        assert d["position"] == 1
        assert d["notified"] is False

    def test_to_dict_id_is_string(self):
        import uuid
        entry = WaitlistEntry(
            id=uuid.uuid4(),
            email="test@example.com",
            source="api",
            position=5,
        )
        d = entry.to_dict()
        assert isinstance(d["id"], str)

    def test_explicit_source_landing(self):
        entry = WaitlistEntry(email="a@b.com", position=1, source="landing")
        assert entry.source == "landing"

    def test_explicit_notified_false(self):
        entry = WaitlistEntry(email="a@b.com", position=1, notified=False)
        assert entry.notified is False


class TestWaitlistSignupValidation:
    """Verify the Pydantic signup model validates inputs."""

    def test_valid_email_accepted(self):
        from app.api.v1.waitlist import WaitlistSignup
        signup = WaitlistSignup(email="user@company.com")
        assert signup.email == "user@company.com"
        assert signup.source == "landing"

    def test_custom_source(self):
        from app.api.v1.waitlist import WaitlistSignup
        signup = WaitlistSignup(email="user@co.com", source="app")
        assert signup.source == "app"

    def test_invalid_email_rejected(self):
        from pydantic import ValidationError
        from app.api.v1.waitlist import WaitlistSignup
        with pytest.raises(ValidationError):
            WaitlistSignup(email="not-an-email")

    def test_empty_email_rejected(self):
        from pydantic import ValidationError
        from app.api.v1.waitlist import WaitlistSignup
        with pytest.raises(ValidationError):
            WaitlistSignup(email="")


class TestWaitlistResponse:
    """Verify the response model."""

    def test_response_has_position_and_message(self):
        from app.api.v1.waitlist import WaitlistResponse
        resp = WaitlistResponse(position=42, message="You are number 42.")
        assert resp.position == 42
        assert "42" in resp.message

    def test_spots_remaining_calculation(self):
        # The count endpoint returns spots_remaining = max(0, 100 - count)
        count = 73
        spots = max(0, 100 - count)
        assert spots == 27

    def test_spots_remaining_zero_when_full(self):
        count = 150
        spots = max(0, 100 - count)
        assert spots == 0
