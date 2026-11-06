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

## Administrative boundaries

`korea_adm1.geojson` and `korea_adm2.geojson` come from **one** SGIS-derived source:
`vuski/admdongkor`, `ver20261001/HangJeongDong_ver20261001.geojson`.
Input Git blob: `877acdc676ee332414cd0d6dd0a2b143dbfbd7d7` (34,652,038 bytes).
Source: https://github.com/vuski/admdongkor/blob/master/ver20261001/HangJeongDong_ver20261001.geojson

This snapshot has 3,559 administrative dong features, 256 municipal units (including city wards),
and 16 province-level units. In this particular source, 전남/광주 are grouped under code `12`
(전남광주통합특별시). Names and parent codes are preserved from the source; this is a pinned
**2026-10-01 snapshot**, not a live authoritative legal boundary service. News location strings
are independent and are never renamed by the frontend.

The build tool dissolves dong polygons by their supplied `sgg` code, simplifies shared topology
at 5% with keep-shapes and cleaning, then dissolves the **same simplified districts** by `sido`.
Thus province lines and district lines share geometry. Coordinates are rounded to five decimal
places. Native land fill also uses the same province geometry, avoiding conflicting coastlines.
Small slivers and simplification intersections are cleaned; use these display assets for visual
exploration, not surveying or exact incident locations.

License and attribution (also available in the app information dialog):

본 데이터는 통계청 통계지리정보서비스(SGIS, https://sgis.kostat.go.kr)에서
공공누리 제1유형으로 개방한 행정동 경계를 가공한 것이며(가공: vuski/admdongkor,
https://github.com/vuski/admdongkor), CC BY 4.0으로 배포됩니다.
추가 가공: MapNews 표시용 단순화, 시·군·구/시·도 통합, 필드 축소 및 좌표 반올림.

- Upstream license preserved verbatim: [BOUNDARY_LICENSE.txt](BOUNDARY_LICENSE.txt)
- https://creativecommons.org/licenses/by/4.0/
- https://www.kogl.or.kr/info/licenseType1.do

Reproduce with the pinned input file (downloads are development-time only):

```bash
npm install --prefix .runtime/maptools mapshaper@0.6.113
python frontend/tools/build_boundaries.py INPUT.geojson --mapshaper .runtime/maptools/node_modules/.bin/mapshaper
```

`build_boundaries.py` checks the input Git blob hash before processing. Node/mapshaper are NOT
runtime dependencies. Both native Qt and Folium use the same bundled output. The Folium page
embeds gzip/base64 geometry and expands it in Chromium to stay below Qt's 2 MiB setHtml URL
limit. No boundary network request is made. Province lines remain visible; district lines appear
at native scale >= 2.4 or Leaflet zoom >= 9. OSM tile attribution remains visible in Leaflet.
