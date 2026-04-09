-- TPC-H Q18 (Large Volume Customer) — simplified for provenance-aware RA evaluation.
-- Original: GROUP BY c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice → DISTINCT.
-- Removed: aggregate sum(l_quantity), HAVING.
-- l_partkey%64=0 kept as data reduction filter.

SELECT DISTINCT
    c_name,
    c_custkey,
    o_orderkey,
    o_orderdate,
    o_totalprice
FROM
    customer,
    orders,
    lineitem
WHERE
    c_custkey = o_custkey
    AND o_orderkey = l_orderkey
    AND l_partkey%64 = 0
