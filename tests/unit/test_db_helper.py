"""
Unit and integration tests for DatabaseHelper in src/data/db_helper.py

Unit tests cover:
- _validate_identifier(): valid names pass, injection attempts and empty raise
- _validate_identifiers(): batch validation

Integration tests (SQLite in-memory) cover:
- insert_data, update_data, delete_data, batch_insert_data
- Identifier validation in CRUD methods
"""
import re
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Unit tests: _validate_identifier / _validate_identifiers
# ---------------------------------------------------------------------------

class TestValidateIdentifier:
    """Unit tests for DatabaseHelper._validate_identifier()."""

    def _call(self, name, context="identifier"):
        """Helper to call the static method."""
        from data.db_helper import DatabaseHelper
        return DatabaseHelper._validate_identifier(name, context)

    # -- Valid identifiers --------------------------------------------------

    @pytest.mark.parametrize("valid_name", [
        "users",
        "user_name",
        "Users",
        "_private",
        "a",
        "A",
        "_",
        "table123",
        "my_column_name_123",
    ])
    def test_valid_identifiers_pass(self, valid_name):
        """Valid SQL identifiers should pass without error and return the name."""
        result = self._call(valid_name)
        assert result == valid_name

    # -- Empty / None -------------------------------------------------------

    @pytest.mark.parametrize("invalid_name", [
        "",
        None,
    ])
    def test_empty_or_none_raises(self, invalid_name):
        """Empty string or None should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            self._call(invalid_name)

    # -- SQL injection attempts ---------------------------------------------

    @pytest.mark.parametrize("malicious", [
        "users; DROP TABLE",
        "users' OR '1'='1",
        "users\" OR \"1\"=\"1",
        "admin--",
        "table/*comment*/",
        "select * from users",
        "DELETE FROM users",
        "'; EXEC xp_cmdshell",
    ])
    def test_sql_injection_attempts_raise(self, malicious):
        """SQL injection patterns should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            self._call(malicious)

    # -- Boundary / format violations ---------------------------------------

    @pytest.mark.parametrize("bad_name", [
        "123abc",        # starts with digit
        "user name",     # space
        "user-name",     # hyphen
        "user.name",     # dot
        "DROP TABLE",    # space + SQL
    ])
    def test_invalid_format_raises(self, bad_name):
        """Names with invalid characters or format should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            self._call(bad_name)

    def test_custom_context_in_error_message(self):
        """The error message should include a custom context string."""
        with pytest.raises(ValueError, match="Invalid SQL table name"):
            from data.db_helper import DatabaseHelper
            DatabaseHelper._validate_identifier("bad name", "table name")


class TestValidateIdentifiers:
    """Unit tests for DatabaseHelper._validate_identifiers()."""

    def test_valid_list_passes(self):
        """A list of valid identifiers should pass without error."""
        from data.db_helper import DatabaseHelper
        # Should not raise
        DatabaseHelper._validate_identifiers(
            ["users", "email", "name", "created_at"]
        )

    def test_empty_list_passes(self):
        """An empty list should pass (nothing to validate)."""
        from data.db_helper import DatabaseHelper
        DatabaseHelper._validate_identifiers([])

    def test_invalid_item_raises(self):
        """A list with at least one invalid identifier should raise."""
        from data.db_helper import DatabaseHelper
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            DatabaseHelper._validate_identifiers(
                ["users", "email", "DROP TABLE users"]
            )

    def test_error_on_first_invalid(self):
        """Validation should raise on the first invalid item encountered."""
        from data.db_helper import DatabaseHelper
        with pytest.raises(ValueError, match="'123bad'"):
            DatabaseHelper._validate_identifiers(
                ["users", "123bad", "still_bad; DROP"]
            )


# ---------------------------------------------------------------------------
# Integration tests: DatabaseHelper with SQLite in-memory
# ---------------------------------------------------------------------------

@pytest.fixture
def db_helper_instance():
    """Create a fresh DatabaseHelper and a test table in SQLite in-memory."""
    from data.db_helper import DatabaseHelper

    helper = DatabaseHelper()

    # Create a test table via raw SQL
    with helper.get_session("sqlite", database=":memory:") as session:
        session.execute(text(
            "CREATE TABLE test_users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  name TEXT NOT NULL,"
            "  email TEXT NOT NULL"
            ")"
        ))

    yield helper

    # Teardown
    helper.close_all()


class TestDatabaseHelperIntegration:
    """Integration tests using SQLite in-memory."""

    # -- insert_data --------------------------------------------------------

    def test_insert_data(self, db_helper_instance):
        """insert_data should return the rowcount and persist the row."""
        helper = db_helper_instance

        rowcount = helper.insert_data(
            "sqlite",
            "test_users",
            {"name": "Alice", "email": "alice@example.com"},
            database=":memory:",
        )

        assert rowcount == 1

        # Verify by querying
        with helper.get_session("sqlite", database=":memory:") as session:
            result = session.execute(text(
                "SELECT name, email FROM test_users WHERE name = :n"),
                {"n": "Alice"},
            ).fetchone()
            assert result is not None
            assert result[0] == "Alice"
            assert result[1] == "alice@example.com"

    def test_insert_data_invalid_table_raises(self, db_helper_instance):
        """insert_data should reject dangerous table names."""
        helper = db_helper_instance

        with pytest.raises(ValueError, match="Invalid SQL table name"):
            helper.insert_data(
                "sqlite",
                "test_users; DROP TABLE test_users",
                {"name": "Eve"},
                database=":memory:",
            )

    def test_insert_data_invalid_column_raises(self, db_helper_instance):
        """insert_data should reject dangerous column names."""
        helper = db_helper_instance

        with pytest.raises(ValueError, match="Invalid SQL column name"):
            helper.insert_data(
                "sqlite",
                "test_users",
                {"name; DROP TABLE test_users": "Eve"},
                database=":memory:",
            )

    def test_insert_data_empty_data(self, db_helper_instance):
        """insert_data with empty data dict raises ValueError (invalid SQL)."""
        helper = db_helper_instance

        with pytest.raises(Exception):
            helper.insert_data(
                "sqlite",
                "test_users",
                {},
                database=":memory:",
            )

    # -- update_data --------------------------------------------------------

    def test_update_data(self, db_helper_instance):
        """update_data should modify existing rows."""
        helper = db_helper_instance

        # Seed
        helper.insert_data(
            "sqlite",
            "test_users",
            {"name": "Bob", "email": "bob@example.com"},
            database=":memory:",
        )

        # Update
        rowcount = helper.update_data(
            "sqlite",
            "test_users",
            {"email": "bob_new@example.com"},
            "name = :cond_name",
            {"cond_name": "Bob"},
            database=":memory:",
        )

        assert rowcount == 1

        # Verify
        with helper.get_session("sqlite", database=":memory:") as session:
            result = session.execute(text(
                "SELECT email FROM test_users WHERE name = :n"),
                {"n": "Bob"},
            ).fetchone()
            assert result[0] == "bob_new@example.com"

    def test_update_data_no_match(self, db_helper_instance):
        """update_data should return 0 when no rows match."""
        helper = db_helper_instance

        rowcount = helper.update_data(
            "sqlite",
            "test_users",
            {"email": "x@y.com"},
            "name = :cond_name",
            {"cond_name": "Nobody"},
            database=":memory:",
        )
        assert rowcount == 0

    def test_update_data_invalid_table_raises(self, db_helper_instance):
        """update_data validates the table name."""
        helper = db_helper_instance

        with pytest.raises(ValueError, match="Invalid SQL table name"):
            helper.update_data(
                "sqlite",
                "test_users; DELETE FROM test_users",
                {"email": "x@y.com"},
                "id = :cond_id",
                {"cond_id": 1},
                database=":memory:",
            )

    # -- delete_data --------------------------------------------------------

    def test_delete_data(self, db_helper_instance):
        """delete_data should remove matching rows."""
        helper = db_helper_instance

        helper.insert_data(
            "sqlite",
            "test_users",
            {"name": "Charlie", "email": "charlie@example.com"},
            database=":memory:",
        )
        helper.insert_data(
            "sqlite",
            "test_users",
            {"name": "Dave", "email": "dave@example.com"},
            database=":memory:",
        )

        rowcount = helper.delete_data(
            "sqlite",
            "test_users",
            "name = :cond_name",
            {"cond_name": "Charlie"},
            database=":memory:",
        )

        assert rowcount == 1

        # Verify Charlie is gone, Dave remains
        with helper.get_session("sqlite", database=":memory:") as session:
            rows = session.execute(text(
                "SELECT name FROM test_users ORDER BY name")
            ).fetchall()
            names = [r[0] for r in rows]
            assert "Charlie" not in names
            assert "Dave" in names

    def test_delete_data_all_rows(self, db_helper_instance):
        """delete_data with a condition matching all rows should remove everything."""
        helper = db_helper_instance

        helper.insert_data(
            "sqlite",
            "test_users",
            {"name": "X", "email": "x@x.com"},
            database=":memory:",
        )
        helper.insert_data(
            "sqlite",
            "test_users",
            {"name": "Y", "email": "y@y.com"},
            database=":memory:",
        )

        rowcount = helper.delete_data(
            "sqlite",
            "test_users",
            "1 = 1",
            database=":memory:",
        )
        assert rowcount == 2

    def test_delete_data_no_match(self, db_helper_instance):
        """delete_data should return 0 when no rows match."""
        helper = db_helper_instance

        rowcount = helper.delete_data(
            "sqlite",
            "test_users",
            "name = :cond_name",
            {"cond_name": "NonExistent"},
            database=":memory:",
        )
        assert rowcount == 0

    def test_delete_data_invalid_table_raises(self, db_helper_instance):
        """delete_data validates the table name."""
        helper = db_helper_instance

        with pytest.raises(ValueError, match="Invalid SQL table name"):
            helper.delete_data(
                "sqlite",
                "test_users; DROP TABLE test_users",
                "1 = 1",
                database=":memory:",
            )

    # -- batch_insert_data --------------------------------------------------

    def test_batch_insert_data(self, db_helper_instance):
        """batch_insert_data should insert multiple rows."""
        helper = db_helper_instance

        data_list = [
            {"name": "Eve", "email": "eve@example.com"},
            {"name": "Frank", "email": "frank@example.com"},
            {"name": "Grace", "email": "grace@example.com"},
        ]

        rowcount = helper.batch_insert_data(
            "sqlite",
            "test_users",
            data_list,
            database=":memory:",
        )

        assert rowcount == 3

        # Verify
        with helper.get_session("sqlite", database=":memory:") as session:
            rows = session.execute(text(
                "SELECT name FROM test_users ORDER BY name")
            ).fetchall()
            assert [r[0] for r in rows] == ["Eve", "Frank", "Grace"]

    def test_batch_insert_data_empty_list(self, db_helper_instance):
        """batch_insert_data should return 0 for an empty list."""
        helper = db_helper_instance

        rowcount = helper.batch_insert_data(
            "sqlite",
            "test_users",
            [],
            database=":memory:",
        )
        assert rowcount == 0

    def test_batch_insert_data_invalid_table_raises(self, db_helper_instance):
        """batch_insert_data validates the table name."""
        helper = db_helper_instance

        with pytest.raises(ValueError, match="Invalid SQL table name"):
            helper.batch_insert_data(
                "sqlite",
                "test_users; DROP TABLE",
                [{"name": "X", "email": "x@x.com"}],
                database=":memory:",
            )

    def test_batch_insert_data_invalid_column_raises(self, db_helper_instance):
        """batch_insert_data validates column names."""
        helper = db_helper_instance

        with pytest.raises(ValueError, match="Invalid SQL column name"):
            helper.batch_insert_data(
                "sqlite",
                "test_users",
                [{"name; DROP TABLE": "X", "email": "x@x.com"}],
                database=":memory:",
            )
