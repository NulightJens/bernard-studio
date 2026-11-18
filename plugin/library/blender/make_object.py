"""Make a new object picture for The art of (only when he asks for an object the library does not have).
Blender studio product render: one glTF model (or a built-in phone, laptop or card mockup showing one of his own
screens) per spec, transparent film, soft key/fill/rim, Cycles shadow catcher for a soft contact shadow.
  blender -b -P make_object.py -- <specs.json> <models folder> <render folder> [only_id ...]
then  python finish_object.py <render folder> <project>/objects   (trims, adds the soft contact shadow and the box)
Models: free CC0 models from Poly Haven, fetched on demand with get_model.py into the models folder.
Spec: {"id": out name, "src": poly haven id | "mock:phone" | "mock:laptop" | "mock:cards" ...,
       "yaw": deg, "elev": deg camera elevation, "rot": [x,y,z] deg object rotation, "lens": mm,
       "screen": image path (mockups), "size": px, "samples": n}"""
import bpy, sys, json, math, os, mathutils
argv = sys.argv[sys.argv.index('--') + 1:]
specs = json.load(open(argv[0])); SRC, OUT = argv[1], argv[2]; only = set(argv[3:])
specs = specs.get('objects', specs) if isinstance(specs, dict) else specs
BASE = os.path.dirname(os.path.abspath(argv[0]))
for _s in specs:                    # screen pictures are given relative to the specs file
    if _s.get('screen') and not os.path.isabs(_s['screen']):
        _s['screen'] = os.path.join(BASE, _s['screen'])
    if _s.get('cards'):
        _s['cards'] = [c if os.path.isabs(c) else os.path.join(BASE, c) for c in _s['cards']]
os.makedirs(OUT, exist_ok=True)

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type = 'METAL'; prefs.get_devices()
        for d in prefs.devices: d.use = True
        sc.cycles.device = 'GPU'
    except Exception as e: print('gpu', e)
    sc.cycles.use_denoising = True; sc.render.film_transparent = True
    sc.view_settings.view_transform = 'AgX'
    try: sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception: pass
    sc.view_settings.exposure = 0.3
    return sc

