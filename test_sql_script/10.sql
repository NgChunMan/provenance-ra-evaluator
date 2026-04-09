-- TPC-H Q10 (Returned Item Reporting) — simplified for provenance-aware RA evaluation.
-- Original: GROUP BY c_custkey, c_name, c_acctbal, ... → replaced with DISTINCT.
-- Removed: aggregate sum(l_extendedprice * (1-l_discount)).
-- Date interval: date '1993-10-01' + interval '3' month (computed by SQL translator).
-- l_partkey%64=0 kept as data reduction filter.

SELECT DISTINCT
    c_custkey,
    c_name,
    c_acctbal,
    c_phone,
    n_name,
    c_address,
    c_comment
FROM
    customer,
    orders,
    lineitem,
    nation
WHERE
    c_custkey = o_custkey
    AND l_orderkey = o_orderkey
    AND o_orderdate >= date '1993-10-01'
    AND o_orderdate < date '1993-10-01' + interval '3' month
    AND l_returnflag = 'R'
    AND c_nationkey = n_nationkey
    AND l_partkey%64 = 0
