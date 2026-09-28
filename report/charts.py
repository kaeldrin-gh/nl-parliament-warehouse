"""Client-side charts for the report (Observable Plot, rendered in the browser).

The page embeds its numbers as JSON; this script draws them as SVG with hover
tooltips, in the page's light or dark tokens. The term buttons switch the
three per-term charts. Kept as a plain string so the braces need no escaping.
"""

PLOT_MODULE = "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6/+esm"

SCRIPT = """
import * as Plot from "__PLOT_MODULE__";

const data = JSON.parse(document.getElementById("report-data").textContent);
const state = { term: data.terms.length ? data.terms[0].term_id : null };

function tokens() {
  const css = getComputedStyle(document.documentElement);
  const v = (name) => css.getPropertyValue(name).trim();
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  return {
    surface: v("--surface"), ink: v("--text-primary"), secondary: v("--text-secondary"),
    muted: v("--text-muted"), grid: v("--grid"), baseline: v("--baseline"),
    s1: v("--series-1"), s2: v("--series-2"),
    rampLo: v("--ramp-lo"), rampMid: v("--ramp-mid"), rampHi: v("--ramp-hi"),
    // Text on the darkest cells: white in light mode, near-black in dark mode.
    onHi: dark ? "#0b0b0b" : "#ffffff",
  };
}

const pct = (x) => (x == null ? "–" : `${Math.round(x * 100)}%`);
const fmt = (n) => n.toLocaleString("en-US");
const term = () => data.terms.find((t) => t.term_id === state.term);

function frame(t, width, height, extra = {}) {
  return {
    width, height, marginLeft: 48, marginRight: 16, marginTop: 16, marginBottom: 32,
    style: { background: "transparent", color: t.secondary, fontSize: "12px",
             fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif" },
    ...extra,
  };
}

const charts = {
  agreement(t, width) {
    const { parties, cells } = term();
    const shown = cells.filter((d) => d.share != null);
    // Room for the longest party name at 12px, and upright column labels when
    // cells are too narrow for slanted ones to clear each other.
    const longest = Math.max(...parties.map((p) => p.length));
    const left = Math.min(Math.round(longest * 6.4) + 12, 150);
    const side = Math.min(width, 820);
    const cell = (side - left) / Math.max(parties.length, 1);
    const top = Math.min(Math.round(longest * 6.4) + 10, 130);
    const chart = frame(t, side, side - left + top);
    return Plot.plot({ ...chart,
      // Plot scales an SVG down to its container; the matrix scrolls instead.
      style: { ...chart.style, maxWidth: "none" },
      marginLeft: left, marginTop: top, marginBottom: 8, marginRight: 8,
      x: { domain: parties, axis: "top", label: null, tickSize: 0,
           tickRotate: cell < 24 ? -90 : -50 },
      y: { domain: parties, label: null, tickSize: 0 },
      color: { type: "linear", domain: [0.3, 0.65, 1], range: [t.rampLo, t.rampMid, t.rampHi],
               interpolate: "lab", clamp: true },
      marks: [
        Plot.cell(shown, { x: "b", y: "a", fill: "share", inset: 1, rx: 2 }),
        cell >= 26
          ? Plot.text(shown, { x: "b", y: "a", text: (d) => Math.round(d.share * 100),
                               fill: (d) => (d.share > 0.72 ? t.onHi : t.ink),
                               fontSize: cell >= 34 ? 11 : 10 })
          : null,
        Plot.tip(cells, Plot.pointer({
          x: "b", y: "a",
          title: (d) => d.share == null
            ? `${d.a} and ${d.b}\\nfewer than ${data.min_shared} shared votes`
            : `${d.a} and ${d.b}\\nsame vote on ${pct(d.share)} of ${fmt(d.both)} decisions`
              + " both voted on",
        })),
      ],
    });
  },

  monthly(t, width) {
    const rows = data.months.flatMap((m) => [
      { month: m.month, outcome: "accepted", count: m.accepted, m },
      { month: m.month, outcome: "rejected", count: m.rejected, m },
    ]);
    const months = data.months.map((m) => m.month);
    const label = Object.fromEntries(data.months.map((m) => [m.month, m.label]));
    const step = Math.max(1, Math.ceil((months.length * 70) / Math.max(width - 64, 1)));
    const starts = data.term_starts.filter((s) => months.includes(s.month));
    return Plot.plot(frame(t, width, 280, {
      marginTop: 24,
      x: { domain: months, label: null, ticks: months.filter((_, i) => i % step === 0),
           tickFormat: (m) => label[m], paddingInner: 0.2 },
      y: { label: null, grid: true, nice: true },
      color: { domain: ["accepted", "rejected"], range: [t.s1, t.s2] },
      marks: [
        Plot.barY(rows, { x: "month", y: "count", fill: "outcome", stroke: t.surface,
                          strokeWidth: 1, order: ["accepted", "rejected"] }),
        Plot.ruleY([0], { stroke: t.baseline }),
        Plot.ruleX(starts, { x: "month", stroke: t.muted, strokeDasharray: "3,3", dx: -2 }),
        Plot.text(starts, { x: "month", text: "label", frameAnchor: "top", dy: -14, dx: 2,
                            textAnchor: "start", fill: t.secondary }),
        Plot.tip(data.months, Plot.pointerX({
          x: "month", y: (d) => d.accepted + d.rejected,
          title: (d) => `${d.label}\\naccepted  ${fmt(d.accepted)}\\nrejected  ${fmt(d.rejected)}`,
        })),
      ],
    }));
  },

  participation(t, width) {
    const rows = term().participation.filter((d) => d.share != null);
    const low = Math.min(...rows.map((d) => d.share), 0.99);
    return Plot.plot(frame(t, width, 28 + rows.length * 24, {
      marginLeft: width < 560 ? 104 : 136, marginRight: 48, marginBottom: 28,
      x: { domain: [Math.floor(low * 20) / 20, 1], grid: true, label: null,
           tickFormat: (x) => `${Math.round(x * 100)}%` },
      y: { domain: rows.map((d) => d.party), label: null, tickSize: 0 },
      marks: [
        Plot.dot(rows, { x: "share", y: "party", r: 5, fill: t.s1, stroke: t.surface,
                         strokeWidth: 2 }),
        Plot.text(rows, { x: "share", y: "party", text: (d) => pct(d.share), dx: 10,
                          textAnchor: "start", fill: t.ink }),
        Plot.tip(rows, Plot.pointer({
          x: "share", y: "party",
          title: (d) => `${d.party} (${d.seats} seats)\\ntook part in ${pct(d.share)} of `
            + `${fmt(d.decisions)} party votes`,
        })),
      ],
    }));
  },

  submitters(t, width) {
    const rows = term().motions_by_party;
    const long = rows.flatMap((d) => [
      { party: d.party, outcome: "accepted", count: d.accepted, d },
      { party: d.party, outcome: "rejected", count: d.rejected, d },
    ]);
    return Plot.plot(frame(t, width, 28 + rows.length * 26, {
      marginLeft: width < 560 ? 104 : 136, marginRight: 56, marginBottom: 28,
      x: { grid: true, label: null, nice: true },
      y: { domain: rows.map((d) => d.party), label: null, tickSize: 0 },
      color: { domain: ["accepted", "rejected"], range: [t.s1, t.s2] },
      marks: [
        Plot.barX(long, { x: "count", y: "party", fill: "outcome", stroke: t.surface,
                          strokeWidth: 1, insetTop: 4, insetBottom: 4,
                          order: ["accepted", "rejected"] }),
        Plot.ruleX([0], { stroke: t.baseline }),
        Plot.text(rows, { x: (d) => d.accepted + d.rejected, y: "party", dx: 6,
                          textAnchor: "start", fill: t.ink,
                          text: (d) => pct(d.accepted / (d.accepted + d.rejected)) }),
        Plot.tip(rows, Plot.pointerY({
          x: (d) => d.accepted + d.rejected, y: "party",
          title: (d) => `${d.party}\\naccepted  ${fmt(d.accepted)}\\nrejected  ${fmt(d.rejected)}`,
        })),
      ],
    }));
  },
};

function render() {
  if (!state.term) return;
  const t = tokens();
  for (const [name, draw] of Object.entries(charts)) {
    const el = document.getElementById(`chart-${name}`);
    // The matrix keeps a readable minimum width and scrolls inside its card on
    // phones; the other charts fit the card.
    const floor = name === "agreement" ? 600 : 280;
    if (el) el.replaceChildren(draw(t, Math.max(el.clientWidth, floor)));
  }
}

for (const button of document.querySelectorAll(".terms button")) {
  button.addEventListener("click", () => {
    state.term = Number(button.dataset.term);
    for (const b of document.querySelectorAll(".terms button")) {
      b.setAttribute("aria-pressed", String(b === button));
    }
    render();
  });
}

render();
let pending;
addEventListener("resize", () => { clearTimeout(pending); pending = setTimeout(render, 150); });
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
""".replace("__PLOT_MODULE__", PLOT_MODULE)
