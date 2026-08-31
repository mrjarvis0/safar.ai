# Data attribution — OpenTravelData (OPTD)

The files in this directory are derived from **OpenTravelData**:
https://github.com/opentraveldata/opentraveldata

- `optd_por_min.csv` — a filtered/compact subset (airports + cities that have an
  IATA code) derived from `optd_por_public.csv`. Columns kept: iata, name, lat,
  lon, country_code, country, timezone, page_rank, loc_type. Sorted by page_rank.
- `optd_airlines.csv` — the OPTD airlines table (unmodified).

**License:** OPTD-generated data is licensed under **Creative Commons Attribution
4.0 (CC-BY 4.0)**. OPTD itself aggregates from Geonames (CC-BY), Wikipedia, and
UN/LOCODE. Attribution is retained here per the license; see the upstream repo
for full provenance.

Used by `safar/data_optd.py` for offline, keyless city/airport → IATA resolution,
airline code → name, and a geo/country/timezone fallback.
