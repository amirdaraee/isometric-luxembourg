// One frame clock for everything that animates. For now each subscriber simply gets its own requestAnimationFrame
// loop; later the insides become one shared loop with a frame budget, without changing this API.
//
//   const stop = subscribe((t, dt) => draw(t), { fps: 30 });
//   ...
//   stop();
//
// t: the requestAnimationFrame timestamp, ms. dt: ms since this subscriber's previous call (0 on the first call).

export type FrameFn = (t: number, dt: number) => void;
export interface FrameOptions {
  /** Highest rate wanted, frames per second. Omit for every frame. */
  fps?: number;
}

/** Calls `fn` once per animation frame (at most `fps` times a second) until the returned function is called. */
export function subscribe(fn: FrameFn, opts: FrameOptions = {}): () => void {
  const minGap = opts.fps && opts.fps > 0 ? 1000 / opts.fps : 0;
  let raf = 0, last = -1, stopped = false;
  const tick = (t: number) => {
    if (stopped) return;
    raf = requestAnimationFrame(tick);
    // a small tolerance so that 30 fps on a 60 Hz screen doesn't drop to 20
    if (last >= 0 && t - last < minGap - 2) return;
    const dt = last < 0 ? 0 : t - last;
    last = t;
    fn(t, dt);
  };
  raf = requestAnimationFrame(tick);
  return () => { stopped = true; cancelAnimationFrame(raf); };
}
