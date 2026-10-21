-- BUS / BUS_ROUTE schema matching the actual PostgreSQL column names.
-- Run on a new database. Existing legacy tables are not dropped.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS public.bus (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    color VARCHAR(30),
    old_price NUMERIC(10, 2),
    new_price NUMERIC(10, 2),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS public.bus_route (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bus_id BIGINT NOT NULL REFERENCES public.bus (id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    line_string geometry(LineString, 4326) NOT NULL,
    distance NUMERIC(10, 2),
    trip_time INTEGER,
    direction VARCHAR(50) NOT NULL,
    start_point geometry(Point, 4326),
    end_point geometry(Point, 4326),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_bus_route_version UNIQUE (bus_id, direction, version),
    CONSTRAINT ck_bus_route_version_positive CHECK (version >= 1),
    CONSTRAINT ck_bus_route_trip_time_nonnegative CHECK (trip_time IS NULL OR trip_time >= 0),
    CONSTRAINT ck_bus_route_distance_nonnegative CHECK (distance IS NULL OR distance >= 0)
);

CREATE INDEX IF NOT EXISTS ix_bus_route_bus_id
    ON public.bus_route (bus_id);

CREATE INDEX IF NOT EXISTS ix_bus_route_active
    ON public.bus_route (bus_id, direction, version DESC)
    WHERE is_active = TRUE;

CREATE OR REPLACE FUNCTION public.set_bus_route_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    latest_version INTEGER;
    latest_line geometry(LineString, 4326);
BEGIN
    -- Serialize concurrent inserts for the same bus and direction.
    PERFORM pg_advisory_xact_lock(
        hashtextextended(NEW.bus_id::text || ':' || NEW.direction, 0)
    );

    SELECT br.version, br.line_string
      INTO latest_version, latest_line
      FROM public.bus_route AS br
     WHERE br.bus_id = NEW.bus_id
       AND br.direction = NEW.direction
     ORDER BY br.version DESC
     LIMIT 1;

    IF NOT FOUND THEN
        NEW.version := 1;
        RETURN NEW;
    END IF;

    IF ST_AsEWKB(NEW.line_string) = ST_AsEWKB(latest_line) THEN
        RAISE EXCEPTION
            'line_string unchanged for bus_id % and direction %; no new version created',
            NEW.bus_id, NEW.direction
            USING ERRCODE = '23505';
    END IF;

    NEW.version := latest_version + 1;

    -- Preserve the currently published version if this new row is inactive.
    IF NEW.is_active THEN
        UPDATE public.bus_route
           SET is_active = FALSE
         WHERE bus_id = NEW.bus_id
           AND direction = NEW.direction
           AND is_active = TRUE;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_set_bus_route_version ON public.bus_route;

CREATE TRIGGER trg_set_bus_route_version
BEFORE INSERT ON public.bus_route
FOR EACH ROW
EXECUTE FUNCTION public.set_bus_route_version();
