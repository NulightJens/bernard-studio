import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {clamp, easeIn, easeInOut, easeOut, Guides, prog, useFonts, Word} from '../kit';

// Words in the room: his words set on the wall behind him. The room plate is his own footage; a cutout of him (the
// same frames through the matte) is laid back over the words, so his head and hands pass in front of them. One slow
// camera push carries plate, words and him together, so the words stay locked to the wall.
// Python (styles/words-in-the-room/render.py) resolves every word anchor to a frame and writes these props.

type Item = {
  kind: 'figure' | 'line' | 'type' | 'title';
  text: string;
  x: number | null; // left edge of the text, or null: centred on the frame
  y: number; // top of the text box (line height 1)
  size: number;
  at: number | null; // null: on the wall from the first frame, settling in
  warm: number | null; // the glow swells once here
  strike: number | null; // the red brush strikes across it here
  dim: number | null; // steps back to a third here
  until: number | null; // leaves here
  leave: 'lift' | 'fade';
  stack: number[]; // rules laid above it, one per frame, nearest first
  cx: number; // the text's centre line (the rules centre on it)
  brush: {left: number; width: number} | null; // where the strike's brush lies
};
export type WordsInTheRoomProps = {
  w: number;
  h: number;
  fps: number;
  frames: number;
  fill: string; // the room's measured colour, carried past the plate's edges
  color: string; // the words' colour
  fonts: {serif: string; serifItalic: string; sans: string; type: string};
  brush: string;
  room: {n: number; left: number; top: number; width: number; height: number; fadeTop: [number, number] | null; fadeBottom: [number, number]};
  camera: {push: number; drift: number; focus: [number, number]; light: [number, number]};
  items: Item[];
  guides?: boolean;
};

const glow = (warm = 0) => `0 0 ${28 + warm * 30}px rgba(255,170,90,${0.18 + warm * 0.22}), 0 0 2px rgba(255,214,170,0.35)`;
const pad = (i: number) => String(i).padStart(5, '0');
const mask = (stops: string) => ({WebkitMaskImage: `linear-gradient(to bottom, ${stops})`, maskImage: `linear-gradient(to bottom, ${stops})`});

const Typed: React.FC<{f: number; at: number | null; text: string; style: React.CSSProperties}> = ({f, at, text, style}) => {
  const n = at === null ? text.length : f < at ? 0 : Math.min(text.length, Math.floor((f - at) * 1.5));
  return (
    <div style={{whiteSpace: 'pre', ...style}}>
      {text.slice(0, n)}
      {n > 0 && n < text.length ? (
        <span style={{display: 'inline-block', width: 0, overflow: 'visible'}}>
          <span style={{opacity: 0.55}}>▍</span>
        </span>
      ) : null}
      {/* the rest, kept invisible so a centred line does not slide while it types */}
      <span style={{opacity: 0}}>{text.slice(n)}</span>
    </div>
  );
};

const Rules: React.FC<{f: number; at: number[]; color: string; centre: number; top: number}> = ({f, at, color, centre, top}) => (
  <div style={{position: 'absolute', inset: 0, filter: 'blur(0.5px)'}}>
    {at.map((t, k) => {
      // nearest rule first and shortest; each one above is 120 px wider
      const p = prog(f, t, 12, easeOut);
      const w = 620 - (at.length - 1 - k) * 120;
      return (
        <div key={k} style={{position: 'absolute', left: centre - (w * p) / 2, top: top - k * 28, width: w * p, height: 2, background: color, opacity: 0.7, boxShadow: glow()}} />
      );
    })}
  </div>
);

const WallItem: React.FC<{it: Item; f: number; p: WordsInTheRoomProps}> = ({it, f, p}) => {
  const serif = '"RoomSerif", serif';
  const warm = it.warm === null ? 0 : interpolate(f, [it.warm - 2, it.warm + 4, it.warm + 20], [0, 1, 0], clamp);
  const dim = it.dim === null ? 1 : interpolate(prog(f, it.dim, 12), [0, 1], [1, 0.32]);
  const lift = it.until !== null && it.leave === 'lift' ? prog(f, it.until, 16, easeIn) : 0;
  const fade = it.until !== null && it.leave === 'fade' ? prog(f, it.until, 10) : 0;
  const shown = it.at === null || f >= it.at - 3;
  if (!shown || lift >= 1 || fade >= 1) return null;
  const wall: React.CSSProperties = {
    position: 'absolute',
    top: it.y,
    ...(it.x === null ? {left: 0, right: 0, display: 'flex', justifyContent: 'center'} : {left: it.x}),
    opacity: dim * (1 - lift) * (1 - fade),
    transform: `translateY(${-lift * 40}px)`,
    filter: `blur(${0.5 + lift * 8}px)`,
  };
  const base: React.CSSProperties = {lineHeight: 1, color: p.color, textShadow: glow(warm), whiteSpace: 'nowrap'};
  let body: React.ReactNode;
  if (it.kind === 'figure') {
    const style: React.CSSProperties = {...base, fontFamily: serif, fontWeight: 600, fontSize: it.size, letterSpacing: '-0.012em', fontFeatureSettings: '"lnum" 1'};
    if (it.at === null) {
      const settle = prog(f, 0, 12, easeOut);
      body = <div style={{...style, transform: `scale(${1.03 - 0.03 * settle})`}}>{it.text}</div>;
    } else {
      body = (
        <div style={style}>
          <Word f={f} at={it.at} dur={16}>
            {it.text}
          </Word>
        </div>
      );
    }
  } else if (it.kind === 'line') {
    body = (
      <div style={{...base, fontFamily: serif, fontStyle: 'italic', fontWeight: 500, fontSize: it.size}}>
        {it.at === null ? it.text : <Word f={f} at={it.at} dur={14}>{it.text}</Word>}
      </div>
    );
  } else if (it.kind === 'type') {
    body = <Typed f={f} at={it.at} text={it.text} style={{...base, fontFamily: '"RoomType", monospace', fontSize: it.size, letterSpacing: '0.16em'}} />;
  } else {
    body = (
      <div style={{...base, fontFamily: '"RoomSans", sans-serif', fontWeight: 800, fontSize: it.size, letterSpacing: '0.26em', marginRight: '-0.26em'}}>
        {it.at === null ? it.text : <Word f={f} at={it.at} dur={18} blur={12}>{it.text}</Word>}
      </div>
    );
  }
  return <div style={wall}>{body}</div>;
};

