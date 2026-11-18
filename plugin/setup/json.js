// Small JSON helper for the setup scripts. Runs with the Mac's own JavaScript
// (osascript -l JavaScript), because a fresh Mac has no working python3.
//
//   osascript -l JavaScript json.js get <file> <dotted.path>     prints the value (strings raw, the rest as JSON)
//   osascript -l JavaScript json.js keys <file> <dotted.path>    prints the keys of an object, one per line
//   osascript -l JavaScript json.js items <file> <dotted.path>   prints the items of an array, one per line
//   osascript -l JavaScript json.js set <file> <dotted.path> <json value>   writes the value (makes the file and parents)
//   osascript -l JavaScript json.js delete <file> <dotted.path>
// A path that contains "/" is split on "/" instead, for keys that contain dots (pins/birefnet_hr/files/config.json).
// A missing file or path prints nothing and exits 1 for get, keys and items.

ObjC.import('Foundation');

function readJSON(path) {
  var s = $.NSString.stringWithContentsOfFileEncodingError(path, $.NSUTF8StringEncoding, null);
  if (!s || s.isNil()) return null;
  return JSON.parse(s.js);
}

function writeJSON(path, obj) {
  var text = JSON.stringify(obj, null, 2) + '\n';
  var ok = $(text).writeToFileAtomicallyEncodingError(path, true, $.NSUTF8StringEncoding, null);
  if (!ok) throw new Error('could not write ' + path);
}

function walk(obj, dotted) {
  if (!dotted) return obj;
  var parts = split(dotted);
  for (var i = 0; i < parts.length; i++) {
    if (obj === null || typeof obj !== 'object' || !(parts[i] in obj)) return undefined;
    obj = obj[parts[i]];
  }
  return obj;
}

function fail() { $.exit(1); }

function split(p) { return p.indexOf('/') >= 0 ? p.split('/') : p.split('.'); }

function run(argv) {
  var cmd = argv[0], file = argv[1], dotted = argv[2] || '';
  if (cmd === 'set' || cmd === 'delete') {
    var root = readJSON(file) || {};
    var parts = split(dotted);
    var obj = root;
    for (var i = 0; i < parts.length - 1; i++) {
      if (obj[parts[i]] === null || typeof obj[parts[i]] !== 'object') obj[parts[i]] = {};
      obj = obj[parts[i]];
    }
    if (cmd === 'set') obj[parts[parts.length - 1]] = JSON.parse(argv[3]);
    else delete obj[parts[parts.length - 1]];
    writeJSON(file, root);
    return '';
  }
  var data = readJSON(file);
  if (data === null) fail();
  var v = walk(data, dotted);
  if (v === undefined) fail();
  if (cmd === 'get') return typeof v === 'string' ? v : JSON.stringify(v);
  if (cmd === 'keys') return Object.keys(v).join('\n');
  if (cmd === 'items') return v.map(function (x) { return typeof x === 'string' ? x : JSON.stringify(x); }).join('\n');
  fail();
}
