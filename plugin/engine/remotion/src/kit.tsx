import React, {useEffect, useState} from 'react';
import {continueRender, delayRender, Easing, interpolate, staticFile} from 'remotion';

// Shared by every composition: easing, progress, the rising word, and font loading from the render's public folder.

export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
export const easeInOut = Easing.bezier(0.65, 0, 0.35, 1);
export const easeIn = Easing.bezier(0.5, 0, 0.75, 0);

export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// progress 0..1 of an animation that starts at frame `start` and lasts `dur` frames
export const prog = (f: number, start: number, dur: number, ease = easeOut) =>
  interpolate(f, [start, start + dur], [0, 1], {...clamp, easing: ease});

// A font face from the public folder: [family, file, descriptors]
export type Face = [string, string, FontFaceDescriptors];

// Loads the faces before the first frame is taken. Each composition calls it once with its own faces.
export const useFonts = (faces: Face[]) => {
  const [handle] = useState(() => delayRender('fonts'));
  useEffect(() => {
    Promise.all(
      faces.map(([fam, file, desc]) => {
        const ff = new FontFace(fam, `url(${staticFile(file)})`, desc);
        return ff.load().then((f) => {
          (document.fonts as any).add(f);
        });
      }),
    )
      .then(() => continueRender(handle))
      .catch((e) => {
        console.error(e);
        continueRender(handle);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
};

// A word that rises out of a mask, sharpening as it lands.
export const Word: React.FC<{
  f: number;
  at: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
  dur?: number;
  rise?: number;
  blur?: number;
}> = ({f, at, children, style, dur = 14, rise = 0.42, blur = 10}) => {
  const p = prog(f, at, dur);
  return (
    <span style={{display: 'inline-block', overflow: 'hidden', padding: '0.08em 0.04em 0.16em', margin: '-0.08em -0.04em -0.16em', verticalAlign: 'bottom'}}>
      <span
        style={{
          display: 'inline-block',
          transform: `translateY(${(1 - p) * rise * 100}%)`,
          opacity: interpolate(p, [0, 0.6], [0, 1], clamp),
          filter: `blur(${(1 - p) * blur}px)`,
          ...style,
        }}
      >
        {children}
      </span>
    </span>
  );
};

// Safe-zone guide overlay for checking stills (80 px sides, bottom 300 px, top 220 px status bar).
export const Guides: React.FC<{show?: boolean}> = ({show}) =>
  show ? (
    <div style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
      <div style={{position: 'absolute', left: 80, top: 0, bottom: 0, borderLeft: '2px dashed #0f0'}} />
      <div style={{position: 'absolute', right: 80, top: 0, bottom: 0, borderLeft: '2px dashed #0f0'}} />
      <div style={{position: 'absolute', left: 0, right: 0, top: 1620, borderTop: '2px dashed #f0f'}} />
      <div style={{position: 'absolute', left: 0, right: 0, top: 220, borderTop: '2px dashed #ff0'}} />
    </div>
  ) : null;
