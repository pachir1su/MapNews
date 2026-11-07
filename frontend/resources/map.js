// This file is inserted after Folium initializes the map and cluster.
(async function () {
    "use strict";
    const map = __MAP__;
    const cluster = __CLUSTER__;
    const markers = new Map();
    const icons = __ICONS__;
    map.attributionControl.setPrefix(false);
    cluster.options.iconCreateFunction = function (group) {
        const count = document.createElement('span');
        count.textContent = String(group.getChildCount());
        return L.divIcon({html:count, className:'news-cluster', iconSize:[40,40]});
    };
    let bridge = null;
    let selected = null;
    let tileErrors = 0;
    let tileLoaded = false;
    let tileTimedOut = false;
    map.eachLayer(function (layer) {
        if (layer instanceof L.TileLayer) {
            const timeout = setTimeout(function () {
                if (!tileLoaded) {
                    tileTimedOut = true;
                    if (bridge) bridge.mapFailed('tiles');
                }
            }, 12000);
            layer.on("tileerror", function () {
                if (++tileErrors === 4 && bridge) bridge.mapFailed("지도 타일을 불러오지 못했습니다.");
            });
            layer.on("tileload", function () {
                tileErrors = 0;
                tileLoaded = true;
                clearTimeout(timeout);
            });
        }
    });
    window.mapReady = false;
    map.createPane('boundaries');
    map.getPane('boundaries').style.zIndex = 350;
    map.getPane('boundaries').style.pointerEvents = 'none';
    async function geometry(encoded) {
        const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
        const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
        return new Response(stream).json();
    }
    const [adm1, adm2] = await Promise.all([geometry('__ADM1__'), geometry('__ADM2__')]);
    const districts = L.geoJSON(adm2, {pane: 'boundaries', interactive: false,
        style: {color: '#8799ad', weight: 0.7, fill: false, opacity: 0.35, className: 'district-boundary'}});
    const provinces = L.geoJSON(adm1, {pane: 'boundaries', interactive: false,
        style: {color: '#64748b', weight: 1.0, fill: false, opacity: 0.45, className: 'province-boundary'}}).addTo(map);
    function updateBoundaries() {
        if (map.getZoom() >= 10) districts.addTo(map);
        else map.removeLayer(districts);
    }
    map.on('zoomend', updateBoundaries);
    updateBoundaries();

    window.setNews = function (rows) {
        map.closePopup();
        cluster.clearLayers();
        markers.clear();
        rows.forEach(function (row) {
            const pin = document.createElement("div");
            pin.className = "news-pin";
            pin.style.backgroundColor = row.color;
            const glyph = document.createElement('img');
            glyph.src = icons[row.icon] || icons['map-pin'];
            glyph.alt = row.category;
            pin.append(glyph);
            const marker = L.marker([row.latitude, row.longitude], {
                icon: L.divIcon({html: pin, className: "", iconSize: [34, 34]}),
                title: row.title, keyboard: true
            });
            marker.on("click", function () {
                if (bridge) bridge.selectNews(row.id);
            });
            cluster.addLayer(marker);
            markers.set(row.id, marker);
        });
        window.selectNews({id: selected, focus: false});
    };
    window.selectNews = function (value) {
        selected = value.id;
        markers.forEach(function (marker, id) {
            const el = marker.getElement();
            if (el) el.classList.toggle("news-selected", id === selected);
        });
        const marker = markers.get(selected);
        if (marker && value.focus) {
            map.stop();
            map.setView(marker.getLatLng(), Math.max(map.getZoom(), 11), {animate: false});
            cluster.zoomToShowLayer(marker, function () {
                if (markers.get(selected) !== marker) return;

                const el = marker.getElement();
                if (el) el.classList.add("news-selected");
            });
        }
    };
    cluster.on("animationend spiderfied", function () {
        window.selectNews({id: selected, focus: false});
    });
    window.setTheme = function (dark) {
        document.body.classList.toggle("map-dark", dark);
        provinces.setStyle({color: dark ? '#afc4df' : '#64748b'});
        districts.setStyle({color: dark ? '#8a9db5' : '#8799ad'});
    };
    window.mapHome = function () { map.setView([36.0, 127.6], 7); };
    window.fitNews = function () {
        if (markers.size) {
            const bounds = L.latLngBounds(Array.from(markers.values()).map(marker => marker.getLatLng()));
            map.fitBounds(bounds, {padding: [35, 35], maxZoom: 12});
        }
    };
    window.mapZoom = function (delta) { map.setZoom(map.getZoom() + delta); };
    new QWebChannel(qt.webChannelTransport, function (channel) {
        bridge = channel.objects.newsBridge;
        window.mapReady = true;
        bridge.ready();
        if (tileErrors >= 4 || tileTimedOut) bridge.mapFailed('tiles');
    });
})();
