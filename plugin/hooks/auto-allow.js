// Bernard Studio's PreToolUse hook. Runs with the Mac's own JavaScript (osascript -l JavaScript), no other tools.
//
// It answers "allow" (no permission question) only for the studio's own routine steps:
//   Bash   one `studio <command> ...` call on its own, made only of plain words (see words() below), with options
//          the studio knows. Never for `studio install ...` (installs need his yes) or for a call that carries a web
//          link (downloads need his yes). `studio open file "<path>"` only for a folder or a picture, video, text or
//          PDF file inside his studio folder or the plugin's examples (the examples page too), never an app, a script
//          or a bundle. The studio checks the same again before it opens anything (browse.safe_to_open); both read
//          the rules from hooks/open-rules.json. A plain `open` always asks him.
//   Read   inside the plugin folder or his studio folder. Glob only with a path there and a plain relative pattern.
//   Write and Edit  inside his studio folder only.
// Everything else prints nothing, so Claude Code asks him as usual. It never denies.
//
// His studio folder is $STUDIO_USER, or ~/Movies/Bernard Studio when that is not set (the same rule as bin/studio).
// The plugin folder is $CLAUDE_PLUGIN_ROOT, which Claude Code sets for plugin hooks.

ObjC.import('Foundation');
ObjC.import('AppKit');

var STUDIO_COMMANDS = ['new', 'projects', 'ingest', 'passage', 'fix-word', 'voice', 'matte', 'matte-photo', 'render',
  'qa', 'finish', 'note', 'lines', 'styles', 'gallery', 'sounds', 'brand', 'doctor', 'needs', 'transcript', 'frame', 'open',
  'list', 'help'];
var STUDIO_OPTIONS = ['--json', '--kind', '--link', '--no-scan', '--source', '--from', '--to', '--t0', '--t1', '--gap',
  '--at', '--all', '--method', '--fps', '--frames', '--cutouts', '--name', '--cut-y', '--grade', '--spec', '--version',
  '--notes', '--no-qa', '--anyway', '--add', '--find'];

function env(name) {
  var v = $.NSProcessInfo.processInfo.environment.objectForKey(name);
  return (v && !v.isNil()) ? v.js : '';
}

function readStdin() {
  var d = $.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile;
  var s = $.NSString.alloc.initWithDataEncoding(d, $.NSUTF8StringEncoding);
  return (s && !s.isNil()) ? s.js : '';
}

function exists(p) { return $.NSFileManager.defaultManager.fileExistsAtPath(p); }

// An absolute path with every symlink resolved, also for a file that does not exist yet (its nearest existing folder is
// resolved). Returns '' for anything unclear: a path that is not absolute, a ".." part, a part that starts with ~ (the
// tools and the shell may expand it to another place), an empty path.
function realPath(p) {
  if (!p || p.charAt(0) !== '/') return '';
  var parts = p.split('/');
  for (var i = 0; i < parts.length; i++) if (parts[i] === '..' || parts[i].charAt(0) === '~') return '';
  var head = p.replace(/\/+$/, '') || '/', tail = '';
  while (head !== '/' && !exists(head)) {
    var k = head.lastIndexOf('/');
    tail = head.slice(k) + tail;
    head = head.slice(0, k) || '/';
  }
  var resolved = $(head).stringByResolvingSymlinksInPath.js;
  return (resolved === '/' ? '' : resolved) + tail;
}

// The two roots come from our own environment, where a leading ~ means his home folder.
function rootPath(p) {
  if (p === '~' || p.indexOf('~/') === 0) p = env('HOME') + p.slice(1);
  return realPath(p);
}

function isDir(p) {
  var flag = Ref();
  return $.NSFileManager.defaultManager.fileExistsAtPathIsDirectory(p, flag) && flag[0];
}

// The open rules shared with the studio (hooks/open-rules.json). Missing or broken: nothing is opened without a question.
function openRules(pluginRoot) {
  if (!pluginRoot) return null;
  var s = $.NSString.stringWithContentsOfFileEncodingError(pluginRoot + '/hooks/open-rules.json', $.NSUTF8StringEncoding,
    null);
  if (!s || s.isNil()) return null;
  return JSON.parse(s.js);
}

function inside(path, root) {
  if (!path || !root) return false;
  return path === root || path.indexOf(root + '/') === 0;
}

