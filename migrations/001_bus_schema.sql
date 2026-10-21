-- Run this file once against the Tareeqi PostgreSQL database.
-- Requires PostGIS. Existing legacy tables are intentionally not dropped.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS public.bus (
    "uniqueID" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    color VARCHAR(30),
    "oldPrice" NUMERIC(10, 2),
    "newPrice" NUMERIC(10, 2),
    "isActive" BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS public.bus_route (
    "uniqueID" BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "busID" BIGINT NOT NULL
        REFERENCES public.bus ("uniqueID") ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    "lineString" geometry(LineString, 4326) NOT NULL,
    distance NUMERIC(12, 2),
    "tripTime" INTEGER,
    direction VARCHAR(50) NOT NULL,
    "startPoint" geometry(Point, 4326),
    "endPoint" geometry(Point, 4326),
    "isActive" BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_bus_route_version UNIQUE ("busID", direction, version),
    CONSTRAINT ck_bus_route_version_positive CHECK (version >= 1),
    CONSTRAINT ck_bus_route_trip_time_nonnegative CHECK ("tripTime" IS NULL OR "tripTime" >= 0),
    CONSTRAINT ck_bus_route_distance_nonnegative CHECK (distance IS NULL OR distance >= 0)
);

CREATE INDEX IF NOT EXISTS ix_bus_route_bus_id
    ON public.bus_route ("busID");

CREATE INDEX IF NOT EXISTS ix_bus_route_active
    ON public.bus_route ("busID", direction, version DESC)
    WHERE "isActive" = TRUE;

CREATE OR REPLACE FUNCTION public.set_bus_route_version()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    latest_version INTEGER;
    latest_geometry geometry(LineString, 4326);
BEGIN
    -- Serialize inserts for this bus and direction.
    PERFORM pg_advisory_xact_lock(
        hashtextextended(NEW."busID"::text || ':' || NEW.direction, 0)
    );

    SELECT br.version, br."lineString"
      INTO latest_version, latest_geometry
      FROM public.bus_route AS br
     WHERE br."busID" = NEW."busID"
       AND br.direction = NEW.direction
     ORDER BY br.version DESC
     LIMIT 1;

    IF NOT FOUND THEN
        NEW.version := 1;
        RETURN NEW;
    END IF;

    IF ST_AsEWKB(NEW."lineString") = ST_AsEWKB(latest_geometry) THEN
        RAISE EXCEPTION
            'LineString unchanged for bus % and direction %; update the existing version instead',
            NEW."busID", NEW.direction
            USING ERRCODE = '23505';
    END IF;

    NEW.version := latest_version + 1;

    -- An inactive draft must not deactivate the currently published version.
    IF NEW."isActive" THEN
        UPDATE public.bus_route
           SET "isActive" = FALSE
         WHERE "busID" = NEW."busID"
           AND direction = NEW.direction
           AND "isActive" = TRUE;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_set_bus_route_version ON public.bus_route;

CREATE TRIGGER trg_set_bus_route_version
BEFORE INSERT ON public.bus_route
FOR EACH ROW
EXECUTE FUNCTION public.set_bus_route_version();
