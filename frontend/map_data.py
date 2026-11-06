"""Read the bundled outline defensively; a damaged basemap must not break the GUI."""
import json
from pathlib import Path
from .models import coordinate

MAP_PATH = Path(__file__).parent / 'resources' / 'east_asia.geojson'


def load_outlines(path: Path | None = None):
    """Return validated outlines and an optional user-facing warning."""
    try:
        with (path or MAP_PATH).open('rb') as stream:
            data = stream.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError('Outline too large')
        raw = json.loads(data)
        if raw.get('type') != 'FeatureCollection' or not isinstance(raw.get('features'), list):
            raise ValueError('Invalid FeatureCollection')
        features = []
        for feature in raw['features']:
            geometry = feature['geometry']
            if geometry['type'] not in ('Polygon', 'MultiPolygon'):
                raise ValueError('Expected polygons')
            polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
            if not polygons:
                raise ValueError('Empty polygon')
            for polygon in polygons:
                if not polygon:
                    raise ValueError('Empty polygon')
                for ring in polygon:
                    if len(ring) < 4:
                        raise ValueError('Invalid ring')
                    for point in ring:
                        if (len(point) != 2 or any(isinstance(v, (bool, str)) for v in point)
                                or coordinate(point[0], 180) is None or coordinate(point[1], 90) is None):
                            raise ValueError('Invalid coordinate')
            features.append({'code': feature.get('properties', {}).get('code', ''), 'polygons': polygons})
        if not features:
            raise ValueError('No outlines')
        return features, ''
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        return [], '지형 자원을 읽지 못했습니다. 좌표 격자에서 뉴스를 계속 탐색할 수 있습니다.'
