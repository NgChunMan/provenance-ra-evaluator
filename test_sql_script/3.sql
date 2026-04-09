-- TPC-H Q3 (Shipping Priority) — simplified for provenance-aware RA evaluation.
-- Original: GROUP BY l_orderkey, o_orderdate, o_shippriority → replaced with DISTINCT.
-- Removed: aggregate sum(l_extendedprice * (1-l_discount)).
-- Date interval: pre-computed.

SELECT DISTINCT
    l_orderkey,
    o_orderdate,
    o_shippriority
FROM
    customer,
    orders,
    lineitem
WHERE
    c_mktsegment = 'BUILDING'
    AND c_custkey = o_custkey
    AND l_orderkey = o_orderkey
    AND o_orderdate < date '1995-03-15'
    AND l_shipdate > date '1995-03-15'