def mat_img(name, path, emit=0.0, rough=0.25):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    b = nt.nodes['Principled BSDF']; t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(path)
    t.extension = 'CLIP'
    b.inputs['Roughness'].default_value = rough
    if emit:  # a lit screen: true colours come from emission only; the glass keeps its specular reflection
        b.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1)
        try: b.inputs['Specular IOR Level'].default_value = 0.08
        except Exception: pass
        b.inputs['Roughness'].default_value = 0.35
        nt.links.new(t.outputs['Color'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = emit
    else:
        nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    return m

def mat_col(name, rgb, rough=0.4, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if coat: b.inputs['Coat Weight'].default_value = coat
    return m

def rounded_slab(name, w, h, d, r, bevel_segments=12, edge=0.006):
    """A true rounded rectangle (corner radius r) extruded to thickness d, centred on z=0, small edge bevel."""
    import bmesh
    me = bpy.data.meshes.new(name); o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o)
    bm = bmesh.new(); r = min(r, w / 2 - 1e-4, h / 2 - 1e-4); pts = []
    for cx, cy, a0 in [(w/2-r, h/2-r, 0), (-w/2+r, h/2-r, 90), (-w/2+r, -h/2+r, 180), (w/2-r, -h/2+r, 270)]:
        for i in range(bevel_segments + 1):
            a = math.radians(a0 + 90 * i / bevel_segments); pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    bot = [bm.verts.new((x, y, -d / 2)) for x, y in pts]; top = [bm.verts.new((x, y, d / 2)) for x, y in pts]
    bm.faces.new(top); bm.faces.new(list(reversed(bot)))
    n = len(pts)
    for i in range(n): bm.faces.new((bot[i], bot[(i + 1) % n], top[(i + 1) % n], top[i]))
    bm.normal_update(); bm.to_mesh(me); bm.free()
    bpy.context.view_layer.objects.active = o; o.select_set(True)
    if edge > 0:
        mod = o.modifiers.new('bev', 'BEVEL'); mod.width = min(edge, d / 2.5); mod.segments = 3; mod.limit_method = 'ANGLE'; mod.angle_limit = math.radians(60)
    if hasattr(bpy.types, 'WeightedNormalModifier'): o.modifiers.new('ws', 'WEIGHTED_NORMAL')
    for f in me.polygons: f.use_smooth = False
    return o

def rounded_plane(name, w, h, r, img, z, emit=1.0, segs=12):
    """Rounded-corner screen plane with planar UVs."""
    import bmesh
    me = bpy.data.meshes.new(name); o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o)
    bm = bmesh.new(); r = min(r, w / 2 - 1e-4, h / 2 - 1e-4); pts = []
    for cx, cy, a0 in [(w/2-r, h/2-r, 0), (-w/2+r, h/2-r, 90), (-w/2+r, -h/2+r, 180), (w/2-r, -h/2+r, 270)]:
        for i in range(segs + 1):
            a = math.radians(a0 + 90 * i / segs); pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    vs = [bm.verts.new((x, y, 0)) for x, y in pts]; f = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new()
    for l in f.loops: l[uv].uv = (l.vert.co.x / w + 0.5, l.vert.co.y / h + 0.5)
    bm.to_mesh(me); bm.free(); o.location.z = z
    o.data.materials.append(mat_img(name + 'M', img, emit=emit, rough=0.08)); return o

def screen_plane(name, w, h, img, z, emit=1.0):
    bpy.ops.mesh.primitive_plane_add(size=1); p = bpy.context.object; p.name = name
    p.scale = (w, h, 1); bpy.ops.object.transform_apply(scale=True); p.location.z = z
    p.data.materials.append(mat_img(name + 'M', img, emit=emit, rough=0.08)); return p

def mock_phone(s):
    # modern phone, 71.5 x 147 x 8 mm, scaled x10; screen image fills the display
    body = rounded_slab('phone', 0.715, 1.47, 0.08, 0.11, edge=0.012)
    body.data.materials.append(mat_col('frame', (0.02, 0.02, 0.022), rough=0.25, metal=0.6))
    glass = rounded_slab('glass', 0.69, 1.445, 0.004, 0.10, edge=0.0); glass.location.z = 0.041
    glass.data.materials.append(mat_col('black', (0.003, 0.003, 0.003), rough=0.05, coat=1.0))
    scr = rounded_plane('screen', 0.655, 1.41, 0.085, s['screen'], 0.0435, emit=s.get('emit', 0.9))
    for o in (body, glass, scr): o.parent = None
    bpy.ops.object.select_all(action='DESELECT')
    for o in (body, glass, scr): o.select_set(True)
    bpy.context.view_layer.objects.active = body; bpy.ops.object.join()
    return bpy.context.object

def mock_laptop(s):
    W, D = 3.04, 2.15
    base = rounded_slab('base', W, D, 0.06, 0.05); base.location.z = 0.03
    alu = mat_col('alu', (0.52, 0.53, 0.55), rough=0.32, metal=1.0); base.data.materials.append(alu)
    kb = rounded_slab('kb', W * 0.9, D * 0.42, 0.004, 0.01); kb.location = (0, 0.18, 0.061)
    kb.data.materials.append(mat_col('keys', (0.006, 0.006, 0.007), rough=0.85))
    tp = rounded_slab('tp', W * 0.38, D * 0.27, 0.003, 0.02); tp.location = (0, -0.6, 0.061)
    tp.data.materials.append(mat_col('tp', (0.5, 0.51, 0.53), rough=0.3, metal=1.0))
    lid = rounded_slab('lid', W, D, 0.05, 0.05)
    lid.data.materials.append(alu)
    bez = rounded_slab('bez', W - 0.02, D - 0.02, 0.004, 0.045); bez.location.z = 0.026
    bez.data.materials.append(mat_col('bezel', (0.004, 0.004, 0.004), rough=0.08, coat=1.0))
    scr = screen_plane('screen', W - 0.14, D - 0.16, s['screen'], 0.0285, emit=s.get('emit', 0.9))
    for o in (bez, scr): o.parent = lid
    lid.rotation_euler.x = math.radians(90 - s.get('open', 22))
    # hinge pivot: move lid so its bottom edge sits at the base's back edge
    lid.location = (0, D / 2 + math.sin(math.radians(s.get('open', 22))) * D / 2, 0.06 + math.cos(math.radians(s.get('open', 22))) * D / 2)
    return [base, kb, tp, lid, bez, scr]

def mock_cards(s):
    # a fanned stack of printed cards (square templates), images = list
    objs = []
    for i, img in enumerate(s['cards']):
        c = rounded_slab(f'card{i}', 1.0, s.get('aspect', 1.0), 0.008, 0.012, 4)
        c.data.materials.append(mat_col('paper', (0.9, 0.9, 0.88), rough=0.7))
        p = screen_plane(f'print{i}', 0.998, s.get('aspect', 1.0) - 0.002, img, 0.0042, emit=s.get('print_emit', 0.85))
        p.parent = c
        dx, dy, rz = s['fan'][i]; c.location = (dx, dy, i * 0.01 + 0.004); c.rotation_euler.z = math.radians(rz)
        objs += [c, p]
    return objs

def import_ph(aid):
    d = os.path.join(SRC, aid); g = [f for f in os.listdir(d) if f.endswith('.gltf')][0]
    bpy.ops.import_scene.gltf(filepath=os.path.join(d, g))
    return [o for o in bpy.context.scene.objects if o.type == 'MESH']

def bounds(objs):
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ mathutils.Vector(c) for o in objs for c in o.bound_box]
    mn = mathutils.Vector([min(p[i] for p in pts) for i in range(3)]); mx = mathutils.Vector([max(p[i] for p in pts) for i in range(3)])
    return mn, mx

