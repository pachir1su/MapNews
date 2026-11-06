# Local map data

`east_asia.geojson` contains KOR, PRK, JPN and CHN geometries extracted from Natural Earth
1:50 million admin-0 countries. All original geometry coordinates are preserved; properties
are reduced to `name` and `code`. Original source:
https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_50m_admin_0_countries.geojson

Natural Earth raster/vector data are public domain; electronic redistribution and modification
are permitted: https://www.naturalearthdata.com/about/terms-of-use/

This is a low-resolution geographical overview, not a road map, a legal boundary reference,
or an indication of an article's exact incident location. The native canvas uses an
equirectangular projection with longitude scale adjusted at 36 degrees N. Marker coordinates
are independent of this polygon dataset. No tiles, geocoding, API or CDN are requested by
the offline canvas.

`dummy_news.json` is a verbatim snapshot from MapNews PR #2, commit
`db6050c6329a88c477598f352ed3fba89d3c6f75`, path `data_ai/dummy_news.json`.
Its Git blob SHA is `468f1c60da200e631a2ed74415a7cc735039a563`.
`demo_coordinates.json` contains approximate representative coordinates chosen only for the
fictional demonstration. These are NOT verified incident coordinates or geocoding results.
The five original category names and article fields are unchanged.
