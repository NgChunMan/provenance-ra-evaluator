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
        SELECT provsql.provenance() as provs FROM
        customer,
        orders,
        lineitem
        where
            c_mktsegment = 'BUILDING'
            and c_custkey = o_custkey
            and l_orderkey = o_orderkey
            and o_orderdate < date '1995-03-15'
            and l_shipdate > date '1995-03-15'
        group by
            l_orderkey,
            o_orderdate,
            o_shippriority
    LOOP
        FOR result IN
            SELECT CONCAT(row_record.provs::text,',',provsql.shapley_all_vars(row_record.provs)::text)
        LOOP
            INSERT INTO shapley_results(shapley_tuple)
            VALUES (to_jsonb(result));

        END LOOP;
    END LOOP;
END $$;

\COPY shapley_results TO '/home/senellar/git/students/pratik/prob_data_shap/experiments/results/3.csv' WITH CSV HEADER;
