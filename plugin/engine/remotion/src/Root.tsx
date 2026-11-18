import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {ScreenAndFace} from './screen-and-face/ScreenAndFace';
import {YourFeed} from './your-feed/YourFeed';
import {WordsInTheRoom} from './words-in-the-room/WordsInTheRoom';

// One composition per style. Python writes the props (every time already in frames) and names the composition;
// size, rate and length come from the props, so one composition serves every passage.
type Sized = {w: number; h: number; fps: number; frames: number};
const sized: CalculateMetadataFunction<any> = ({props}) => {
  const p = props as unknown as Sized;
  return {width: p.w, height: p.h, fps: p.fps, durationInFrames: Math.max(1, Math.round(p.frames))};
};
const blank = {w: 1080, h: 1920, fps: 24, frames: 24};

export const Root: React.FC = () => (
  <>
    <Composition id="screen-and-face" component={ScreenAndFace as any} width={1080} height={1920} fps={24} durationInFrames={24}
      defaultProps={blank as any} calculateMetadata={sized} />
    <Composition id="your-feed" component={YourFeed as any} width={1080} height={1920} fps={30} durationInFrames={30}
      defaultProps={blank as any} calculateMetadata={sized} />
    <Composition id="words-in-the-room" component={WordsInTheRoom as any} width={1080} height={1920} fps={24} durationInFrames={24}
      defaultProps={blank as any} calculateMetadata={sized} />
    {/* more compositions here, one line each (see README.md) */}
  </>
);
