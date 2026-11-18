import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {useFonts} from '../kit';

// Your feed: his real posts among anonymous grey posts. The feed scrolls and lands on his post, pulls back to show it
// between the post above and the post below, zooms into its picture, and at the end a second post of his lifts its
// picture out of the card. Python (styles/your-feed/render.py) resolves every moment to a frame and writes the props;
// nothing here knows about words.

type Post = {src: string; w: number; h: number; pic: [number, number, number, number]}; // card units, picture rect
type Caption = {text: string; at: number} | null;
type Title = {small: string; big: string} | null;
type Box = {x0: number; y0: number; x1: number; y1: number; at: number} | null;
export type YourFeedProps = {
  w: number;
  h: number;
  fps: number;
  frames: number;
  colors: {obsidian: string; cream: string; red: string; redOver: string};
  fonts: {serif: string; serifItalic: string; label: string};
  first: Post;
  second: Post;
  feedCount: number; // posts in the column (his is `mid`)
  mid: number;
  scroll: {at: number; land: number; click: number};
  back: {at: number; label: number; above: number | null; below: number | null; same: number | null; caption: Caption};
  zoom: {at: number; x: number; y: number; scale: number; title: Title; box: Box};
  lift: {at: number; pull: number; red: number; ruleY: number; maxW: number; maxH: number};
  grain: number;
  guides?: boolean;
};

const CW = 554, CH = 878, GAP = 18, PITCH = CH + GAP; // card units = a 1080p screen recording's pixels
const IMG_Y0 = 236, IMG_Y1 = 650; // the skeleton's picture band

const easeIO = Easing.bezier(0.65, 0, 0.35, 1);
const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
const k = (f: number, ins: number[], outs: number[], ease = easeIO) =>
  interpolate(f, ins, outs, {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});

const Skeleton: React.FC<{o: number}> = ({o}) => {
  const g = '#3A3A3E', g2 = '#2D2D31';
  const bar = (x: number, y: number, w: number, h: number, c = g) => (
    <div style={{position: 'absolute', left: x, top: y, width: w, height: h, borderRadius: h / 2, background: c}} />
  );
  return (
    <div style={{position: 'absolute', inset: 0, background: '#1E1E21', opacity: o, borderRadius: 14}}>
      <div style={{position: 'absolute', left: 14, top: 12, width: 50, height: 50, borderRadius: 25, background: g}} />
      {bar(76, 16, 150, 14)}{bar(76, 38, 110, 10, g2)}{bar(76, 55, 90, 10, g2)}
      {bar(14, 96, 470, 12, g2)}{bar(14, 118, 400, 12, g2)}{bar(14, 140, 300, 12, g2)}
      <div style={{position: 'absolute', left: 0, top: IMG_Y0, width: CW, height: IMG_Y1 - IMG_Y0, background: g}} />
      {bar(14, 760, 80, 12, g2)}{bar(400, 760, 130, 12, g2)}
      {[50, 180, 310, 440].map((x) => <div key={x} style={{position: 'absolute', left: x, top: 820, width: 30, height: 30, borderRadius: 15, background: g2}} />)}
    </div>
  );
};

const Cursor: React.FC<{x: number; y: number; o: number; press: number}> = ({x, y, o, press}) => (
  <div style={{position: 'absolute', left: x, top: y, opacity: o, transform: `scale(${1 - press * 0.12})`, transformOrigin: '0 0', filter: 'drop-shadow(0 6px 10px rgba(0,0,0,0.55))'}}>
    <svg width="46" height="64" viewBox="0 0 23 32">
      <path d="M1 1 L1 25 L7 19.5 L11 29 L15 27.3 L11 18 L19 18 Z" fill="#fff" stroke="#111" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  </div>
);

const Label: React.FC<{text: string; x: number; y: number; o: number; color: string; lineTo?: number}> = ({text, x, y, o, color, lineTo}) => (
  <div style={{position: 'absolute', left: x, top: y - 18, opacity: o, transform: `translateX(${(1 - o) * -16}px)`, display: 'flex', alignItems: 'center', gap: 14}}>
    <span style={{fontFamily: 'StudioLabel', fontSize: 40, letterSpacing: 3, color, whiteSpace: 'nowrap'}}>{text}</span>
    {lineTo ? <div style={{height: 2, width: lineTo * o, background: color}} /> : null}
  </div>
);

