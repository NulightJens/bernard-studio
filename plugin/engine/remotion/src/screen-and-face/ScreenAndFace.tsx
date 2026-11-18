import React from 'react';
import {AbsoluteFill, Img, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {clamp, easeIn, easeInOut, easeOut, Guides, prog, useFonts, Word} from '../kit';

// Screen and Face: his real screen on top, him below, and a black seam between them where the number lands.
// Python (styles/screen-and-face/render.py) resolves every word anchor to a frame and writes these props.

type Shot = {src: string; from: number; dur: number; push: [number, number]; origin: string};
type Line = {text: string; at: number};
type Figure = {
  text: string;
  scale?: number; // the figure's size: 168 px times this (0.7 to 1.4), default 1
  open: boolean; // on screen from frame 0 (the claim on the first frame), settling in over half a second
  inAt: number; // frame the number rises in (when not open)
  ruleAt: number | null; // a cream rule draws under the number
  strikeAt: number | null; // the red brush strike across the number
  outAt: number | null; // the number starts to leave
  lines: Line[];
  linesFrom: number; // the lines block is on screen from here ...
  linesOutAt: number | null; // ... starts to leave here ...
  linesCut: number | null; // ... and is gone from here
  underlineAt: number | null; // a red line draws under the lines
};
export type ScreenAndFaceProps = {
  w: number;
  h: number;
  fps: number;
  frames: number;
  colors: {black: string; cream: string; red: string; line: string};
  fonts: {serif: string; serifItalic: string};
  brush: string;
  face: {src: string; left: number; top: number; width: number; height: number; segments: {from: number; punch: number}[]};
  screens: Shot[];
  figures: Figure[];
  guides?: boolean;
};

// The frame, kept as Bernard picked it.
const TOP_H = 820;
const BAND_Y = 820;
const BAND_H = 190;
const BOT_Y = BAND_Y + BAND_H; // 1010
const SIDE = 80;

const Screen: React.FC<Shot> = ({src, from, dur, push, origin}) => {
  const f = useCurrentFrame();
  const s = interpolate(f - from, [0, dur], push, clamp);
  return (
    <Sequence from={from} durationInFrames={Math.max(1, dur)} layout="none">
      <div style={{position: 'absolute', inset: 0, overflow: 'hidden'}}>
        <OffthreadVideo
          src={staticFile(src)}
          muted
          style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${s})`, transformOrigin: origin}}
        />
      </div>
    </Sequence>
  );
};

export const ScreenAndFace: React.FC<ScreenAndFaceProps> = (p) => {
  const f = useCurrentFrame();
  const C = p.colors;
  useFonts([
    ['StudioSerif', p.fonts.serif, {style: 'normal', weight: '300 700'}],
    ['StudioSerif', p.fonts.serifItalic, {style: 'italic', weight: '300 700'}],
  ]);
  const serif = '"StudioSerif", serif';
  const numStyle: React.CSSProperties = {
    fontFamily: serif,
    fontWeight: 600,
    fontSize: 168,
    lineHeight: 1,
    color: C.cream,
    letterSpacing: '-0.01em',
    fontFeatureSettings: '"lnum" 1',
    whiteSpace: 'nowrap',
  };
  const labelStyle: React.CSSProperties = {
    fontFamily: serif,
    fontStyle: 'italic',
    fontWeight: 500,
    fontSize: 50,
    lineHeight: 1.08,
    color: C.cream,
    textAlign: 'right',
    whiteSpace: 'nowrap',
  };

  // the opening settle: a 3 % scale clears over half a second
  const open = prog(f, 0, 12, easeOut);
  const openScale = 1.03 - 0.03 * open;

  let punch = 1.0;
  for (const s of p.face.segments) if (f >= s.from) punch = s.punch;

  return (
    <AbsoluteFill style={{background: C.black}}>
      {/* TOP: his real screen */}
      <div style={{position: 'absolute', left: 0, top: 0, width: p.w, height: TOP_H, overflow: 'hidden'}}>
        {p.screens.map((s, k) => (
          <Screen key={k} {...s} />
        ))}
        <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 160, background: 'linear-gradient(to bottom, rgba(10,9,8,0), rgba(10,9,8,0.55))'}} />
        <div style={{position: 'absolute', inset: 0, boxShadow: 'inset 0 0 120px rgba(0,0,0,0.45)'}} />
      </div>

      {/* BOTTOM: him */}
      <div style={{position: 'absolute', left: 0, top: BOT_Y, width: p.w, height: p.h - BOT_Y, overflow: 'hidden'}}>
        <div style={{position: 'absolute', inset: 0, transform: `scale(${punch})`, transformOrigin: '50% 30%'}}>
          <OffthreadVideo
            src={staticFile(p.face.src)}
            muted
            style={{position: 'absolute', left: p.face.left, top: p.face.top, width: p.face.width, height: p.face.height}}
          />
        </div>
        <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 70, background: 'linear-gradient(to bottom, rgba(10,9,8,0.7), rgba(10,9,8,0))'}} />
      </div>

      {/* SEAM BAND */}
      <div style={{position: 'absolute', left: 0, top: BAND_Y, width: p.w, height: BAND_H, background: C.black}}>
        <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 1, background: C.line}} />
        <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 1, background: C.line}} />

        {p.figures.map((g, k) => {
          const out = g.outAt === null ? 0 : prog(f, g.outAt, 7, easeIn);
          const shown = (g.open || f >= g.inAt - 2) && (g.outAt === null || f < g.outAt + 8);
          if (!shown) return null;
          const rule = g.ruleAt === null ? 0 : prog(f, g.ruleAt, 12, easeOut);
          const strike = g.strikeAt === null ? 0 : prog(f, g.strikeAt, 8, easeInOut);
          const sc = g.scale ?? 1;
          return (
            <div key={`n${k}`} style={{position: 'absolute', left: SIDE, top: 0, height: BAND_H, display: 'flex', alignItems: 'center', opacity: 1 - out, transform: `translateY(${-out * 30}px)`, filter: `blur(${out * 6}px)`}}>
              <div style={{position: 'relative', ...numStyle, fontSize: 168 * sc, ...(g.open ? {transform: `scale(${openScale})`, transformOrigin: '0% 50%'} : {})}}>
                {g.open ? g.text : (
                  <Word f={f} at={g.inAt} dur={16}>
                    {g.text}
                  </Word>
                )}
                {g.ruleAt !== null ? (
                  <div style={{position: 'absolute', left: 4, bottom: -14 + 84 * Math.max(0, sc - 1), height: 2, width: `${rule * 100}%`, background: C.cream, opacity: 0.6}} />
                ) : null}
                {g.strikeAt !== null ? (
                  <div style={{position: 'absolute', left: -40, right: -30, top: '50%', height: 132 * sc, transform: 'translateY(-50%) rotate(-3deg)', clipPath: `inset(0 ${(1 - strike) * 100}% 0 0)`}}>
                    <Img src={staticFile(p.brush)} style={{width: '100%', height: '100%', objectFit: 'fill', opacity: 0.95}} />
                  </div>
                ) : null}
              </div>
            </div>
          );
        })}

        {/* right-hand lines, serif italic */}
        {p.figures.map((g, k) => {
          if (!g.lines.length || f < g.linesFrom || (g.linesCut !== null && f >= g.linesCut)) return null;
          const out = g.linesOutAt === null ? 0 : prog(f, g.linesOutAt, 7, easeIn);
          return (
            <div key={`l${k}`} style={{position: 'absolute', right: SIDE, top: 0, height: BAND_H, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'flex-end'}}>
              <div style={{position: 'relative', ...labelStyle, opacity: 1 - out, ...(g.open ? {transform: `scale(${openScale})`, transformOrigin: '100% 50%'} : {})}}>
                {g.lines.map((ln, j) => (
                  <React.Fragment key={j}>
                    {j > 0 ? <br /> : null}
                    {g.open ? ln.text : (
                      <Word f={f} at={ln.at}>
                        {ln.text}
                      </Word>
                    )}
                  </React.Fragment>
                ))}
                {g.underlineAt !== null ? (
                  <div style={{position: 'absolute', right: 0, bottom: -10, height: 3, width: `${prog(f, g.underlineAt, 10, easeOut) * 100}%`, background: C.red}} />
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
      <Guides show={p.guides} />
    </AbsoluteFill>
  );
};
