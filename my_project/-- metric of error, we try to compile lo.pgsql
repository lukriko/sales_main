with cte_base as (
    select *
    from sales_main_web
    where
    to_char("CD", 'YYYY-MM') in ('2026-02', '2025-02') 
    and "UN" not in ('მთავარი საწყობი 2')
),

max_year as (select max(extract(year from "CD"))::int as yr from cte_base),
cte_2026 as (
    select * from cte_base 
    where extract(year from "CD") = (select yr from max_year)
),
cte_2025 as (
    select * from cte_base 
    where extract(year from "CD") = (select yr from max_year) - 1
),

cte_base_new as (
    select
        "UN",
        (sum("Tanxa") filter (where "ProdG" = 'SKIN CARE') /
         nullif(sum("Tanxa") filter (where "ProdG" <> 'POP'), 0))::numeric as skincare_pct,

        1 - (count(distinct "Zedd") filter (where left("Gvari", 13) = 'ფიზიკური პირი')
             / nullif(count(distinct "Zedd")::numeric, 0)) as client_identification,

        sum("Tanxa")                    as total_turnover,
        count(distinct "Zedd")::numeric as total_tickets,

        (select count(*) from (
            select "Zedd" from cte_2026 cb2
            where cb2."UN" = cb."UN" and cb2."ProdG" <> 'POP'
            group by "Zedd" having count(*) >= 3
        ) x)::numeric
        /
        nullif((select count(*) from (
            select distinct "Zedd" from cte_2026 cb2
            where cb2."UN" = cb."UN" and cb2."ProdG" <> 'POP'
        ) x), 0) as cross_selling_pct,

        (select count(*) from (
            select "Zedd" from cte_2026 cb2
            where cb2."UN" = cb."UN" and cb2."ProdG" <> 'POP'
            group by "Zedd" having count(*) = 1
        ) x)::numeric
        /
        nullif((select count(*) from (
            select distinct "Zedd" from cte_2026 cb2
            where cb2."UN" = cb."UN" and cb2."ProdG" <> 'POP'
        ) x), 0) as single_pct

    from cte_2026 cb
    group by "UN"
),

cte_base_past as (
    select
        "UN",
        (sum("Tanxa") filter (where "ProdG" = 'SKIN CARE') /
         nullif(sum("Tanxa") filter (where "ProdG" <> 'POP'), 0))::numeric as skincare_pct,

        1 - (count(distinct "Zedd") filter (where left("Gvari", 13) = 'ფიზიკური პირი')
             / nullif(count(distinct "Zedd")::numeric, 0)) as client_identification,

        sum("Tanxa")                    as total_turnover,
        count(distinct "Zedd")::numeric as total_tickets,

        (select count(*) from (
            select "Zedd" from cte_2025 cb2
            where cb2."UN" = cb."UN" and cb2."ProdG" <> 'POP'
            group by "Zedd" having count(*) >= 3
        ) x)::numeric
        /
        nullif((select count(*) from (
            select distinct "Zedd" from cte_2025 cb2
            where cb2."UN" = cb."UN" and cb2."ProdG" <> 'POP'
        ) x), 0) as cross_selling_pct,

        (select count(*) from (
            select "Zedd" from cte_2025 cb2
            where cb2."UN" = cb."UN" and cb2."ProdG" <> 'POP'
            group by "Zedd" having count(*) = 1
        ) x)::numeric
        /
        nullif((select count(*) from (
            select distinct "Zedd" from cte_2025 cb2
            where cb2."UN" = cb."UN" and cb2."ProdG" <> 'POP'
        ) x), 0) as single_pct

    from cte_2025 cb
    group by "UN"
),

change_cte as (
    select
        c1."UN",
        (c1.skincare_pct          - c2.skincare_pct)          / nullif(c2.skincare_pct, 0)          as skincare_pct_change,
        (c1.client_identification - c2.client_identification) / nullif(c2.client_identification, 0) as client_identification_change,
        (c1.total_turnover        - c2.total_turnover)        / nullif(c2.total_turnover, 0)        as total_turnover_change,
        (c1.total_tickets         - c2.total_tickets)         / nullif(c2.total_tickets, 0)         as total_tickets_change,
        (c1.cross_selling_pct     - c2.cross_selling_pct)     / nullif(c2.cross_selling_pct, 0)     as cross_selling_pct_change,
        (c1.single_pct            - c2.single_pct)            / nullif(c2.single_pct, 0)            as single_pct_change,

        -- ── carry forward raw 2026 levels for level scoring ──
        c1.skincare_pct          as skincare_pct_level,
        c1.client_identification as client_identification_level,
        c1.cross_selling_pct     as cross_selling_pct_level,
        c1.single_pct            as single_pct_level

    from cte_base_new  c1
    join cte_base_past c2 on c1."UN" = c2."UN"
),

