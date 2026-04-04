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
        SELECT provsql.provenance() AS provs FROM
        (
            SELECT
                n1.n_name AS supp_nation,
                n2.n_name AS cust_nation,
                extract(year from l_shipdate) AS l_year,
                l_extendedprice * (1 - l_discount) AS volume
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
                AND l_shipdate between date '1995-01-01' AND date '1996-12-31'
                AND l_partkey%64=0
        ) AS shipping
    group by
        supp_nation,
        cust_nation,
        l_year


    LOOP
        FOR result IN
            SELECT CONCAT(row_record.provs::text,',',provsql.shapley_all_vars(row_record.provs)::text)
        LOOP
            INSERT INTO shapley_results(shapley_tuple)
            VALUES (to_jsonb(result));

        END LOOP;
    END LOOP;
END $$;

\COPY shapley_results TO '/home/senellar/git/students/pratik/prob_data_shap/experiments/results/7.csv' WITH CSV HEADER;
