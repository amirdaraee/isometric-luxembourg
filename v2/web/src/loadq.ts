// The loads' queue. A view asks for all its tiles at once: three files a tile, seven layers, and each tile's coarser
// parents. On a large window that is some 2,000 requests, and a browser refuses what it will not hold (Chrome:
// net::ERR_INSUFFICIENT_RESOURCES, 549 of 1,947 on a 2552 x 1278 window at two device pixels a pixel). So at most
// `max` loads run at a time and the rest wait their turn; a load no longer wanted when its turn comes is dropped;
// and a request the network fails is made again.

/** What a load is rejected with when it was dropped unrun: nothing wanted it any more. */
export class Stale extends Error {
  constructor() { super("no longer wanted"); }
}

export type Limit = <T>(run: () => Promise<T>, wanted?: () => boolean) => Promise<T>;

/** At most `max` runs at a time, in the order asked. `wanted` is asked when a load's turn comes: false drops it. */
export function limiter(max: number): Limit {
  let active = 0;
  const queue: { run: () => Promise<unknown>; wanted?: () => boolean; res: (v: unknown) => void; rej: (e: unknown) => void }[] = [];
  const next = () => {
    while (active < max && queue.length) {
      const j = queue.shift()!;
      if (j.wanted && !j.wanted()) { j.rej(new Stale()); continue; }
      active++;
      let p: Promise<unknown>;
      try { p = j.run(); } catch (e) { p = Promise.reject(e); }
      p.then(j.res, j.rej).finally(() => { active--; next(); });
    }
  };
  return <T>(run: () => Promise<T>, wanted?: () => boolean) => new Promise<T>((res, rej) => {
    queue.push({ run, wanted, res: res as (v: unknown) => void, rej });
    next();
  });
}

/** run(), and again after a wait each time it throws: `tries` times in all, the wait doubling from `waitMs`. */
export async function retry<T>(run: () => Promise<T>, tries = 3, waitMs = 250,
  sleep: (ms: number) => Promise<void> = (ms) => new Promise((r) => setTimeout(r, ms))): Promise<T> {
  for (let i = 0; ; i++) {
    try { return await run(); } catch (e) {
      if (i + 1 >= tries) throw e;
      await sleep(waitMs * 2 ** i);
    }
  }
}

/** The wait before a tile that failed is asked for again: 1 s after the first failure, doubling, 30 s at most. */
export function retryWaitMs(failures: number): number {
  return Math.min(30000, 1000 * 2 ** Math.max(0, failures - 1));
}
