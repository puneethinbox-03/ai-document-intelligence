from sqlalchemy import DateTime, Integer, JSON, String

from app.models.usage_event import UsageEvent


def test_usage_event_uses_expected_table_name():
    assert UsageEvent.__tablename__ == "usage_events"


def test_usage_event_has_expected_columns():
    expected_columns = {
        "id",
        "user_id",
        "event_type",
        "quantity",
        "duration_ms",
        "event_metadata",
        "created_at",
    }

    assert expected_columns.issubset(UsageEvent.__table__.columns.keys())


def test_usage_event_user_id_is_required_foreign_key():
    column = UsageEvent.__table__.c.user_id

    assert column.nullable is False
    assert len(column.foreign_keys) == 1
    assert next(iter(column.foreign_keys)).target_fullname == "users.id"


def test_usage_event_type_is_required():
    column = UsageEvent.__table__.c.event_type

    assert column.nullable is False
    assert isinstance(column.type, String)
    assert column.type.length == 100


def test_usage_event_quantity_defaults_to_one():
    column = UsageEvent.__table__.c.quantity

    assert column.nullable is False
    assert isinstance(column.type, Integer)
    assert column.default.arg == 1
    assert column.server_default.arg == "1"


def test_usage_event_duration_is_optional_integer():
    column = UsageEvent.__table__.c.duration_ms

    assert column.nullable is True
    assert isinstance(column.type, Integer)


def test_usage_event_metadata_is_optional_json():
    column = UsageEvent.__table__.c.event_metadata

    assert column.nullable is True
    assert isinstance(column.type, JSON)


def test_usage_event_created_at_is_required_and_timezone_aware():
    column = UsageEvent.__table__.c.created_at

    assert column.nullable is False
    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True
    assert column.server_default is not None


def test_usage_event_does_not_have_updated_at():
    assert "updated_at" not in UsageEvent.__table__.columns


def test_usage_event_check_constraints():
    from sqlalchemy import CheckConstraint

    constraints = {
        constraint.name
        for constraint in UsageEvent.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert constraints == {
        "ck_usage_events_quantity_positive",
        "ck_usage_events_duration_non_negative",
    }


def test_usage_event_user_foreign_key_cascades_on_delete():
    foreign_key = next(
        iter(UsageEvent.__table__.c.user_id.foreign_keys)
    )

    assert foreign_key.ondelete == "CASCADE"


def test_usage_event_user_created_at_index():
    indexes = {
        index.name: index
        for index in UsageEvent.__table__.indexes
    }

    index = indexes["ix_usage_events_user_id_created_at"]

    assert [column.name for column in index.columns] == [
        "user_id",
        "created_at",
    ]


def test_usage_event_type_created_at_index():
    indexes = {
        index.name: index
        for index in UsageEvent.__table__.indexes
    }

    index = indexes["ix_usage_events_event_type_created_at"]

    assert [column.name for column in index.columns] == [
        "event_type",
        "created_at",
    ]
