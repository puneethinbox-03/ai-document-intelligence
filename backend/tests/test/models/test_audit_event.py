from sqlalchemy import DateTime, JSON, String, Uuid

from app.models.audit_event import AuditEvent


def test_audit_event_uses_expected_table_name():
    assert AuditEvent.__tablename__ == "audit_events"


def test_audit_event_has_expected_columns():
    expected_columns = {
        "id",
        "actor_user_id",
        "action",
        "resource_type",
        "resource_id",
        "event_metadata",
        "request_id",
        "created_at",
    }

    assert expected_columns.issubset(AuditEvent.__table__.columns.keys())


def test_audit_event_actor_user_id_is_optional_foreign_key():
    column = AuditEvent.__table__.c.actor_user_id

    assert column.nullable is True
    assert len(column.foreign_keys) == 1
    assert next(iter(column.foreign_keys)).target_fullname == "users.id"


def test_audit_event_action_and_resource_type_are_required():
    assert AuditEvent.__table__.c.action.nullable is False
    assert isinstance(AuditEvent.__table__.c.action.type, String)
    assert AuditEvent.__table__.c.action.type.length == 100

    assert AuditEvent.__table__.c.resource_type.nullable is False
    assert isinstance(AuditEvent.__table__.c.resource_type.type, String)
    assert AuditEvent.__table__.c.resource_type.type.length == 100


def test_audit_event_resource_id_is_optional_uuid_without_foreign_key():
    column = AuditEvent.__table__.c.resource_id

    assert column.nullable is True
    assert isinstance(column.type, Uuid)
    assert len(column.foreign_keys) == 0


def test_audit_event_metadata_is_optional_json():
    column = AuditEvent.__table__.c.event_metadata

    assert column.nullable is True
    assert isinstance(column.type, JSON)


def test_audit_event_request_id_is_optional():
    column = AuditEvent.__table__.c.request_id

    assert column.nullable is True
    assert isinstance(column.type, String)
    assert column.type.length == 64


def test_audit_event_created_at_is_required_and_timezone_aware():
    column = AuditEvent.__table__.c.created_at

    assert column.nullable is False
    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True
    assert column.server_default is not None


def test_audit_event_does_not_have_updated_at():
    assert "updated_at" not in AuditEvent.__table__.columns


def test_audit_event_actor_foreign_key_uses_set_null():
    foreign_key = next(
        iter(AuditEvent.__table__.c.actor_user_id.foreign_keys)
    )

    assert foreign_key.ondelete == "SET NULL"


def test_audit_event_actor_created_at_index():
    indexes = {
        index.name: index
        for index in AuditEvent.__table__.indexes
    }

    index = indexes["ix_audit_events_actor_user_id_created_at"]

    assert [column.name for column in index.columns] == [
        "actor_user_id",
        "created_at",
    ]


def test_audit_event_resource_lookup_index():
    indexes = {
        index.name: index
        for index in AuditEvent.__table__.indexes
    }

    index = indexes["ix_audit_events_resource_type_resource_id"]

    assert [column.name for column in index.columns] == [
        "resource_type",
        "resource_id",
    ]
