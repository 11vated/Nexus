// Paradigm Pocket Studio — visual2d gene editor with deterministic xoshiro256**,
// Gaussian additive mutation, BLX-α crossover, AsyncStorage persistence,
// and a live SVG-style canvas preview rendered with React Native primitives.

import React, { useEffect, useMemo, useState } from "react";
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  TextInput, Alert, Pressable,
} from "react-native";
// AsyncStorage shim — falls back to in-memory if the native module isn't installed.
// Drop in @react-native-async-storage/async-storage later for persistence across launches.
const _mem: Record<string, string> = {};
const AsyncStorage = {
  getItem: async (k: string) => (_mem[k] ?? null),
  setItem: async (k: string, v: string) => { _mem[k] = v; },
  removeItem: async (k: string) => { delete _mem[k]; },
};


// ===================== xoshiro256** (deterministic, BigInt) =====================
const MASK = (1n << 64n) - 1n;
const rotl = (x: bigint, k: bigint) => ((x << k) | (x >> (64n - k))) & MASK;

class Xoshiro {
  s0: bigint; s1: bigint; s2: bigint; s3: bigint;
  constructor(seed: bigint) {
    // SplitMix64 to expand a single seed to 4 64-bit lanes
    let z = seed & MASK;
    const next = () => {
      z = (z + 0x9e3779b97f4a7c15n) & MASK;
      let r = z;
      r = ((r ^ (r >> 30n)) * 0xbf58476d1ce4e5b9n) & MASK;
      r = ((r ^ (r >> 27n)) * 0x94d049bb133111ebn) & MASK;
      return (r ^ (r >> 31n)) & MASK;
    };
    this.s0 = next(); this.s1 = next(); this.s2 = next(); this.s3 = next();
    if (this.s0 === 0n && this.s1 === 0n && this.s2 === 0n && this.s3 === 0n) this.s0 = 1n;
  }
  next(): bigint {
    const result = (rotl((this.s1 * 5n) & MASK, 7n) * 9n) & MASK;
    const t = (this.s1 << 17n) & MASK;
    this.s2 ^= this.s0;
    this.s3 ^= this.s1;
    this.s1 ^= this.s2;
    this.s0 ^= this.s3;
    this.s2 ^= t;
    this.s3 = rotl(this.s3, 45n);
    return result;
  }
  // uniform [0, 1)
  uniform(): number {
    return Number(this.next() >> 11n) / 2 ** 53;
  }
  // Box–Muller standard normal
  normal(): number {
    let u = this.uniform(); if (u < 1e-12) u = 1e-12;
    const v = this.uniform();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
}

// ===================== Hashing (FNV-1a 64-bit, deterministic, JS-safe) =====================
function fnv1a64(str: string): bigint {
  let h = 0xcbf29ce484222325n;
  const P = 0x100000001b3n;
  for (let i = 0; i < str.length; i++) {
    h ^= BigInt(str.charCodeAt(i));
    h = (h * P) & MASK;
  }
  return h;
}
function shortHash(str: string): string {
  return "sha256:" + fnv1a64(str).toString(16).padStart(16, "0");
}

// ===================== UniversalSeed (visual2d) =====================
type GeneVal =
  | { type: "scalar"; value: number; min: number; max: number }
  | { type: "categorical"; value: string; choices: string[] }
  | { type: "vector"; value: number[] }; // RGB in [0,1]

type UniversalSeed = {
  $gst: "1.0";
  $domain: "visual2d";
  $hash: string;
  $name: string;
  $lineage: {
    parents: string[];
    operation: "primordial" | "mutate" | "breed";
    generation: number;
    timestamp: string;
  };
  genes: Record<string, GeneVal>;
  $metadata: { engine_version: string; tags: string[] };
};

const ARCHETYPES = ["mandala", "lattice", "petals", "spiral", "weave"];

function defaultGenes(): Record<string, GeneVal> {
  return {
    size:       { type: "scalar", value: 0.6, min: 0.2, max: 1.0 },
    petals:     { type: "scalar", value: 8,   min: 3,   max: 18  },
    rotation:   { type: "scalar", value: 0.3, min: 0,   max: 1.0 },
    intensity:  { type: "scalar", value: 0.7, min: 0,   max: 1.0 },
    archetype:  { type: "categorical", value: "mandala", choices: ARCHETYPES },
    palette:    { type: "vector", value: [0.45, 0.85, 0.78] },
    accent:     { type: "vector", value: [0.65, 0.55, 0.95] },
  };
}

function canonicalize(seed: UniversalSeed): string {
  // simple deterministic JSON without $hash + sorted keys
  const { $hash, ...rest } = seed;
  const keys = Object.keys(rest).sort();
  const obj: any = {};
  for (const k of keys) (obj as any)[k] = (rest as any)[k];
  // sort genes too
  if (obj.genes) {
    const gk = Object.keys(obj.genes).sort();
    const g: any = {};
    for (const k of gk) g[k] = obj.genes[k];
    obj.genes = g;
  }
  return JSON.stringify(obj);
}
function hashSeed(seed: UniversalSeed): string {
  return shortHash(canonicalize(seed));
}
function seedToBigint(hash: string): bigint {
  const hex = hash.replace("sha256:", "");
  return BigInt("0x" + hex.padStart(16, "0"));
}

function makePrimordial(name: string): UniversalSeed {
  const s: UniversalSeed = {
    $gst: "1.0",
    $domain: "visual2d",
    $hash: "",
    $name: name,
    $lineage: { parents: [], operation: "primordial", generation: 0, timestamp: new Date().toISOString() },
    genes: defaultGenes(),
    $metadata: { engine_version: "1.0.0", tags: ["primordial"] },
  };
  s.$hash = hashSeed(s);
  return s;
}

// ===================== Genetic Operators =====================
function mutateSeed(parent: UniversalSeed, rate: number): UniversalSeed {
  const rng = new Xoshiro(seedToBigint(parent.$hash) ^ 0xa5a5a5a5a5a5a5a5n);
  const newGenes: Record<string, GeneVal> = {};
  for (const k of Object.keys(parent.genes)) {
    const g = parent.genes[k];
    if (g.type === "scalar") {
      const sigma = rate * (g.max - g.min);
      let v = g.value + sigma * rng.normal();
      v = Math.max(g.min, Math.min(g.max, v));
      newGenes[k] = { ...g, value: v };
    } else if (g.type === "vector") {
      const v = g.value.map((c) => Math.max(0, Math.min(1, c + rate * rng.normal())));
      newGenes[k] = { ...g, value: v };
    } else if (g.type === "categorical") {
      if (rng.uniform() < rate) {
        const others = g.choices.filter((c) => c !== g.value);
        if (others.length > 0) {
          const idx = Math.floor(rng.uniform() * others.length);
          newGenes[k] = { ...g, value: others[idx] };
        } else newGenes[k] = g;
      } else newGenes[k] = g;
    }
  }
  const child: UniversalSeed = {
    ...parent,
    $hash: "",
    $name: parent.$name + " *",
    $lineage: {
      parents: [parent.$hash],
      operation: "mutate",
      generation: parent.$lineage.generation + 1,
      timestamp: new Date().toISOString(),
    },
    genes: newGenes,
    $metadata: { ...parent.$metadata, tags: [...parent.$metadata.tags, "mutated"] },
  };
  child.$hash = hashSeed(child);
  return child;
}

function breedSeeds(a: UniversalSeed, b: UniversalSeed): UniversalSeed {
  const rng = new Xoshiro(seedToBigint(a.$hash) ^ seedToBigint(b.$hash));
  const ALPHA = 0.5;
  const out: Record<string, GeneVal> = {};
  for (const k of Object.keys(a.genes)) {
    const ga = a.genes[k]; const gb = b.genes[k];
    if (!gb) { out[k] = ga; continue; }
    if (ga.type === "scalar" && gb.type === "scalar") {
      // BLX-α
      const lo = Math.min(ga.value, gb.value);
      const hi = Math.max(ga.value, gb.value);
      const I = hi - lo;
      const min = lo - ALPHA * I, max = hi + ALPHA * I;
      let v = min + rng.uniform() * (max - min);
      v = Math.max(ga.min, Math.min(ga.max, v));
      out[k] = { ...ga, value: v };
    } else if (ga.type === "vector" && gb.type === "vector") {
      out[k] = { ...ga, value: ga.value.map((c, i) => {
        const cb = gb.value[i] ?? c;
        const lo = Math.min(c, cb), hi = Math.max(c, cb);
        const I = hi - lo;
        let v = (lo - ALPHA * I) + rng.uniform() * ((hi + ALPHA * I) - (lo - ALPHA * I));
        return Math.max(0, Math.min(1, v));
      }) };
    } else if (ga.type === "categorical" && gb.type === "categorical") {
      out[k] = { ...ga, value: rng.uniform() < 0.5 ? ga.value : gb.value };
    } else out[k] = ga;
  }
  const child: UniversalSeed = {
    $gst: "1.0",
    $domain: "visual2d",
    $hash: "",
    $name: `${a.$name} × ${b.$name}`,
    $lineage: {
      parents: [a.$hash, b.$hash],
      operation: "breed",
      generation: Math.max(a.$lineage.generation, b.$lineage.generation) + 1,
      timestamp: new Date().toISOString(),
    },
    genes: out,
    $metadata: { engine_version: "1.0.0", tags: ["bred"] },
  };
  child.$hash = hashSeed(child);
  return child;
}

// ===================== Storage =====================
const KEY = "paradigm.visual2d.seeds.v1";
async function loadSeeds(): Promise<UniversalSeed[]> {
  try { const raw = await AsyncStorage.getItem(KEY); return raw ? JSON.parse(raw) : []; }
  catch { return []; }
}
async function saveSeeds(arr: UniversalSeed[]) {
  try { await AsyncStorage.setItem(KEY, JSON.stringify(arr)); } catch {}
}

// ===================== Preview rendering (deterministic from seed hash) =====================
type Dot = { x: number; y: number; r: number; color: string; opacity: number };

function rgb(v: number[]) {
  const r = Math.round(v[0] * 255), g = Math.round(v[1] * 255), b = Math.round(v[2] * 255);
  return `rgb(${r},${g},${b})`;
}
function lerp(a: number, b: number, t: number) { return a + (b - a) * t; }

function grow(seed: UniversalSeed, canvas = 280): Dot[] {
  const rng = new Xoshiro(seedToBigint(seed.$hash));
  const g = seed.genes;
  const sz = (g.size as any).value as number;
  const petals = Math.round((g.petals as any).value);
  const rot = (g.rotation as any).value as number * Math.PI * 2;
  const intensity = (g.intensity as any).value as number;
  const arch = (g.archetype as any).value as string;
  const pal = (g.palette as any).value as number[];
  const acc = (g.accent as any).value as number[];
  const cx = canvas / 2, cy = canvas / 2;
  const R = (canvas / 2) * sz;
  const dots: Dot[] = [];
  const rings = 6;
  for (let ring = 1; ring <= rings; ring++) {
    const rr = (R * ring) / rings;
    const count = petals * ring;
    for (let i = 0; i < count; i++) {
      const a0 = (i / count) * Math.PI * 2 + rot * (ring / rings);
      let r = rr, ang = a0;
      if (arch === "spiral") { r = rr * (0.6 + 0.4 * (i / count)); ang = a0 + ring * 0.4; }
      if (arch === "lattice") { r = rr; ang = a0 + (ring % 2 ? Math.PI / petals : 0); }
      if (arch === "weave") { r = rr + Math.sin(a0 * petals) * 6; }
      if (arch === "petals") { r = rr * (0.6 + 0.4 * Math.abs(Math.cos(a0 * petals / 2))); }
      const jitter = (rng.uniform() - 0.5) * 4;
      const x = cx + Math.cos(ang) * r + jitter;
      const y = cy + Math.sin(ang) * r + jitter;
      const t = ring / rings;
      const color = rgb([lerp(pal[0], acc[0], t), lerp(pal[1], acc[1], t), lerp(pal[2], acc[2], t)]);
      const radius = Math.max(2, 6 * (1 - t * 0.6) * (0.6 + intensity * 0.5));
      dots.push({ x, y, r: radius, color, opacity: 0.35 + intensity * 0.55 });
    }
  }
  return dots;
}

// ===================== UI =====================
const BG = "#070b14";
const PANEL = "#0f1626";
const PANEL_2 = "#141d33";
const BORDER = "#1f2a44";
const TEXT = "#e6ebf5";
const DIM = "#8b95ad";
const ACCENT = "#7cf0c5";
const ACCENT_2 = "#a78bfa";
const WARN = "#fbbf24";

export default function Studio() {
  const [seed, setSeed] = useState<UniversalSeed>(() => makePrimordial("Bloom #1"));
  const [saved, setSaved] = useState<UniversalSeed[]>([]);
  const [mutationRate, setMutationRate] = useState(0.15);
  const [breedPick, setBreedPick] = useState<string | null>(null);
  const [showJson, setShowJson] = useState(false);
  const [growthTick, setGrowthTick] = useState(0);

  useEffect(() => { loadSeeds().then(setSeed0 => setSaved(setSeed0 || [])); }, []);

  // Re-hash on every gene change so the preview is deterministic per gene state
  useEffect(() => {
    setSeed((prev) => {
      const re: UniversalSeed = { ...prev, $hash: "" };
      re.$hash = hashSeed(re);
      return re;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dots = useMemo(() => grow(seed), [seed.$hash, growthTick]);

  function updateScalar(name: string, value: number) {
    setSeed((s) => {
      const g = s.genes[name] as any;
      const ng = { ...s.genes, [name]: { ...g, value } };
      const ns: UniversalSeed = { ...s, genes: ng, $hash: "" };
      ns.$hash = hashSeed(ns);
      return ns;
    });
  }
  function updateCategorical(name: string, value: string) {
    setSeed((s) => {
      const g = s.genes[name] as any;
      const ng = { ...s.genes, [name]: { ...g, value } };
      const ns: UniversalSeed = { ...s, genes: ng, $hash: "" };
      ns.$hash = hashSeed(ns);
      return ns;
    });
  }
  function updateVector(name: string, idx: number, value: number) {
    setSeed((s) => {
      const g = s.genes[name] as any;
      const v = [...g.value]; v[idx] = value;
      const ng = { ...s.genes, [name]: { ...g, value: v } };
      const ns: UniversalSeed = { ...s, genes: ng, $hash: "" };
      ns.$hash = hashSeed(ns);
      return ns;
    });
  }

  async function persist(s: UniversalSeed) {
    const next = [s, ...saved.filter((x) => x.$hash !== s.$hash)].slice(0, 24);
    setSaved(next);
    await saveSeeds(next);
  }
  async function onSave() { await persist(seed); Alert.alert("Saved", `${seed.$name}\n${seed.$hash}`); }
  function onGrow() { setGrowthTick((t) => t + 1); }
  function onMutate() {
    const child = mutateSeed(seed, mutationRate);
    setSeed(child);
  }
  function onBreed() {
    const partner = saved.find((s) => s.$hash === breedPick);
    if (!partner) { Alert.alert("Pick a partner", "Save 2+ seeds first, then pick one to breed with."); return; }
    setSeed(breedSeeds(seed, partner));
  }
  function onNew() { setSeed(makePrimordial(`Bloom #${saved.length + 2}`)); }
  function onLoad(s: UniversalSeed) { setSeed(s); }
  async function onDelete(h: string) {
    const next = saved.filter((s) => s.$hash !== h);
    setSaved(next); await saveSeeds(next);
  }

  return (
    <ScrollView style={st.root} contentContainerStyle={st.scroll}>
      <View style={st.header}>
        <Text style={st.kicker}>POCKET STUDIO · visual2d</Text>
        <Text style={st.title}>{seed.$name}</Text>
        <Text style={st.mono} numberOfLines={1}>{seed.$hash}</Text>
        <View style={st.lineageRow}>
          <Lineage label="op" value={seed.$lineage.operation} />
          <Lineage label="gen" value={String(seed.$lineage.generation)} />
          <Lineage label="parents" value={String(seed.$lineage.parents.length)} />
        </View>
      </View>

      {/* CANVAS PREVIEW */}
      <View style={st.canvasWrap}>
        <View style={st.canvas}>
          {dots.map((d, i) => (
            <View
              key={i}
              style={{
                position: "absolute",
                left: d.x - d.r, top: d.y - d.r,
                width: d.r * 2, height: d.r * 2,
                borderRadius: d.r, backgroundColor: d.color, opacity: d.opacity,
              }}
            />
          ))}
        </View>
        <Text style={st.canvasNote}>
          deterministic · xoshiro256** seeded from $hash · {dots.length} primitives
        </Text>
      </View>

      {/* ACTION BAR */}
      <View style={st.actions}>
        <ActionBtn label="Grow" tone="accent" onPress={onGrow} />
        <ActionBtn label="Mutate" tone="violet" onPress={onMutate} />
        <ActionBtn label="Breed" tone="warn" onPress={onBreed} />
        <ActionBtn label="Save" tone="ghost" onPress={onSave} />
      </View>
      <View style={st.actionsRow2}>
        <ActionBtn label="New" tone="ghost" onPress={onNew} />
        <ActionBtn label={showJson ? "Hide JSON" : "Show JSON"} tone="ghost" onPress={() => setShowJson((v) => !v)} />
      </View>

      {/* MUTATION RATE */}
      <Section title="Mutation Rate">
        <View style={st.row}>
          <Text style={st.value}>{mutationRate.toFixed(2)}</Text>
          <Slider min={0.01} max={0.5} step={0.01} value={mutationRate} onChange={setMutationRate} />
        </View>
        <Text style={st.dim}>Gaussian additive σ scales with this rate.</Text>
      </Section>

      {/* GENES */}
      <Section title="Genes">
        {Object.keys(seed.genes).map((k) => {
          const g = seed.genes[k];
          if (g.type === "scalar") {
            return (
              <View key={k} style={st.gene}>
                <View style={st.geneHead}>
                  <Text style={st.geneName}>{k}</Text>
                  <View style={st.typePill}><Text style={st.typePillText}>scalar</Text></View>
                  <Text style={st.value}>{g.value.toFixed(2)}</Text>
                </View>
                <Slider min={g.min} max={g.max} step={(g.max - g.min) / 100}
                  value={g.value} onChange={(v) => updateScalar(k, v)} />
              </View>
            );
          }
          if (g.type === "categorical") {
            return (
              <View key={k} style={st.gene}>
                <View style={st.geneHead}>
                  <Text style={st.geneName}>{k}</Text>
                  <View style={st.typePill}><Text style={st.typePillText}>categorical</Text></View>
                </View>
                <View style={st.chipsWrap}>
                  {g.choices.map((c) => {
                    const active = g.value === c;
                    return (
                      <Pressable key={c} onPress={() => updateCategorical(k, c)}
                        style={[st.chip, active && st.chipActive]}>
                        <Text style={[st.chipText, active && st.chipTextActive]}>{c}</Text>
                      </Pressable>
                    );
                  })}
                </View>
              </View>
            );
          }
          // vector (RGB)
          return (
            <View key={k} style={st.gene}>
              <View style={st.geneHead}>
                <Text style={st.geneName}>{k}</Text>
                <View style={st.typePill}><Text style={st.typePillText}>vector·rgb</Text></View>
                <View style={[st.swatch, { backgroundColor: rgb(g.value) }]} />
              </View>
              {["R", "G", "B"].map((label, i) => (
                <View key={label} style={st.row}>
                  <Text style={st.channel}>{label}</Text>
                  <Slider min={0} max={1} step={0.01} value={g.value[i]}
                    onChange={(v) => updateVector(k, i, v)} />
                  <Text style={st.value}>{g.value[i].toFixed(2)}</Text>
                </View>
              ))}
            </View>
          );
        })}
      </Section>

      {/* BREED PARTNER */}
      <Section title={`Breed Partner (${saved.length} saved)`}>
        {saved.length === 0 && <Text style={st.dim}>Save seeds to enable breeding.</Text>}
        <View style={st.savedWrap}>
          {saved.map((s) => {
            const active = breedPick === s.$hash;
            return (
              <Pressable key={s.$hash} style={[st.savedCard, active && st.savedActive]}
                onPress={() => setBreedPick(s.$hash)}>
                <Text style={st.savedName} numberOfLines={1}>{s.$name}</Text>
                <Text style={st.savedHash} numberOfLines={1}>{s.$hash.slice(7, 19)}…</Text>
                <View style={st.savedFoot}>
                  <Text style={st.savedDim}>g{s.$lineage.generation} · {s.$lineage.operation}</Text>
                  <Pressable onPress={() => onLoad(s)}><Text style={st.savedAction}>load</Text></Pressable>
                  <Pressable onPress={() => onDelete(s.$hash)}><Text style={st.savedDel}>×</Text></Pressable>
                </View>
              </Pressable>
            );
          })}
        </View>
      </Section>

      {/* JSON */}
      {showJson && (
        <Section title="UniversalSeed JSON">
          <TextInput
            value={JSON.stringify(seed, null, 2)}
            multiline editable={false}
            style={st.json}
          />
        </Section>
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

// ===================== Inline subcomponents =====================
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={st.section}>
      <Text style={st.sectionTitle}>{title}</Text>
      <View style={st.sectionBody}>{children}</View>
    </View>
  );
}
function Lineage({ label, value }: { label: string; value: string }) {
  return (
    <View style={st.lin}>
      <Text style={st.linLabel}>{label}</Text>
      <Text style={st.linValue}>{value}</Text>
    </View>
  );
}
function ActionBtn({ label, onPress, tone }: { label: string; onPress: () => void; tone: "accent" | "violet" | "warn" | "ghost" }) {
  const bg = tone === "accent" ? ACCENT : tone === "violet" ? ACCENT_2 : tone === "warn" ? WARN : PANEL_2;
  const fg = tone === "ghost" ? TEXT : BG;
  return (
    <TouchableOpacity onPress={onPress} style={[st.actionBtn, { backgroundColor: bg, borderColor: tone === "ghost" ? BORDER : bg }]}>
      <Text style={[st.actionText, { color: fg }]}>{label}</Text>
    </TouchableOpacity>
  );
}
function Slider({ min, max, step, value, onChange }: { min: number; max: number; step: number; value: number; onChange: (v: number) => void }) {
  const [w, setW] = useState(220);
  const t = (value - min) / (max - min);
  return (
    <View
      onLayout={(e) => setW(e.nativeEvent.layout.width)}
      style={st.slider}
      onStartShouldSetResponder={() => true}
      onMoveShouldSetResponder={() => true}
      onResponderMove={(e) => {
        const x = e.nativeEvent.locationX;
        const ratio = Math.max(0, Math.min(1, x / w));
        let v = min + ratio * (max - min);
        v = Math.round(v / step) * step;
        onChange(Math.max(min, Math.min(max, v)));
      }}
      onResponderGrant={(e) => {
        const x = e.nativeEvent.locationX;
        const ratio = Math.max(0, Math.min(1, x / w));
        let v = min + ratio * (max - min);
        v = Math.round(v / step) * step;
        onChange(Math.max(min, Math.min(max, v)));
      }}
    >
      <View style={st.sliderTrack} />
      <View style={[st.sliderFill, { width: `${t * 100}%` }]} />
      <View style={[st.sliderThumb, { left: `${t * 100}%` }]} />
    </View>
  );
}

// ===================== Styles =====================
const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  scroll: { paddingBottom: 60 },
  header: { paddingHorizontal: 18, paddingTop: 56, paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: BORDER },
  kicker: { color: ACCENT, fontSize: 10, letterSpacing: 2, marginBottom: 6 },
  title: { color: TEXT, fontSize: 26, fontWeight: "800", letterSpacing: -0.5 },
  mono: { color: DIM, fontSize: 11, fontFamily: "monospace", marginTop: 4 },
  lineageRow: { flexDirection: "row", marginTop: 12 },
  lin: { backgroundColor: PANEL_2, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 6, marginRight: 8, borderWidth: 1, borderColor: BORDER },
  linLabel: { color: DIM, fontSize: 9, letterSpacing: 1 },
  linValue: { color: TEXT, fontSize: 12, fontWeight: "700" },

  canvasWrap: { padding: 18, alignItems: "center" },
  canvas: {
    width: 280, height: 280, backgroundColor: "#0a0f1c",
    borderRadius: 16, borderWidth: 1, borderColor: BORDER, overflow: "hidden",
  },
  canvasNote: { color: DIM, fontSize: 10, marginTop: 8 },

  actions: { flexDirection: "row", paddingHorizontal: 14, marginTop: 4 },
  actionsRow2: { flexDirection: "row", paddingHorizontal: 14, marginTop: 8 },
  actionBtn: {
    flex: 1, marginHorizontal: 4, paddingVertical: 12, borderRadius: 10,
    alignItems: "center", borderWidth: 1,
  },
  actionText: { fontWeight: "800", letterSpacing: 0.3, fontSize: 13 },

  section: { paddingHorizontal: 14, marginTop: 18 },
  sectionTitle: { color: TEXT, fontSize: 14, fontWeight: "700", marginBottom: 8, paddingHorizontal: 4, letterSpacing: 0.3 },
  sectionBody: { backgroundColor: PANEL, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: BORDER },

  gene: { marginBottom: 14, paddingBottom: 10, borderBottomWidth: 1, borderBottomColor: BORDER },
  geneHead: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  geneName: { color: TEXT, fontWeight: "700", fontSize: 13, flex: 1 },
  typePill: { backgroundColor: PANEL_2, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, marginRight: 8 },
  typePillText: { color: ACCENT_2, fontSize: 9, fontWeight: "700", letterSpacing: 0.5 },
  value: { color: ACCENT, fontFamily: "monospace", fontSize: 12, minWidth: 44, textAlign: "right" },
  channel: { color: DIM, width: 14, fontSize: 11, fontWeight: "700" },
  swatch: { width: 22, height: 22, borderRadius: 6, borderWidth: 1, borderColor: BORDER },

  row: { flexDirection: "row", alignItems: "center", marginVertical: 4 },
  slider: { flex: 1, height: 32, justifyContent: "center", marginHorizontal: 6, position: "relative" },
  sliderTrack: { position: "absolute", left: 0, right: 0, height: 4, backgroundColor: PANEL_2, borderRadius: 2 },
  sliderFill: { position: "absolute", left: 0, height: 4, backgroundColor: ACCENT, borderRadius: 2 },
  sliderThumb: { position: "absolute", width: 18, height: 18, borderRadius: 9, backgroundColor: ACCENT, marginLeft: -9, top: 7 },

  chipsWrap: { flexDirection: "row", flexWrap: "wrap" },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, marginRight: 6, marginBottom: 6, borderWidth: 1, borderColor: BORDER, backgroundColor: PANEL_2 },
  chipActive: { backgroundColor: ACCENT, borderColor: ACCENT },
  chipText: { color: TEXT, fontSize: 12, fontWeight: "600" },
  chipTextActive: { color: BG, fontWeight: "800" },

  savedWrap: { flexDirection: "row", flexWrap: "wrap" },
  savedCard: { width: "48%", margin: "1%", backgroundColor: PANEL_2, borderRadius: 10, padding: 10, borderWidth: 1, borderColor: BORDER },
  savedActive: { borderColor: WARN },
  savedName: { color: TEXT, fontSize: 13, fontWeight: "700" },
  savedHash: { color: DIM, fontSize: 10, fontFamily: "monospace", marginTop: 2 },
  savedFoot: { flexDirection: "row", marginTop: 6, alignItems: "center" },
  savedDim: { color: DIM, fontSize: 10, flex: 1 },
  savedAction: { color: ACCENT, fontSize: 11, fontWeight: "700", marginRight: 8 },
  savedDel: { color: "#ef4444", fontSize: 16, fontWeight: "900" },

  dim: { color: DIM, fontSize: 11 },
  json: { color: TEXT, backgroundColor: BG, borderWidth: 1, borderColor: BORDER, borderRadius: 8, padding: 10, fontFamily: "monospace", fontSize: 11, minHeight: 200, textAlignVertical: "top" },
});
