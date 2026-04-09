-- TPC-H Q19 (Discounted Revenue) — simplified for provenance-aware RA evaluation.
-- Original: GROUP BY 1 → replaced with DISTINCT.
-- Removed: aggregate sum(l_extendedprice * (1-l_discount)).
-- Arithmetic in conditions pre-computed: 1+10→11, 10+10→20, 20+10→30.
-- Kept: IN, BETWEEN, complex OR predicates.

SELECT DISTINCT
    l_partkey,
    p_partkey
FROM
    lineitem,
    part
WHERE
    l_partkey%2 = 1
    AND (
        (
            p_partkey = l_partkey
            AND p_brand = 'Brand#12'
            AND p_container IN ('SM CASE', 'SM BOX', 'SM PACK', 'SM PKG')
            AND l_quantity >= 1 AND l_quantity <= 11
            AND p_size BETWEEN 1 AND 5
            AND l_shipmode IN ('AIR', 'AIR REG')
            AND l_shipinstruct = 'DELIVER IN PERSON'
        )
        OR
        (
            p_partkey = l_partkey
            AND p_brand = 'Brand#23'
            AND p_container IN ('MED BAG', 'MED BOX', 'MED PKG', 'MED PACK')
            AND l_quantity >= 10 AND l_quantity <= 20
            AND p_size BETWEEN 1 AND 10
            AND l_shipmode IN ('AIR', 'AIR REG')
            AND l_shipinstruct = 'DELIVER IN PERSON'
        )
        OR
        (
            p_partkey = l_partkey
            AND p_brand = 'Brand#34'
            AND p_container IN ('LG CASE', 'LG BOX', 'LG PACK', 'LG PKG')
            AND l_quantity >= 20 AND l_quantity <= 30
            AND p_size BETWEEN 1 AND 15
            AND l_shipmode IN ('AIR', 'AIR REG')
            AND l_shipinstruct = 'DELIVER IN PERSON'
        )
    )
