import {Config} from '@remotion/cli/config';

// PNG frames: JPEG bands dark gradients. ANGLE keeps the GPU on in the headless browser. bt709 like every deliverable.
Config.setVideoImageFormat('png');
Config.setChromiumOpenGlRenderer('angle');
Config.setColorSpace('bt709');
