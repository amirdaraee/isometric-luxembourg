// The sun's real position over Luxembourg: v2/config/sun.py (NOAA, Meeus) line for line, so the viewer and the
// Python checks agree (sun.test.ts compares them).

const LAT = 49.6112, LON = 6.13;
const rad = (d: number) => (d * Math.PI) / 180, deg = (r: number) => (r * 180) / Math.PI;

/** Azimuth (degrees clockwise from north) and elevation (degrees, with refraction) at an instant. */
export function sunPosition(t: Date, lat = LAT, lon = LON): { az: number; el: number } {
  const jd = t.getTime() / 86400000 + 2440587.5;
  const jc = (jd - 2451545.0) / 36525.0;
  const gml = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360;
  const gma = 357.52911 + jc * (35999.05029 - 0.0001537 * jc);
  const ecc = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc);
  const m = rad(gma);
  const ctr = Math.sin(m) * (1.914602 - jc * (0.004817 + 0.000014 * jc)) + Math.sin(2 * m) * (0.019993 - 0.000101 * jc)
    + Math.sin(3 * m) * 0.000289;
  const trueLong = gml + ctr;
  const omega = 125.04 - 1934.136 * jc;
  const appLong = trueLong - 0.00569 - 0.00478 * Math.sin(rad(omega));
  const meanObl = 23 + (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60;
  const obl = meanObl + 0.00256 * Math.cos(rad(omega));
  const decl = deg(Math.asin(Math.sin(rad(obl)) * Math.sin(rad(appLong))));
  const y = Math.tan(rad(obl / 2)) ** 2;
  const l0 = rad(gml);
  const eot = 4 * deg(y * Math.sin(2 * l0) - 2 * ecc * Math.sin(m) + 4 * ecc * y * Math.sin(m) * Math.cos(2 * l0)
    - 0.5 * y * y * Math.sin(4 * l0) - 1.25 * ecc * ecc * Math.sin(2 * m));
  const minutes = t.getUTCHours() * 60 + t.getUTCMinutes() + t.getUTCSeconds() / 60 + t.getUTCMilliseconds() / 60000;
  const tst = (((minutes + eot + 4 * lon) % 1440) + 1440) % 1440;
  const ha = tst / 4 >= 0 ? tst / 4 - 180 : tst / 4 + 180;
  const la = rad(lat), de = rad(decl), h = rad(ha);
  const cz = Math.sin(la) * Math.sin(de) + Math.cos(la) * Math.cos(de) * Math.cos(h);
  const zen = deg(Math.acos(Math.max(-1, Math.min(1, cz))));
  const sz = Math.sin(rad(zen));
  let az: number;
  if (Math.abs(sz) < 1e-9) az = 180;
  else {
    let a = (Math.sin(la) * cz - Math.sin(de)) / (Math.cos(la) * sz);
    a = deg(Math.acos(Math.max(-1, Math.min(1, a))));
    az = ha > 0 ? (a + 180) % 360 : (540 - a) % 360;
  }
  const el = 90 - zen;
  let r: number;
  if (el > 85) r = 0;
  else if (el > 5) { const te = Math.tan(rad(el)); r = 58.1 / te - 0.07 / te ** 3 + 0.000086 / te ** 5; }
  else if (el > -0.575) r = 1735 + el * (-518.2 + el * (103.4 + el * (-12.79 + el * 0.711)));
  else r = -20.772 / Math.tan(rad(el));
  return { az, el: el + r / 3600 };
}

/** Unit vector towards the sun in (east, north, up). */
export function sunVector(az: number, el: number): [number, number, number] {
  const a = rad(az), e = rad(el);
  return [Math.sin(a) * Math.cos(e), Math.cos(a) * Math.cos(e), Math.sin(e)];
}
