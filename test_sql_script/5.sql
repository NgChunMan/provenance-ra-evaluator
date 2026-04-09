-- TPC-H Q5 (Local Supplier Volume) — simplified for provenance-aware RA evaluation.
-- Original: GROUP BY n_name → replaced with DISTINCT.
-- Removed: aggregate sum(l_extendedprice * (1-l_discount)).
-- Date interval: date '1994-01-01' + interval '1' year (computed by SQL translator).
-- l_partkey%56=0 kept as data reduction filter.

SELECT DISTINCT
    n_name
FROM
    customer,
    orders,
    lineitem,
    supplier,
    nation,
    region
WHERE
    c_custkey = o_custkey
    AND l_orderkey = o_orderkey
    AND l_suppkey = s_suppkey
    AND c_nationkey = s_nationkey
    AND s_nationkey = n_nationkey
    AND n_regionkey = r_regionkey
    AND r_name = 'ASIA'
    AND o_orderdate >= date '1994-01-01'
    AND o_orderdate < date '1994-01-01' + interval '1' year
    AND l_partkey%56 = 0
