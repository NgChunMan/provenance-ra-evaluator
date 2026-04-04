"""
RA translations for the TPC-H-derived queries we are keeping.

These tests intentionally do not wire through individual operators.
They serve as a stable fixture for the intended RA shape:
- selection
- projection
- cross product
- multiset sum
- deduplication

GROUP BY is not part of the RA language here.
"""

import pytest


TPCH_RA_QUERIES = {
    "3": """
        π[l_orderkey, o_orderdate, o_shippriority](
            σ[c_mktsegment = 'BUILDING'
              ∧ c_custkey = o_custkey
              ∧ l_orderkey = o_orderkey
              ∧ o_orderdate < date '1995-03-15'
              ∧ l_shipdate > date '1995-03-15'](
                customer × orders × lineitem
            )
        )
    """,
    "5": """
        π[n_name](
            σ[c_custkey = o_custkey
              ∧ l_orderkey = o_orderkey
              ∧ l_suppkey = s_suppkey
              ∧ c_nationkey = s_nationkey
              ∧ s_nationkey = n_nationkey
              ∧ n_regionkey = r_regionkey
              ∧ r_name = 'ASIA'
              ∧ o_orderdate >= date '1994-01-01'
              ∧ o_orderdate < date '1995-01-01'
              ∧ l_partkey % 56 = 0](
                customer × orders × lineitem × supplier × nation × region
            )
        )
    """,
    "10": """
        π[c_custkey, c_name, c_acctbal, c_phone, n_name, c_address, c_comment](
            σ[c_custkey = o_custkey
              ∧ l_orderkey = o_orderkey
              ∧ o_orderdate >= date '1993-10-01'
              ∧ o_orderdate < date '1993-10-01' + interval '3' month
              ∧ l_returnflag = 'R'
              ∧ c_nationkey = n_nationkey
              ∧ l_partkey % 64 = 0](
                customer × orders × lineitem × nation
            )
        )
    """,
    "19": """
        σ[l_partkey % 2 = 1
          ∧ (
            (p_partkey = l_partkey
             ∧ p_brand = 'Brand#12'
             ∧ p_container ∈ {'SM CASE', 'SM BOX', 'SM PACK', 'SM PKG'}
             ∧ l_quantity ∈ [1, 11]
             ∧ p_size ∈ [1, 5]
             ∧ l_shipmode ∈ {'AIR', 'AIR REG'}
             ∧ l_shipinstruct = 'DELIVER IN PERSON')
            ∨
            (p_partkey = l_partkey
             ∧ p_brand = 'Brand#23'
             ∧ p_container ∈ {'MED BAG', 'MED BOX', 'MED PKG', 'MED PACK'}
             ∧ l_quantity ∈ [10, 20]
             ∧ p_size ∈ [1, 10]
             ∧ l_shipmode ∈ {'AIR', 'AIR REG'}
             ∧ l_shipinstruct = 'DELIVER IN PERSON')
            ∨
            (p_partkey = l_partkey
             ∧ p_brand = 'Brand#34'
             ∧ p_container ∈ {'LG CASE', 'LG BOX', 'LG PACK', 'LG PKG'}
             ∧ l_quantity ∈ [20, 30]
             ∧ p_size ∈ [1, 15]
             ∧ l_shipmode ∈ {'AIR', 'AIR REG'}
             ∧ l_shipinstruct = 'DELIVER IN PERSON')
          ](
            lineitem × part
        )
    """,
}


@pytest.mark.parametrize("query_id", sorted(TPCH_RA_QUERIES))
def test_ra_translation_is_present(query_id):
    assert TPCH_RA_QUERIES[query_id].strip()


@pytest.mark.parametrize("query_id", sorted(TPCH_RA_QUERIES))
def test_ra_translation_does_not_use_group_by(query_id):
    assert "group by" not in TPCH_RA_QUERIES[query_id].lower()


@pytest.mark.parametrize("query_id", sorted(TPCH_RA_QUERIES))
def test_ra_translation_uses_ra_symbols(query_id):
    query = TPCH_RA_QUERIES[query_id]

    assert "σ" in query
    assert "×" in query
    assert "π" in query or query_id == "19"


@pytest.mark.parametrize("query_id", sorted(TPCH_RA_QUERIES))
def test_ra_translation_has_balanced_parentheses(query_id):
    query = TPCH_RA_QUERIES[query_id]
    assert query.count("(") == query.count(")")