def render(s):
    sc = reset(); size = s.get('size', 1100)
    src = s['src']
    if src == 'mock:phone': objs = [mock_phone(s)]
    elif src == 'mock:laptop': objs = mock_laptop(s)
    elif src == 'mock:cards': objs = mock_cards(s)
    else: objs = import_ph(src)
    if s.get('only'):
        for o in objs:
            if not any(k in o.name for k in s['only']): o.hide_render = True
    for name in s.get('hide', []):
        for o in objs:
            if name in o.name: o.hide_render = True
    for o in objs:
        for sl in o.material_slots:
            m = sl.material
            if m and 'glass' in m.name.lower() and m.use_nodes:
                b = m.node_tree.nodes.get('Principled BSDF')
                if b:
                    for l in list(b.inputs['Alpha'].links): m.node_tree.links.remove(l)
                    for l in list(b.inputs['Base Color'].links): m.node_tree.links.remove(l)
                    b.inputs['Alpha'].default_value = 1.0; b.inputs['Base Color'].default_value = (1, 1, 1, 1)
                    b.inputs['Transmission Weight'].default_value = 1.0; b.inputs['Roughness'].default_value = 0.02
                    try: m.surface_render_method = 'DITHERED'
                    except Exception: pass
    for o in objs:
        for sl in o.material_slots:
            m = sl.material
            if m and 'flame' in m.name.lower() and m.use_nodes:
                nt = m.node_tree; b = nt.nodes.get('Principled BSDF')
                tex = [n for n in nt.nodes if n.type == 'TEX_IMAGE']
                if b and tex:
                    bw = nt.nodes.new('ShaderNodeRGBToBW'); nt.links.new(tex[0].outputs['Color'], bw.inputs['Color'])
                    nt.links.new(bw.outputs['Val'], b.inputs['Alpha'])
                    nt.links.new(tex[0].outputs['Color'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = 3.0
    if s.get('screen_mat') and s.get('screen'):
        for o in objs:
            for i, sl in enumerate(o.material_slots):
                if sl.material and s['screen_mat'] in sl.material.name: o.material_slots[i].material = mat_img('scr', s['screen'], emit=0.9, rough=0.1)
    # group under an empty and rotate
    bpy.ops.object.empty_add(); piv = bpy.context.object
    tops = [o for o in bpy.context.scene.objects if o.parent is None and o is not piv and o.type in ('MESH', 'EMPTY')]
    for o in tops: o.parent = piv
    piv.rotation_euler = [math.radians(a) for a in s.get('rot', [0, 0, 0])]
    piv.scale = [s.get('scale', 1)] * 3
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_render]
    mn, mx = bounds(meshes)
    piv.location -= mathutils.Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    mn, mx = bounds(meshes); ctr = (mn + mx) / 2; rad = (mx - mn).length / 2
    # floor shadow catcher
    bpy.ops.mesh.primitive_plane_add(size=rad * 40, location=(0, 0, mn.z)); fl = bpy.context.object
    fl.is_shadow_catcher = True
    # camera
    cam_d = bpy.data.cameras.new('cam'); cam_d.lens = s.get('lens', 85); cam = bpy.data.objects.new('cam', cam_d)
    sc.collection.objects.link(cam); sc.camera = cam
    yaw, el = math.radians(s.get('yaw', 0)), math.radians(s.get('elev', 15))
    fov = 2 * math.atan(18 / cam_d.lens); dist = rad / math.sin(fov / 2) * 1.02
    dirv = mathutils.Vector((math.sin(yaw) * math.cos(el), -math.cos(yaw) * math.cos(el), math.sin(el)))
    cam.location = ctr + dirv * dist
    cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam_d.clip_end = dist * 10
    # lights: big soft key upper-left-front, fill right, rim back, top
    def area(name, loc, energy, sz, col=(1, 1, 1)):
        L = bpy.data.lights.new(name, 'AREA'); L.size = sz; L.energy = energy; L.color = col
        o = bpy.data.objects.new(name, L); sc.collection.objects.link(o); o.location = loc
        o.rotation_euler = (ctr - mathutils.Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    k = s.get('light', 1.0) * (rad ** 2) * 60
    def at(az, elv, r):
        a, e = math.radians(az), math.radians(elv)
        rot = mathutils.Matrix.Rotation(yaw, 3, 'Z')
        v = rot @ mathutils.Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
        return tuple(ctr + v * r)
    area('key', at(-45, 50, rad * 4), k * 9, rad * 3.5)
    area('fill', at(60, 20, rad * 4), k * 3.5, rad * 4)
    area('rim', at(160, 35, rad * 4), k * 4.5, rad * 2.5)
    area('top', at(0, 88, rad * 4), k * 3.5, rad * 4)
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.78, 0.78, 0.78, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = s.get('world', 0.55)
    sc.render.resolution_x = sc.render.resolution_y = size; sc.render.resolution_percentage = 100
    sc.cycles.samples = s.get('samples', 96)
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    # pass A: object only (no floor)
    fl.hide_render = True
    sc.render.filepath = os.path.join(OUT, s['id'] + '.png')
    bpy.ops.render.render(write_still=True)
    if s.get('shadow') is False:
        print('RENDERED', s['id'], flush=True); return
    # pass B: shadow only (objects held out), cheaper
    fl.hide_render = False
    for o in meshes: o.is_holdout = True
    sc.cycles.samples = 12; sc.render.resolution_percentage = 35
    sc.render.filepath = os.path.join(OUT, s['id'] + '_shadow.png')
    bpy.ops.render.render(write_still=True); print('RENDERED', s['id'], flush=True)

for s in specs:
    if only and s['id'] not in only: continue
    if s.get('skip'): continue
    if os.environ.get('SKIP_EXISTING') and os.path.exists(os.path.join(OUT, s['id'] + '.png')): continue
    try: render(s)
    except Exception as e:
        import traceback; traceback.print_exc(); print('FAILED', s['id'], e, flush=True)
