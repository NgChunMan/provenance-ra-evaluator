-- TPC-H Q7 (Volume Shipping) — simplified for provenance-aware RA evaluation.
-- Original: subquery + GROUP BY supp_nation, cust_nation, l_year → flattened.
-- Removed: aggregate sum(volume), extract(year), arithmetic expressions.
-- Self-join on nation handled via table aliases: nation n1, nation n2.
-- l_partkey%64=0 kept as data reduction filter.

SELECT DISTINCT
    n1.n_name,
    n2.n_name
FROM
    supplier,
    lineitem,
    orders,
    customer,
    nation n1,
    nation n2
WHERE
    s_suppkey = l_suppkey
    AND o_orderkey = l_orderkey
    AND c_custkey = o_custkey
    AND s_nationkey = n1.n_nationkey
    AND c_nationkey = n2.n_nationkey
    AND (
        (n1.n_name = 'FRANCE' AND n2.n_name = 'GERMANY')
        OR (n1.n_name = 'GERMANY' AND n2.n_name = 'FRANCE')
    )
    AND l_shipdate >= date '1995-01-01'
    AND l_shipdate <= date '1996-12-31'
    AND l_partkey%64 = 0