// Splits a shell command into words, for plain commands only, and returns null for anything a shell (bash or zsh)
// could expand or treat specially. A strict whitelist, so the words seen here are exactly the words the shell passes:
//   outside quotes   only letters, digits, . _ / : , @ % + = - and spaces (a word may not start with =, which zsh
//                    expands); anything else, such as ( ) { } [ ] * ? ~ ! # ^ ; & | < > $ ` \ or a newline, is refused
//   "double quotes"  anything except $ ` \ ! and newlines
//   'single quotes'  anything except newlines (the shell takes it literally)
var PLAIN = /^[A-Za-z0-9._\/:,@%+=-]$/;
function words(cmd) {
  if (/[\n\r\0]/.test(cmd)) return null;
  var out = [], cur = '', inWord = false, fresh = true, i = 0, c, j;
  while (i < cmd.length) {
    c = cmd.charAt(i);
    if (c === ' ' || c === '\t') {
      if (inWord) { out.push(cur); cur = ''; inWord = false; }
      fresh = true; i++;
    } else if (c === "'") {
      j = cmd.indexOf("'", i + 1);
      if (j < 0) return null;
      cur += cmd.slice(i + 1, j); inWord = true; fresh = false; i = j + 1;
    } else if (c === '"') {
      j = cmd.indexOf('"', i + 1);
      if (j < 0) return null;
      var inner = cmd.slice(i + 1, j);
      if (/[$`\\!]/.test(inner)) return null;
      cur += inner; inWord = true; fresh = false; i = j + 1;
    } else if (PLAIN.test(c)) {
      if (fresh && c === '=') return null;
      cur += c; inWord = true; fresh = false; i++;
    } else {
      return null;
    }
  }
  if (inWord) out.push(cur);
  return out;
}

function looksLikeLink(w) {
  return /:\/\//.test(w) || /^(https?|ftp):/i.test(w) || /^www\./i.test(w)
    || /^[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}\//i.test(w);
}

function studioAllowed(w) {
  if (w[0] !== 'studio') return false;
  if (w.length === 1 || (w.length === 2 && (w[1] === '--help' || w[1] === '-h'))) return true;
  if (STUDIO_COMMANDS.indexOf(w[1]) < 0) return false;
  for (var i = 2; i < w.length; i++) {
    if (looksLikeLink(w[i])) return false;
    // open and list name places by word (drop, project "<name>"), never by path (studio open file is judged below)
    if ((w[1] === 'open' || w[1] === 'list') && w[2] !== 'file' && (/\.\./.test(w[i]) || /^[\/~]/.test(w[i]))) {
      return false;
    }
    if (w[i].charAt(0) === '-' && STUDIO_OPTIONS.indexOf(w[i]) < 0 && !/^-[0-9.]+$/.test(w[i])) return false;
  }
  return true;
}

// `studio open file <one path>`: his studio folder, one of its four folders, anything inside a project, or the
// examples; folders never a bundle (an app, a package, a script); files only the types in open-rules.json.
function openFileAllowed(w, userRoot, pluginRoot) {
  if (w[1] !== 'open' || w[2] !== 'file') return true;           // not an open file call: nothing more to check
  if (w.length !== 4 || w[3].charAt(0) === '-') return false;
  var rules = openRules(pluginRoot);
  var p = realPath(w[3]);
  if (!rules || !p || !exists(p) || !userRoot) return false;
  var examples = pluginRoot ? pluginRoot + '/examples' : '';
  var projects = userRoot + '/Projects';
  if (!inside(p, userRoot) && !inside(p, examples)) return false;
  var ext = (p.match(/\.([A-Za-z0-9]+)$/) || ['', ''])[1].toLowerCase();
  if (isDir(p)) {
    var own = p === userRoot || rules.studio_folders.some(function (f) { return p === userRoot + '/' + f; });
    if (!own && !inside(p, projects) && !inside(p, examples)) return false;
    if (rules.bundle_types.indexOf(ext) >= 0 || exists(p + '/Contents/Info.plist')) return false;
    return !$.NSWorkspace.sharedWorkspace.isFilePackageAtPath(p);
  }
  if (rules.file_types.indexOf(ext) >= 0) return true;
  return rules.examples_only_types.indexOf(ext) >= 0 && inside(p, examples);
}

function decide(input) {
  var tool = input.tool_name, t = input.tool_input || {}, cwd = input.cwd || '';
  var userRoot = rootPath(env('STUDIO_USER') || (env('HOME') + '/Movies/Bernard Studio'));
  var pluginRoot = rootPath(env('CLAUDE_PLUGIN_ROOT'));
  if (tool === 'Bash') {
    var w = words(String(t.command || '').replace(/^[ \t]+|[ \t]+$/g, ''));
    if (!w) return null;
    if (studioAllowed(w) && openFileAllowed(w, userRoot, pluginRoot)) return 'a studio step';
    return null;
  }
  if (tool === 'Read') {
    var r = realPath(String(t.file_path || ''));
    if (inside(r, userRoot) || inside(r, pluginRoot)) return 'reads a studio file';
    return null;
  }
  if (tool === 'Glob') {
    var pat = String(t.pattern || '');
    if (!t.path || !pat || /[{}~\\]/.test(pat) || /(^|\/)\.\.(\/|$)/.test(pat) || pat.charAt(0) === '/') return null;
    var g = realPath(String(t.path));
    if (inside(g, userRoot) || inside(g, pluginRoot)) return 'lists studio files';
    return null;
  }
  if (tool === 'Write' || tool === 'Edit') {
    var f = realPath(String(t.file_path || ''));
    if (inside(f, userRoot) && f !== userRoot) return 'writes inside his studio folder';
    return null;
  }
  return null;
}

function run(argv) {
  try {
    var input = JSON.parse(readStdin());
    var why = decide(input);
    if (!why) return;
    return JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'allow',
      permissionDecisionReason: 'Bernard Studio: ' + why } });
  } catch (e) {
    return;
  }
}
