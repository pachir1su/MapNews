# Vendored map dependencies

- Leaflet **1.9.4** — BSD-2-Clause; see LEAFLET-LICENSE.
  CSS: https://github.com/Leaflet/Leaflet/blob/v1.9.4/dist/leaflet.css
  Built JS: https://github.com/cdnjs/cdnjs/blob/master/ajax/libs/leaflet/1.9.4/leaflet.js
- Leaflet.markercluster **1.5.3** — MIT; see MARKERCLUSTER-LICENSE.
  CSS: https://github.com/Leaflet/Leaflet.markercluster/tree/v1.5.3/dist
  Built JS: https://github.com/cdnjs/cdnjs/blob/master/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.js

Files are copied without modification. Versioned dependency files are committed,
so demo initialization does not fetch a CDN. Default marker/layer-control images
are unused (MapNews uses DOM DivIcons and no layer selector).
Native offline mode does not instantiate WebEngine or request map tiles.
Online mode requests OpenStreetMap tiles and retains visible attribution.
