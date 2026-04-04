DROP TABLE IF EXISTS shapley_results;

CREATE TABLE shapley_results (
    shapley_tuple JSONB
);

DO $$
DECLARE
    row_record RECORD;
    result TEXT; -- Define a variable to hold the tuple as a string
BEGIN
    FOR row_record IN
        SELECT provsql.provenance() AS provs FROM
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
            AND l_partkey % 64 = 0
        GROUP BY
            c_custkey,
            c_name,
            c_acctbal,
            c_phone,
            n_name,
            c_address,
            c_comment
    LOOP
        FOR result IN
            SELECT CONCAT(row_record.provs::text,',',provsql.shapley_all_vars(row_record.provs)::text)
        LOOP
            INSERT INTO shapley_results(shapley_tuple)
            VALUES (to_jsonb(result));

        END LOOP;
    END LOOP;
END $$;

\COPY shapley_results TO '/home/senellar/git/students/pratik/prob_data_shap/experiments/results/10.csv' WITH CSV HEADER;
