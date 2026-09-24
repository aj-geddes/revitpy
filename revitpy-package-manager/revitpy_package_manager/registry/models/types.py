"""Portable column types.

Production runs on PostgreSQL and uses native ``ARRAY``/``JSONB``/``INET``
types. Other dialects (notably SQLite, used by the test suite and for local
development) lack these, so each type falls back to a portable variant.
The PostgreSQL DDL is unchanged by these variants.
"""

from sqlalchemy import JSON, Boolean, String, and_, literal
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement


class _ArrayHasElement(FunctionElement):
    """``column`` (a list-of-strings column) contains the scalar ``value``.

    Rendered as ``column @> ARRAY[value]`` on PostgreSQL and as a
    ``json_each`` membership test on SQLite, where the column is JSON.
    """

    type = Boolean()
    inherit_cache = True
    name = "array_has_element"


@compiles(_ArrayHasElement)
def _array_has_element_default(element, compiler, **kw):
    column, value = list(element.clauses)
    return (
        f"({compiler.process(column, **kw)} @> "
        f"ARRAY[CAST({compiler.process(value, **kw)} AS VARCHAR)])"
    )


@compiles(_ArrayHasElement, "sqlite")
def _array_has_element_sqlite(element, compiler, **kw):
    column, value = list(element.clauses)
    return (
        f"EXISTS (SELECT 1 FROM json_each({compiler.process(column, **kw)}) "
        f"WHERE json_each.value = {compiler.process(value, **kw)})"
    )


class _StringArray(ARRAY):
    """``text[]`` whose ``contains`` works on every dialect.

    ``Column.contains(value)`` is true when the list holds ``value`` (a
    string), or every element of ``value`` (a list/tuple/set of strings).
    Stock ``ARRAY.contains`` always renders PostgreSQL's ``@>``, which fails
    on the JSON fallback column used elsewhere.
    """

    cache_ok = True

    class Comparator(ARRAY.Comparator):
        def contains(self, other, **kwargs):
            values = [other] if isinstance(other, str) else list(other)
            clauses = [
                _ArrayHasElement(self.expr, literal(v, String())) for v in values
            ]
            return clauses[0] if len(clauses) == 1 else and_(*clauses)

    comparator_factory = Comparator


# list[str] column: native text[] on PostgreSQL, JSON array elsewhere.
StringArray = _StringArray(String).with_variant(JSON(), "sqlite")

# dict column: JSONB on PostgreSQL, generic JSON elsewhere.
JSONDict = JSONB().with_variant(JSON(), "sqlite")

# IP address column: INET on PostgreSQL, a string (fits IPv6) elsewhere.
IPAddress = INET().with_variant(String(45), "sqlite")
