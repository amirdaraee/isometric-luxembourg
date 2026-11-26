/** The shadow height map's coarse tops (layer-09-light.md rule 2): for blocks of TOP_CELLS x TOP_CELLS cells, a
 * height nothing in the block reaches, and whether the block has a tree or a structure at all. The light pass asks
 * it before reading the cells themselves, so a ray in the air over everything near it costs one read a step instead
 * of eight, and one among buildings only costs five. It changes no shadow: a block's value is at least the highest
 * thing the cells read at any point in the block can give. */
export const TOP_CELLS = 4;

export interface Tops { data: Float32Array; width: number; height: number; zTop: number }

/** A, B: the height map's two RGBA textures (terrain cm low and high byte, building, tree top; tree bottom, structure
 * top, structure bottom); units: building, tree, structure (m). A point's reading mixes the four cells around it
 * (terrain bilinear, tops averaged), which is never above the highest terrain plus the highest top among them; a
 * point in block I reads cells K*I - 1 to K*I + K, so each block also takes the row and column on either side. */
export function coarseTops(A: Uint8Array, B: Uint8Array, width: number, height: number, zbase: number,
                           units: [number, number, number], K = TOP_CELLS): Tops {
  const cw = Math.ceil(width / K), ch = Math.ceil(height / K);
  const maxT = new Float32Array(cw * ch).fill(-1e9), maxTop = new Float32Array(cw * ch), more = new Uint8Array(cw * ch);
  let tmax = -1e9;
  for (let y = 0; y < height; y++) {
    const J = Math.floor(y / K), ry = y % K;
    const J0 = ry === 0 && J > 0 ? J - 1 : J, J1 = ry === K - 1 && J + 1 < ch ? J + 1 : J;
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      const T = A[i] + A[i + 1] * 256;
      const top = Math.max(A[i + 2] * units[0], A[i + 3] * units[1], B[i + 1] * units[2]);
      const second = A[i + 3] > 0 || B[i + 1] > 0 ? 1 : 0;       // a tree or a structure: its numbers are in B
      if (T > tmax) tmax = T;
      const I = Math.floor(x / K), rx = x % K;
      const I0 = rx === 0 && I > 0 ? I - 1 : I, I1 = rx === K - 1 && I + 1 < cw ? I + 1 : I;
      for (let j = J0; j <= J1; j++) for (let c = I0; c <= I1; c++) {
        const o = j * cw + c;
        if (T > maxT[o]) maxT[o] = T;
        if (top > maxTop[o]) maxTop[o] = top;
        if (second) more[o] = 1;
      }
    }
  }
  const data = new Float32Array(cw * ch * 2);                  // per block: its top, and 1 where B has to be read
  for (let o = 0; o < cw * ch; o++) { data[o * 2] = zbase + maxT[o] / 100 + maxTop[o] + 0.01; data[o * 2 + 1] = more[o]; }
  return { data, width: cw, height: ch, zTop: zbase + tmax / 100 + 80 };
}
