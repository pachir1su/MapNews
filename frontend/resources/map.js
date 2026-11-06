// This file is inserted after Folium initializes the map and cluster.
(function () {
    "use strict";
    const map = __MAP__;
    const cluster = __CLUSTER__;
    const markers = new Map();
    let bridge = null;
    let selected = null;
    let tileErrors = 0;
    window.mapReady = false;

    window.setNews = function (rows) {
        map.closePopup();
        cluster.clearLayers();
        markers.clear();
        rows.forEach(function (row) {
            const pin = document.createElement("div");
            pin.className = "news-pin";
            pin.style.backgroundColor = row.color;
            pin.textContent = row.category.slice(0, 1);
            // Leaflet DOM nodes/textContent keep all news strings out of HTML parsing.
            const card = document.createElement("div");
            const title = document.createElement("strong");
            title.textContent = row.title;
            const location = document.createElement("p");
            location.textContent = row.category + " · " + row.location;
            card.append(title, location);
            const marker = L.marker([row.latitude, row.longitude], {
                icon: L.divIcon({html: pin, className: "", iconSize: [26, 26]}),
                title: row.title, keyboard: true
            }).bindPopup(card);
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
            cluster.zoomToShowLayer(marker, function () {
                if (markers.get(selected) !== marker) return;
                marker.openPopup();
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
    };
    window.mapHome = function () { map.setView([36.0, 127.6], 7); };
    window.fitNews = function () {
        if (markers.size) {
            const bounds = L.latLngBounds(Array.from(markers.values()).map(marker => marker.getLatLng()));
            map.fitBounds(bounds, {padding: [35, 35], maxZoom: 12});
        }
    };
    window.mapZoom = function (delta) { map.setZoom(map.getZoom() + delta); };
    map.eachLayer(function (layer) {
        if (layer instanceof L.TileLayer) {
            layer.on("tileerror", function () {
                if (++tileErrors === 4 && bridge) bridge.mapFailed("지도 타일을 불러오지 못했습니다.");
            });
            layer.on("tileload", function () { tileErrors = 0; });
        }
    });
    new QWebChannel(qt.webChannelTransport, function (channel) {
        bridge = channel.objects.newsBridge;
        window.mapReady = true;
        bridge.ready();
    });
})();