const Grain: React.FC<{opacity: number; step?: number}> = ({opacity, step = 2}) => {
  const f = useCurrentFrame();
  const seed = Math.floor(f / step) % 97;
  if (opacity <= 0) return null;
  return (
    <AbsoluteFill style={{pointerEvents: 'none', mixBlendMode: 'overlay', opacity}}>
      <svg width="100%" height="100%">
        <filter id={`g${seed}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={seed} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter={`url(#g${seed})`} />
      </svg>
    </AbsoluteFill>
  );
};

// a post card: his post as a picture (a crop of his screen, or a card made from his photo), scaled to card units
const Card: React.FC<{p: Post}> = ({p}) => <Img src={staticFile(p.src)} style={{width: CW, height: CH}} />;

export const YourFeed: React.FC<YourFeedProps> = (p) => {
  const f = useCurrentFrame();
  const C = p.colors;
  useFonts([
    ['StudioSerif', p.fonts.serif, {style: 'normal', weight: '300 700'}],
    ['StudioSerif', p.fonts.serifItalic, {style: 'italic', weight: '300 700'}],
    ['StudioLabel', p.fonts.label, {style: 'normal', weight: '400'}],
  ]);
  const s = (sec: number) => sec * p.fps; // seconds -> frames for the style's fixed motion lengths
  const {scroll: sc, back: bk, zoom: zm, lift: lf} = p;
  const MID = p.mid;
  const FEED = Array.from({length: p.feedCount}, (_, i) => i);
  const fp = p.first.pic; // the picture of his post, card units

  // ---------- camera over the feed (scroll, pull back, zoom)
  const yStart = CH / 2, yMid = MID * PITCH + CH / 2, yImg = MID * PITCH + zm.y;
  const scrollEase = Easing.bezier(0.5, 0, 0.18, 1);
  const scrollP = k(f, [sc.at, sc.land], [0, 1], scrollEase);
  let yc = yStart + (yMid - yStart) * scrollP;
  yc = yc + (yImg - yMid) * k(f, [zm.at, zm.at + s(0.9)], [0, 1]);
  const early = f < zm.at - s(0.05);
  const S = early ? k(f, [bk.at, bk.at + s(0.85)], [1.38, 0.6]) : k(f, [zm.at, zm.at + s(0.9)], [0.6, zm.scale]);
  const cx = early ? k(f, [bk.at, bk.at + s(0.85)], [540, 650]) : k(f, [zm.at, zm.at + s(0.9)], [650, 540 + (CW / 2 - zm.x) * zm.scale]);
  const cy = early ? 850 : k(f, [zm.at, zm.at + s(0.9)], [850, 930]);
  // directional blur from the scroll's speed
  const yPrev = yStart + (yMid - yStart) * k(f - 1, [sc.at, sc.land], [0, 1], scrollEase);
  const vel = Math.abs(yc - yPrev) * S * (f < sc.click ? 1 : 0);
  const blur = Math.min(7, vel * 0.1);

  const skel = bk.same === null ? 0 : k(f, [bk.same, bk.same + s(0.4)], [0, 1]);
  const scrim = k(f, [zm.at + s(0.05), zm.at + s(0.75)], [0, 1]);
  const posterO = k(f, [zm.at + s(0.1), zm.at + s(0.65)], [0, 1]);
  const midBack = k(f, [zm.at - s(0.08), zm.at + s(0.3)], [0, 1]); // his post comes back in colour
  const sceneFeed = f < lf.at;
  const away = k(f, [zm.at - s(0.15), zm.at + s(0.05)], [1, 0]);

  // labels and pulses
  const pingA = bk.above === null ? 0 : k(f, [bk.above, bk.above + s(0.15), bk.above + s(0.8)], [0, 1, 0.35]) * away;
  const lYou = k(f, [bk.label, bk.label + s(0.25)], [0, 1], easeOut) * away;
  const pingB = bk.below === null ? 0 : k(f, [bk.below, bk.below + s(0.15), bk.below + s(0.68)], [0, 1, 0.35]) * away;
  const capO = bk.caption === null ? 0 : k(f, [bk.caption.at, bk.caption.at + s(0.25)], [0, 1], easeOut) * away;
  const cardScreenY = (i: number) => cy + (i * PITCH + CH / 2 - yc) * S;

  // the frame drawn on a detail of his picture (zoom), card units
  const bx = zm.box;
  const draw = bx === null ? 0 : k(f, [bx.at, bx.at + s(0.65)], [0, 1], easeIO);
  const toScreen = (ux: number, uy: number) => [cx + (ux - CW / 2) * S, cy + (MID * PITCH + uy - yc) * S];
  const [sx0, sy0] = bx === null ? [0, 0] : toScreen(bx.x0, bx.y0);
  const [sx1, sy1] = bx === null ? [0, 0] : toScreen(bx.x1, bx.y1);
  const zoomOut = k(f, [lf.at - s(0.25), lf.at - s(0.05)], [1, 0]);

  // cursor path
  let cxr = 760, cyr = 1180, co = k(f, [sc.at + s(0.05), sc.at + s(0.35)], [0, 1]), press = 0;
  if (f < sc.click + s(0.4)) {
    cxr = k(f, [sc.click - s(0.8), sc.click], [780, 600], easeIO);
    cyr = k(f, [sc.click - s(0.8), sc.click], [1230, 980], easeIO);
    press = k(f, [sc.click, sc.click + s(0.08), sc.click + s(0.2)], [0, 1, 0]);
  } else if (bx === null || f < bx.at - s(0.2)) {
    cxr = k(f, [bk.at + s(0.3), bk.at + s(0.9)], [600, 860], easeIO);
    cyr = k(f, [bk.at + s(0.3), bk.at + s(0.9)], [980, 1200], easeIO);
    co = k(f, [bk.at + s(0.9), bk.at + s(1.2)], [1, 0]);
  } else {
    co = k(f, [bx.at - s(0.35), bx.at - s(0.15)], [0, 1]) * k(f, [lf.at - s(0.3), lf.at - s(0.1)], [1, 0]);
    cxr = sx0 + (sx1 - sx0) * draw;
    cyr = sy0 + (sy1 - sy0) * draw;
    if (f < bx.at) {
      cxr = k(f, [bx.at - s(0.35), bx.at], [sx0 + 140, sx0], easeOut);
      cyr = k(f, [bx.at - s(0.35), bx.at], [sy0 + 160, sy0], easeOut);
    }
    press = k(f, [bx.at - s(0.05), bx.at + s(0.02)], [0, 1]) * k(f, [bx.at + s(0.65), bx.at + s(0.75)], [1, 0]);
  }
  const ripple = k(f, [sc.click + s(0.04), sc.click + s(0.5)], [0, 1], easeOut);

  const top3 = zm.title === null ? 0 : k(f, [zm.at + s(0.15), zm.at + s(0.55)], [0, 1], easeOut) * zoomOut;

  // ---------- the lift: his second post sits in an anonymous feed; its picture comes out of the card, straight on
  const s4 = f >= lf.at - 3;
  const s4in = k(f, [lf.at - s(0.05) - 4, lf.at + 3], [0, 1]);
  const pull = k(f, [lf.pull, lf.pull + s(0.67)], [0, 1], easeIO);
  const settle = k(f, [lf.pull + s(0.77), p.frames], [0, 1], easeOut);

  return (
    <AbsoluteFill style={{background: C.obsidian}}>
      {sceneFeed && (
        <AbsoluteFill>
          <AbsoluteFill style={{background: `radial-gradient(ellipse 60% 45% at ${(cx / 1080) * 100}% 46%, rgba(241,235,223,0.10), rgba(0,0,0,0) 70%)`}} />
          <svg width="0" height="0" style={{position: 'absolute'}}>
            <filter id="vblur"><feGaussianBlur stdDeviation={`0 ${blur.toFixed(2)}`} /></filter>
          </svg>
          <div style={{position: 'absolute', left: 0, top: 0, width: CW, height: FEED.length * PITCH, transformOrigin: '0 0',
            transform: `translate(${cx - (CW / 2) * S}px, ${cy - yc * S}px) scale(${S})`, filter: blur > 0.3 ? 'url(#vblur)' : undefined}}>
            {FEED.map((i) => {
              const isMid = i === MID;
              const sk = isMid ? skel * (1 - midBack) : 1;
              const ping = i === MID - 1 ? pingA : i === MID + 1 ? pingB : 0;
              const dim = isMid ? 1 : 1 - 0.35 * k(f, [zm.at - s(0.05), zm.at + s(0.45)], [0, 1]);
              return (
                <div key={i} style={{position: 'absolute', left: 0, top: i * PITCH, width: CW, height: CH, borderRadius: 14, overflow: 'hidden', opacity: dim,
                  boxShadow: '0 30px 60px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.06)'}}>
                  {isMid && <Card p={p.first} />}
                  {(!isMid || sk > 0) && <Skeleton o={sk} />}
                  {ping > 0 && <div style={{position: 'absolute', inset: 0, borderRadius: 14, boxShadow: `inset 0 0 0 ${6 * ping}px rgba(241,235,223,${0.9 * ping})`}} />}
                  {isMid && scrim > 0 && (<>
                    <div style={{position: 'absolute', left: 0, top: 0, width: CW, height: fp[1], background: C.obsidian, opacity: 0.97 * scrim}} />
                    <div style={{position: 'absolute', left: 0, top: fp[3] + 16, width: CW, height: CH - fp[3] - 16, background: C.obsidian, opacity: 0.97 * scrim}} />
                    <div style={{position: 'absolute', left: 0, top: fp[1] - 6, width: fp[0], height: fp[3] - fp[1] + 72, background: C.obsidian, opacity: 0.88 * scrim}} />
                    <div style={{position: 'absolute', left: fp[2], top: fp[1] - 6, width: CW - fp[2], height: fp[3] - fp[1] + 72, background: C.obsidian, opacity: 0.88 * scrim}} />
                  </>)}
                </div>
              );
            })}
          </div>
          {/* zoom: everything but his picture goes dark; the picture stays exactly where the zoom put it */}
          {posterO > 0 && (() => {
            const [px0, py0] = toScreen(fp[0], fp[1]); const [px1, py1] = toScreen(fp[2], fp[3]); const [cx0, cy0] = toScreen(0, 0);
            return (<>
              <AbsoluteFill style={{background: C.obsidian, opacity: 0.985 * posterO}} />
              <div style={{position: 'absolute', left: px0, top: py0, width: px1 - px0, height: py1 - py0, overflow: 'hidden', boxShadow: `0 40px 90px rgba(0,0,0,${0.7 * posterO})`}}>
                <Img src={staticFile(p.first.src)} style={{position: 'absolute', left: cx0 - px0, top: cy0 - py0, width: CW * S, height: CH * S}} />
              </div>
            </>);
          })()}
          {/* his post: cream corner brackets */}
          {(() => {
            const o = lYou; if (o <= 0) return null;
            const y0 = cardScreenY(MID) - (CH / 2) * S - 14, y1 = cardScreenY(MID) + (CH / 2) * S + 14;
            const x0 = cx - (CW / 2) * S - 14, x1 = cx + (CW / 2) * S + 14, L = 40 * o;
            const st = {position: 'absolute' as const, borderColor: C.cream, borderStyle: 'solid', width: L, height: L};
            return (<>
              <div style={{...st, left: x0, top: y0, borderWidth: '4px 0 0 4px'}} />
              <div style={{...st, left: x1 - L, top: y0, borderWidth: '4px 4px 0 0'}} />
              <div style={{...st, left: x0, top: y1 - L, borderWidth: '0 0 4px 4px'}} />
              <div style={{...st, left: x1 - L, top: y1 - L, borderWidth: '0 4px 4px 0'}} />
            </>);
          })()}
          {/* cream while his real post (which may carry its own red) shows; red once it has turned grey like the rest */}
          <Label text="YOUR POST" x={140} y={cardScreenY(MID)} o={lYou} color={skel > 0.5 ? C.redOver : C.cream} lineTo={90} />
          {bk.caption !== null && (
            <div style={{position: 'absolute', left: 140, top: 1510, opacity: capO, fontFamily: 'StudioSerif', fontStyle: 'italic', fontSize: 64, color: C.cream, letterSpacing: 0.5, whiteSpace: 'nowrap'}}>
              {bk.caption.text}
            </div>
          )}
          {draw > 0 && (
            <div style={{position: 'absolute', left: Math.min(sx0, sx0 + (sx1 - sx0) * draw), top: sy0, width: (sx1 - sx0) * draw, height: (sy1 - sy0) * draw,
              border: `3px solid ${C.cream}`, boxShadow: '0 0 0 9999px rgba(0,0,0,' + (0.45 * draw).toFixed(3) + ')', opacity: zoomOut}} />
          )}
          {zm.title !== null && (
            <div style={{position: 'absolute', left: 80, right: 80, top: 236, textAlign: 'center', opacity: top3, transform: `translateY(${(1 - top3) * 14}px)`}}>
              <div style={{fontFamily: 'StudioLabel', fontSize: 30, letterSpacing: 6, color: 'rgba(241,235,223,0.7)'}}>{zm.title.small}</div>
              <div style={{fontFamily: 'StudioSerif', fontStyle: 'italic', fontWeight: 500, fontSize: 92, lineHeight: 1.0, color: C.cream, marginTop: 6}}>{zm.title.big}</div>
            </div>
          )}
          {ripple > 0 && ripple < 1 && (
            <div style={{position: 'absolute', left: 600 - 60 * ripple, top: 980 - 60 * ripple, width: 120 * ripple, height: 120 * ripple, borderRadius: '50%', border: `3px solid rgba(241,235,223,${1 - ripple})`}} />
          )}
          <Cursor x={cxr} y={cyr} o={co} press={press} />
        </AbsoluteFill>
      )}
      {s4 && (() => {
        const S4 = 0.6, colY = 900, cardX = 540 - (CW / 2) * S4;
        const cardY = (i: number) => colY + i * PITCH * S4 - (CH / 2) * S4;
        const dimFeed = 1 - 0.92 * pull;
        const [IX, IY, IX1, IY1] = p.second.pic;
        const IW = IX1 - IX, IH = IY1 - IY;
        const endW = Math.min(lf.maxW, (lf.maxH * IW) / IH);
        const w = IW * S4 + (endW - IW * S4) * pull;
        const x0 = cardX + IX * S4, y0 = cardY(0) + IY * S4;
        const cxp = x0 + (IW * S4) / 2 + (540 - (x0 + (IW * S4) / 2)) * pull;
        const cyp = y0 + (IH * S4) / 2 + (820 - (y0 + (IH * S4) / 2)) * pull - 10 * settle;
        const h = (w * IH) / IW;
        const line = k(f, [lf.red, lf.red + s(0.4)], [0, 1], easeOut);
        const u = w / 880;
        return (
          <AbsoluteFill style={{opacity: s4in}}>
            <AbsoluteFill style={{background: 'radial-gradient(ellipse 60% 45% at 50% 46%, rgba(241,235,223,0.08), rgba(0,0,0,0) 70%)'}} />
            {[-1, 0, 1].map((i) => (
              <div key={i} style={{position: 'absolute', left: cardX, top: cardY(i), width: CW, height: CH, transform: `scale(${S4})`, transformOrigin: '0 0',
                borderRadius: 14, overflow: 'hidden', opacity: dimFeed, boxShadow: '0 30px 60px rgba(0,0,0,0.55)'}}>
                {i === 0 ? <Card p={p.second} /> : <Skeleton o={1} />}
                {i === 0 && <div style={{position: 'absolute', left: IX, top: IY, width: IW, height: IH, background: '#1A1A1C', opacity: pull > 0 ? 1 : 0}} />}
              </div>
            ))}
            <div style={{position: 'absolute', left: cxp - w / 2, top: cyp - h / 2, width: w, height: h, perspective: 1600}}>
              <div style={{position: 'absolute', inset: 0, overflow: 'hidden', borderRadius: 4 + 4 * pull,
                transform: `translateZ(${40 * Math.sin(Math.PI * pull)}px) rotateX(${4 * Math.sin(Math.PI * pull)}deg)`,
                boxShadow: `0 ${10 + 40 * pull}px ${20 + 70 * pull}px rgba(0,0,0,${0.3 + 0.5 * pull})`}}>
                <Img src={staticFile(p.second.src)} style={{position: 'absolute', left: -IX * (w / IW), top: -IY * (w / IW), width: CW * (w / IW), height: CH * (w / IW)}} />
                {/* the one red mark of the last frame: a short rule */}
                <div style={{position: 'absolute', left: w / 2 - 45 * line * u, top: lf.ruleY * h, height: 6 * u, width: 90 * line * u, background: C.red}} />
              </div>
            </div>
          </AbsoluteFill>
        );
      })()}
      <AbsoluteFill style={{pointerEvents: 'none', background: 'radial-gradient(ellipse 75% 60% at 50% 45%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.5) 100%)'}} />
      <Grain opacity={p.grain} step={2} />
    </AbsoluteFill>
  );
};
