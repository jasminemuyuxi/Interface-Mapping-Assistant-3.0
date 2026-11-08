"""Verify customer-interface metadata and PostgreSQL DDL without a database."""

import importlib
import importlib.abc
import socket
import sys

import pytest
import sqlalchemy
from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateIndex, CreateTable


class _RejectDatabaseImports(importlib.abc.MetaPathFinder):
    """Fail rather than loading configuration, dotenv, or PostgreSQL drivers."""

    blocked = ("db.database", "dotenv", "psycopg", "psycopg2")

    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".")
               for name in self.blocked):
            raise AssertionError(f"Forbidden offline import: {fullname}")
        return None


@pytest.fixture(scope="module")
def metadata():
    """Import only required models under explicit no-connection guards."""
    guard = _RejectDatabaseImports()
    assert not any(name in sys.modules for name in guard.blocked)
    assert "models.customer_interface" not in sys.modules

    def reject_connection(*args, **kwargs):
        raise AssertionError("Database/network access is forbidden in offline tests")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sqlalchemy, "create_engine", reject_connection)
        patch.setattr(sqlalchemy.engine, "create_engine", reject_connection)
        patch.setattr(Engine, "connect", reject_connection)
        patch.setattr(Engine, "raw_connection", reject_connection)
        patch.setattr(socket, "create_connection", reject_connection)
        patch.setattr(socket.socket, "connect", reject_connection)
        sys.meta_path.insert(0, guard)
        try:
            customer = importlib.import_module("models.customer").Customer
            base = importlib.import_module("db.base").Base
            dialect = postgresql.dialect()
            before = str(CreateTable(customer.__table__).compile(dialect=dialect))
            before_indexes = sorted(
                str(CreateIndex(index).compile(dialect=dialect))
                for index in customer.__table__.indexes
            )
            existing = dict(base.metadata.tables)
            model = importlib.import_module("models.customer_interface").CustomerInterface
            yield model, customer, base, dialect, before, before_indexes, existing
            assert not any(name in sys.modules for name in guard.blocked)
        finally:
            sys.meta_path.remove(guard)


def test_columns_and_stable_identity(metadata):
    model, _, base, _, *_ = metadata
    table = model.__table__
    assert table.metadata is base.metadata
    assert list(table.c.keys()) == [
        "customer_interface_id", "customer_id", "interface_code",
        "interface_name", "created_at", "updated_at",
    ]
    assert all(not column.nullable for column in table.c)
    assert list(table.primary_key.columns.keys()) == ["customer_interface_id"]
    assert table.primary_key.name == "pk_customer_interfaces"
    for name in ("customer_interface_id", "customer_id"):
        assert isinstance(table.c[name].type, BigInteger)
    assert table.c.customer_interface_id.identity is not None
    assert table.c.customer_id.identity is None


def test_display_fields_and_no_plain_uniqueness(metadata):
    table = metadata[0].__table__
    for name, length in (("interface_code", 100), ("interface_name", 200)):
        column = table.c[name]
        assert isinstance(column.type, String)
        assert column.type.length == length
        assert column.default is None and column.server_default is None
        assert not column.unique
    assert not any(isinstance(item, UniqueConstraint) for item in table.constraints)
    value = "MiXeD/\u5ba2\u6237@v1"
    first = metadata[0](customer_id=1, interface_code=value, interface_name="Same name")
    second = metadata[0](customer_id=2, interface_code="Different", interface_name="Same name")
    assert first.interface_code == value
    assert first.interface_name == second.interface_name
    # Object construction checks display preservation, not database acceptance.


def test_customer_fk_resolves_and_lookup_index(metadata):
    table = metadata[0].__table__
    foreign_key, = table.foreign_keys
    assert foreign_key.parent is table.c.customer_id
    assert foreign_key.column is metadata[1].__table__.c.customer_id
    assert foreign_key.ondelete == "RESTRICT"
    assert foreign_key.onupdate is None
    assert foreign_key.constraint.name == "fk_customer_interfaces_customer_id_customers"
    index = next(i for i in table.indexes if i.name == "ix_customer_interfaces_customer_id")
    assert not index.unique
    assert list(index.columns.keys()) == ["customer_id"]


def test_nonblank_checks(metadata):
    table = metadata[0].__table__
    checks = {c.name: str(c.sqltext) for c in table.constraints
              if isinstance(c, CheckConstraint)}
    assert checks == {
        "ck_customer_interfaces_interface_code_not_blank": "interface_code ~ '[^[:space:]]'",
        "ck_customer_interfaces_interface_name_not_blank": "interface_name ~ '[^[:space:]]'",
    }


def test_global_expression_index_and_ddl(metadata):
    table, dialect = metadata[0].__table__, metadata[3]
    assert len(table.indexes) == 2
    unique, = [i for i in table.indexes if i.unique]
    assert unique.name == "ux_customer_interfaces_interface_code_ci"
    expression, = unique.expressions
    assert expression.name == "lower"
    assert list(expression.clauses) == [table.c.interface_code]
    assert unique.dialect_options["postgresql"]["where"] is None
    sql = str(CreateIndex(unique).compile(dialect=dialect))
    assert sql == (
        "CREATE UNIQUE INDEX ux_customer_interfaces_interface_code_ci "
        "ON customer_interfaces (lower(interface_code))"
    )
    lookup = next(i for i in table.indexes if not i.unique)
    assert str(CreateIndex(lookup).compile(dialect=dialect)) == (
        "CREATE INDEX ix_customer_interfaces_customer_id "
        "ON customer_interfaces (customer_id)"
    )


def test_timestamp_configuration(metadata):
    table, dialect = metadata[0].__table__, metadata[3]
    for name in ("created_at", "updated_at"):
        column = table.c[name]
        assert isinstance(column.type, DateTime) and column.type.timezone
        assert str(column.server_default.arg.compile(dialect=dialect)) == "now()"
        assert column.default is None
    assert table.c.created_at.onupdate is None
    assert str(table.c.updated_at.onupdate.arg.compile(dialect=dialect)) == "now()"
    assert table.c.updated_at.server_onupdate is None


def test_postgresql_table_ddl_and_existing_metadata_unchanged(metadata):
    model, customer, base, dialect, before, before_indexes, existing = metadata
    ddl = " ".join(str(CreateTable(model.__table__).compile(dialect=dialect)).split())
    for fragment in (
        "customer_interface_id BIGINT GENERATED BY DEFAULT AS IDENTITY",
        "customer_id BIGINT NOT NULL", "interface_code VARCHAR(100) NOT NULL",
        "interface_name VARCHAR(200) NOT NULL",
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL",
        "updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL",
        "CONSTRAINT pk_customer_interfaces PRIMARY KEY (customer_interface_id)",
        "CHECK (interface_code ~ '[^[:space:]]')",
        "CHECK (interface_name ~ '[^[:space:]]')",
        "FOREIGN KEY(customer_id) REFERENCES customers (customer_id) ON DELETE RESTRICT",
    ):
        assert fragment in ddl
    assert "UNIQUE" not in ddl  # Functional uniqueness is compiled separately.
    assert str(CreateTable(customer.__table__).compile(dialect=dialect)) == before
    assert sorted(str(CreateIndex(i).compile(dialect=dialect))
                  for i in customer.__table__.indexes) == before_indexes
    assert set(base.metadata.tables) == set(existing) | {"customer_interfaces"}
    assert all(base.metadata.tables[name] is table for name, table in existing.items())
    assert not any(name.startswith("models.standard_") for name in sys.modules)
