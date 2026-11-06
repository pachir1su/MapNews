"""Prepare local map assets; mapshaper is a build tool, never an app dependency.

npm install --prefix .runtime/maptools mapshaper@0.6.113
python frontend/tools/build_boundaries.py INPUT --mapshaper .runtime/maptools/node_modules/.bin/mapshaper
See resources/MAP_DATA.md for the pinned input and attribution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

SOURCE_BLOB = '877acdc676ee332414cd0d6dd0a2b143dbfbd7d7'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--mapshaper', default='mapshaper')
    args = parser.parse_args()
    data = args.source.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if blob != SOURCE_BLOB:
        raise ValueError('Unexpected source version; review provenance before updating the assets')
    with tempfile.TemporaryDirectory() as temporary:
        districts, provinces = (Path(temporary) / name for name in ('districts.json', 'provinces.json'))
        # Simplify shared arcs ONCE, then dissolve that same geometry into provinces.
        subprocess.run([args.mapshaper, '-i', str(args.source), '-clean', '-dissolve2', 'sgg',
            'copy-fields=sido,sidonm,sggnm', '-simplify', '5%', 'keep-shapes', '-clean',
            '-o', str(districts), 'format=geojson', 'precision=0.00001',
            '-dissolve2', 'sido', 'copy-fields=sidonm',
            '-each', 'label_point=[this.innerX,this.innerY]',
            '-o', str(provinces), 'format=geojson', 'precision=0.00001'], check=True)
        folder = Path(__file__).resolve().parents[1] / 'resources'
        for level, source in (('adm1', provinces), ('adm2', districts)):
            collection = json.loads(source.read_text(encoding='utf-8'))
            for row in collection['features']:
                prop = row['properties']
                if level == 'adm1':
                    row['properties'] = {'code': prop['sido'], 'name': prop['sidonm'],
                        'label_point': [round(v, 5) for v in prop['label_point']]}
                else:
                    row['properties'] = {'code': prop['sgg'], 'name': prop['sggnm'],
                                         'parent': prop['sido']}
            text = json.dumps(collection, ensure_ascii=False, separators=(',', ':'))
            (folder / f'korea_{level}.geojson').write_text(text, encoding='utf-8')
            print(level, len(collection['features']), len(text.encode()), 'bytes')


if __name__ == '__main__':
    main()
