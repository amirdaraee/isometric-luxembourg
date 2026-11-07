import { useEffect, useMemo, useRef, useState } from "react";
import { asset } from "../config";
import type { Place } from "./Pins";

const fold = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const RANK: Record<string, number> = { address: 3, street: 2 };

interface Entry extends Place {
  key: string;
  sub?: string;
}

interface Props {
  places: Place[];
  onPick: (p: Place) => void;
  onSurprise?: () => void;
}

export function Search({ places, onPick, onSurprise }: Props) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState(0);
  const [addresses, setAddresses] = useState<Entry[]>([]);
  const input = useRef<HTMLInputElement>(null);

  const index = useMemo<Entry[]>(() => places.map((p) => ({ ...p, key: fold(`${p.n} ${p.a ?? ""}`) })), [places]);

  // Addresses are large, so they load the first time someone searches.
  const loadAddresses = () => {
    if (addresses.length) return;
    fetch(asset("/data/addresses.json"))
      .then((r) => r.json())
      .then((rows: [string, string, number, number][]) =>
        setAddresses(rows.map(([n, pc, x, y]) => ({ n, c: "address", x, y, sub: pc ? `L-${pc}` : undefined, key: fold(n) }))),
      )
      .catch(() => undefined);
  };

  const results = useMemo(() => {
    const terms = fold(q).trim().split(/\s+/).filter(Boolean);
    if (!terms.length) return [];
    const score = (e: Entry) => {
      if (!terms.every((t) => e.key.includes(t))) return -1;
      const rank = RANK[e.c] ?? (e.f || e.q ? 0 : 1);
      return rank * 10 + (e.key.startsWith(terms[0]) ? 0 : 5);
    };
    const pool = /\d/.test(q) ? [...addresses, ...index] : [...index, ...addresses];
    const hits: [number, Entry][] = [];
    for (const e of pool) {
      const s = score(e);
      if (s >= 0) hits.push([s, e]);
    }
    return hits.sort((a, b) => a[0] - b[0]).slice(0, 8).map((h) => h[1]);
  }, [q, index, addresses]);

  useEffect(() => setSel(0), [q]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement !== input.current) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const pick = (p: Place) => {
    onPick(p);
    setOpen(false);
    setQ("");
    input.current?.blur();
  };

  return (
    <div className="top">
      <div className="pill glass">
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
          <circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d="M16.5 16.5 21 21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <input
          ref={input}
          type="search"
          value={q}
          placeholder="Search Luxembourg"
          aria-label="Search places, streets and addresses"
          aria-controls="results"
          autoComplete="off"
          spellCheck={false}
          onFocus={() => {
            setOpen(true);
            loadAddresses();
          }}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setSel((s) => Math.min(s + 1, results.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setSel((s) => Math.max(s - 1, 0));
            } else if (e.key === "Enter" && results[sel]) {
              pick(results[sel]);
            } else if (e.key === "Escape") {
              setQ("");
              input.current?.blur();
            }
          }}
        />
        <kbd aria-hidden="true">/</kbd>
        {onSurprise && (<button type="button" className="ibtn" title="Surprise me" aria-label="Surprise me" onClick={onSurprise}>
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <rect x="3.5" y="3.5" width="17" height="17" rx="4" fill="none" stroke="currentColor" strokeWidth="2" />
            <circle cx="8.5" cy="8.5" r="1.6" fill="currentColor" />
            <circle cx="12" cy="12" r="1.6" fill="currentColor" />
            <circle cx="15.5" cy="15.5" r="1.6" fill="currentColor" />
          </svg>
        </button>)}
      </div>
      {open && q.trim() !== "" && (
        <ul id="results" className="results glass" role="listbox">
          {results.length === 0 && <li className="none">Nothing here yet. The map covers the centre and Kirchberg.</li>}
          {results.map((r, i) => (
            <li key={`${r.n}-${r.x}-${r.y}`} role="option" aria-selected={i === sel}>
              <button type="button" className={i === sel ? "on" : ""} onMouseDown={() => pick(r)}>
                <span className="name">{r.n}</span>
                <span className="sub">{r.sub ?? r.c.replace("-", " ")}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
