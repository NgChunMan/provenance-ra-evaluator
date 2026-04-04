DROP TABLE IF EXISTS shapley_results;

CREATE TABLE shapley_results (
    shapley_tuple JSONB
);

DO $$
DECLARE
    row_record RECORD;
    result TEXT;
BEGIN
    FOR row_record IN
        SELECT provsql.provenance() as provs from
            partsupp,
            part,
            supplier
        where
            p_partkey = ps_partkey
            and ps_suppkey = s_suppkey
            and p_brand <> 'Brand#45'
            and p_type not like 'MEDIUM POLISHED%'
            and p_size in (49, 14, 23, 45, 19, 3, 36, 9)
            and s_comment not like '%Customer%Complaints%'
            and p_partkey%64=0
        group by
            p_brand,
            p_type,
            p_size


    LOOP
        FOR result IN
            SELECT CONCAT(row_record.provs::text,',',provsql.shapley_all_vars(row_record.provs)::text)
        LOOP
            INSERT INTO shapley_results(shapley_tuple)
            VALUES (to_jsonb(result));

        END LOOP;
    END LOOP;
END $$;

\COPY shapley_results TO '/home/senellar/git/students/pratik/prob_data_shap/experiments/results/16.csv' WITH CSV HEADER;