// The red brush across a figure: drawn left to right on its word, leaves with the figure.
const Strike: React.FC<{it: Item; f: number}> = ({it, f}) => {
  const box = it.brush;
  if (it.strike === null || box === null || f < it.strike) return null;
  const lift = it.until !== null && it.leave === 'lift' ? prog(f, it.until, 16, easeIn) : 0;
  const s = prog(f, it.strike, 9, easeInOut);
  return (
    <div
      style={{
        position: 'absolute', left: box.left, width: box.width, top: it.y + 0.19 * it.size, height: 0.72 * it.size,
        transform: `rotate(-3deg) translateY(${-lift * 40}px)`, clipPath: `inset(0 ${(1 - s) * 100}% 0 0)`,
        opacity: 1 - lift, filter: `blur(${0.5 + lift * 8}px)`,
      }}
    >
      {/* eslint-disable-next-line @remotion/warn-native-media-tag */}
      <Img src={staticFile('brush-red.png')} style={{width: '100%', height: '100%', objectFit: 'fill', filter: 'saturate(1.05) brightness(1.05)'}} />
    </div>
  );
};

export const WordsInTheRoom: React.FC<WordsInTheRoomProps> = (p) => {
  const f = useCurrentFrame();
  useFonts([
    ['RoomSerif', p.fonts.serif, {style: 'normal', weight: '300 700'}],
    ['RoomSerif', p.fonts.serifItalic, {style: 'italic', weight: '300 700'}],
    ['RoomSans', p.fonts.sans, {style: 'normal', weight: '100 900'}],
    ['RoomType', p.fonts.type, {style: 'normal', weight: '400'}],
  ]);
  const r = p.room;
  const i = Math.min(f, r.n - 1) + 1;
  const cam = p.camera;
  const push = interpolate(f, [0, p.frames], [1.0, 1.0 + cam.push], {...clamp, easing: easeInOut});
  const drift = interpolate(f, [0, p.frames], [0, cam.drift], clamp);
  const endFade = interpolate(f, [p.frames - 16, p.frames - 1], [1, 0], clamp);
  const plateBox: React.CSSProperties = {position: 'absolute', left: r.left, top: r.top, width: r.width, height: r.height};
  const fb = r.fadeBottom.map((y) => y - r.top);
  const plateStops = r.fadeTop
    ? `rgba(0,0,0,0) ${r.fadeTop[0] - r.top}px, rgba(0,0,0,1) ${r.fadeTop[1] - r.top}px, rgba(0,0,0,1) ${fb[0]}px, rgba(0,0,0,0) ${fb[1]}px`
    : `rgba(0,0,0,1) ${fb[0]}px, rgba(0,0,0,0) ${fb[1]}px`;
  const himStops = `rgba(0,0,0,1) ${fb[0]}px, rgba(0,0,0,0) ${fb[1]}px`;
  const [lx, ly] = cam.light;

  return (
    <AbsoluteFill style={{background: p.fill}}>
      <AbsoluteFill style={{transform: `translateY(${drift}px) scale(${push})`, transformOrigin: `${cam.focus[0]}px ${cam.focus[1]}px`, opacity: endFade}}>
        {/* the room */}
        <Img src={staticFile(`room/f${pad(i)}.jpg`)} style={{...plateBox, ...mask(plateStops)}} />

        {/* the words, on the wall behind him */}
        {p.items.map((it, k) => (
          <React.Fragment key={k}>
            <WallItem it={it} f={f} p={p} />
            <Strike it={it} f={f} />
            {it.stack.length ? <Rules f={f} at={it.stack} color={p.color} centre={it.cx} top={it.y - 0.46 * it.size} /> : null}
          </React.Fragment>
        ))}

        {/* him, over the words */}
        <Img src={staticFile(`room/p${pad(i)}.png`)} style={{...plateBox, ...mask(himStops)}} />

        {/* the room's own falloff, over everything so words and room share the same light */}
        <div style={{position: 'absolute', inset: -200, background: `radial-gradient(ellipse 60% 48% at ${lx + 200}px ${ly + 200}px, rgba(0,0,0,0) 40%, rgba(0,0,0,0.35) 100%)`}} />
      </AbsoluteFill>
      <Guides show={p.guides} />
    </AbsoluteFill>
  );
};
