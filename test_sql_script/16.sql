-- TPC-H Q16 (Parts/Supplier Relationship) — simplified for provenance-aware RA evaluation.
-- Original: GROUP BY p_brand, p_type, p_size → replaced with DISTINCT.
-- Removed: aggregate count(distinct ps_suppkey).
-- Kept: NOT LIKE, IN, <> operators.
-- p_partkey%64=0 kept as data reduction filter.

SELECT DISTINCT
    p_brand,
    p_type,
    p_size
FROM
    partsupp,
    part,
    supplier
WHERE
    p_partkey = ps_partkey
    AND ps_suppkey = s_suppkey
    AND p_brand <> 'Brand#45'
    AND p_type NOT LIKE 'MEDIUM POLISHED%'
    AND p_size IN (49, 14, 23, 45, 19, 3, 36, 9)
    AND s_comment NOT LIKE '%Customer%Complaints%'
    AND p_partkey%64 = 0
