"""Fetch free CC0 models from Poly Haven (glTF, 1k or 2k textures) into <models folder>/<id>/, only when he asks for a
new object and says yes to the download.   python get_model.py <models folder> <id> [<id> ...]"""
import json, sys, os, urllib.request
root = sys.argv[1]
def get(url, path):
    if os.path.exists(path): return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'BernardStudio/1'})
    with urllib.request.urlopen(req, timeout=120) as r, open(path, 'wb') as f: f.write(r.read())
for aid in sys.argv[2:]:
  try:
    req = urllib.request.Request(f'https://api.polyhaven.com/files/{aid}', headers={'User-Agent': 'BernardStudio/1'})
    files = json.load(urllib.request.urlopen(req, timeout=60))
    g = files['gltf']; res = '1k' if '1k' in g else ('2k' if '2k' in g else sorted(g)[0])
    e = g[res]['gltf']; d = os.path.join(root, aid)
    get(e['url'], os.path.join(d, os.path.basename(e['url'])))
    for rel, inc in e.get('include', {}).items(): get(inc['url'], os.path.join(d, rel))
    print(aid, res, 'ok', flush=True)
  except Exception as ex: print(aid, 'FAILED', ex, flush=True)