minmax_cte as (
    select
        "UN",

        -- ── change scaled (60% weight total) ──
        (skincare_pct_change          - min(skincare_pct_change)          over()) / nullif(max(skincare_pct_change)          over() - min(skincare_pct_change)          over(), 0) as skincare_change_scaled,
        (client_identification_change - min(client_identification_change) over()) / nullif(max(client_identification_change) over() - min(client_identification_change) over(), 0) as client_identification_change_scaled,
        (total_turnover_change        - min(total_turnover_change)        over()) / nullif(max(total_turnover_change)        over() - min(total_turnover_change)        over(), 0) as turnover_change_scaled,
        (total_tickets_change         - min(total_tickets_change)         over()) / nullif(max(total_tickets_change)         over() - min(total_tickets_change)         over(), 0) as tickets_change_scaled,
        (cross_selling_pct_change     - min(cross_selling_pct_change)     over()) / nullif(max(cross_selling_pct_change)     over() - min(cross_selling_pct_change)     over(), 0) as cross_selling_change_scaled,
        (single_pct_change            - min(single_pct_change)            over()) / nullif(max(single_pct_change)            over() - min(single_pct_change)            over(), 0) as single_change_scaled,

        -- ── level scaled (40% weight total) ──
        (skincare_pct_level          - min(skincare_pct_level)          over()) / nullif(max(skincare_pct_level)          over() - min(skincare_pct_level)          over(), 0) as skincare_level_scaled,
        (client_identification_level - min(client_identification_level) over()) / nullif(max(client_identification_level) over() - min(client_identification_level) over(), 0) as client_identification_level_scaled,
        (cross_selling_pct_level     - min(cross_selling_pct_level)     over()) / nullif(max(cross_selling_pct_level)     over() - min(cross_selling_pct_level)     over(), 0) as cross_selling_level_scaled,
        (single_pct_level            - min(single_pct_level)            over()) / nullif(max(single_pct_level)            over() - min(single_pct_level)            over(), 0) as single_level_scaled

    from change_cte
)

select
    "UN",

    round((
        -- ── change component (60%) ──
        -- weights mirror your original, scaled down to 60%
        skincare_change_scaled              * (0.20 * 0.70) +
        client_identification_change_scaled * (0.15 * 0.70) +
        turnover_change_scaled              * (0.30 * 0.70) +
        tickets_change_scaled               * (0.15 * 0.70) +
        cross_selling_change_scaled         * (0.10 * 0.70) +
        (1 - single_change_scaled)          * (0.10 * 0.70) +

        -- ── level component (40%), split evenly across 4 metrics ──
        skincare_level_scaled               * (0.25 * 0.30) +
        client_identification_level_scaled  * (0.25 * 0.30) +
        cross_selling_level_scaled          * (0.25 * 0.30) +
        (1 - single_level_scaled)           * (0.25 * 0.30)   -- lower single is better
    )::numeric, 2) as main,

    -- ── ranks unchanged ──
    rank() over(order by skincare_change_scaled desc)              as rank_skincare,
    rank() over(order by client_identification_change_scaled desc) as rank_client_identification,
    rank() over(order by turnover_change_scaled desc)              as rank_turnover,
    rank() over(order by tickets_change_scaled desc)               as rank_tickets,
    rank() over(order by cross_selling_change_scaled desc)         as rank_cross_selling,
    rank() over(order by single_change_scaled desc)                 as rank_single,
    rank() over(order by skincare_level_scaled desc)                 as skincare_level_scaled,
    rank() over(order by client_identification_level_scaled desc)                 as client_identification_level_scaled,
    rank() over(order by cross_selling_level_scaled desc)                 as cross_selling_level_scaled

from minmax_cte
order by main desc;