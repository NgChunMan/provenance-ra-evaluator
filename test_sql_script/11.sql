-- TPC-H Q11 (Important Stock Identification) — simplified for provenance-aware RA evaluation.
-- Original: GROUP BY ps_partkey → replaced with DISTINCT.
-- Removed: aggregate sum(ps_supplycost * ps_availqty), HAVING clause.
-- ps_partkey%512=0 kept as data reduction filter.

SELECT DISTINCT
    ps_partkey
FROM
    partsupp,
    supplier,
    nation
WHERE
    ps_suppkey = s_suppkey
    AND s_nationkey = n_nationkey
    AND n_name = 'GERMANY'
    AND ps_partkey%512 = 0
