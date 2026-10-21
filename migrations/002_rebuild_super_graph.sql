-- Rebuild the multimodal routing graph using the current bus / bus_route schema.
-- Assumes public.ways, public.ways_vertices_pgr, and public.super_graph already
-- exist with the columns used below by the existing routing setup.
-- Run after migrations/001_bus_schema.sql.

CREATE OR REPLACE FUNCTION public.rebuild_super_graph()
RETURNS void
LANGUAGE plpgsql
AS $BODY$
BEGIN
    -- Remove the previous graph before rebuilding it.
    TRUNCATE TABLE public.super_graph;

    -- Walking edges from the street network.
    INSERT INTO public.super_graph
        (source, target, cost, reverse_cost, edge_type, geom)
    SELECT
        w.source,
        w.target,
        w.length_m / 1.4,
        w.length_m / 1.4,
        'walk',
        w.geom
    FROM public.ways AS w;

    -- Generate points at <= 50 m spacing along every active bus route.
    -- Use bus_route.id as the route key so routes with identical names do not
    -- accidentally connect to each other.
    DROP TABLE IF EXISTS pg_temp.safe_bus_nodes;

    CREATE TEMP TABLE safe_bus_nodes ON COMMIT DROP AS
    WITH max_street_node AS (
        SELECT COALESCE(MAX(id), 0)::BIGINT AS safe_offset
        FROM public.ways_vertices_pgr
    ),
    route_points AS (
        SELECT
            br.id AS bus_route_id,
            (b.name || ' — ' || br.direction)::VARCHAR AS route_name,
            dp.path AS point_path,
            dp.geom AS geom
        FROM public.bus_route AS br
        JOIN public.bus AS b
          ON b.id = br.bus_id
        CROSS JOIN LATERAL ST_DumpPoints(
            ST_SetSRID(
                ST_Segmentize(br.line_string::geography, 50)::geometry,
                4326
            )
        ) AS dp
        WHERE br.is_active = TRUE
          AND b.is_active = TRUE
    )
    SELECT
        (SELECT safe_offset FROM max_street_node)
            + ROW_NUMBER() OVER (ORDER BY bus_route_id, point_path)::BIGINT AS node_id,
        bus_route_id,
        route_name,
        geom,
        ROW_NUMBER() OVER (
            PARTITION BY bus_route_id
            ORDER BY point_path
        )::BIGINT AS pt_idx
    FROM route_points;

    -- Directed bus edges between consecutive generated points.
    INSERT INTO public.super_graph
        (source, target, cost, reverse_cost, edge_type, route_name, geom)
    SELECT
        a.node_id,
        b.node_id,
        ST_Distance(a.geom::geography, b.geom::geography) / 5.5,
        -1,
        'bus',
        a.route_name,
        ST_SetSRID(ST_MakeLine(a.geom, b.geom), 4326)
    FROM safe_bus_nodes AS a
    JOIN safe_bus_nodes AS b
      ON b.bus_route_id = a.bus_route_id
     AND b.pt_idx = a.pt_idx + 1;

    -- Connect each generated bus node to its nearest street vertex within 500 m.
    -- The positive reverse_cost makes this transfer traversable in both ways.
    INSERT INTO public.super_graph
        (source, target, cost, reverse_cost, edge_type, route_name, geom)
    SELECT
        bn.node_id,
        street.id,
        (ST_Distance(bn.geom::geography, street.geom::geography) / 1.4) + 120,
        (ST_Distance(bn.geom::geography, street.geom::geography) / 1.4) + 120,
        'transfer',
        'Walk/Wait Transfer',
        ST_SetSRID(ST_MakeLine(bn.geom, street.geom), 4326)
    FROM safe_bus_nodes AS bn
    CROSS JOIN LATERAL (
        SELECT v.id, v.geom
        FROM public.ways_vertices_pgr AS v
        ORDER BY v.geom <-> bn.geom
        LIMIT 1
    ) AS street
    WHERE ST_DWithin(
        bn.geom::geography,
        street.geom::geography,
        500
    );

    DROP TABLE IF EXISTS pg_temp.safe_bus_nodes;
END;
$BODY$;

ALTER FUNCTION public.rebuild_super_graph() OWNER TO postgres;
