import uuid

import pytest
from pydantic import ValidationError

from app.schemas.audit import AuditStartRequest


def test_audit_start_generates_seed_when_missing():
    payload = AuditStartRequest(
        target_id=uuid.uuid4(),
        dataset_id=uuid.uuid4(),
    )

    assert 1 <= payload.random_seed <= 2_147_483_647


def test_audit_start_preserves_provided_seed():
    payload = AuditStartRequest(
        target_id=uuid.uuid4(),
        dataset_id=uuid.uuid4(),
        random_seed=12345,
    )

    assert payload.random_seed == 12345


def test_audit_start_rejects_seed_outside_supported_range():
    with pytest.raises(ValidationError):
        AuditStartRequest(
            target_id=uuid.uuid4(),
            dataset_id=uuid.uuid4(),
            random_seed=0,
        )
