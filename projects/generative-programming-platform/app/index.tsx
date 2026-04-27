import React, { useMemo, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Alert,
} from "react-native";

// ----- Paradigm / GSPL — Mobile Planning Surface -----
// Until Kahlil confirms the build direction, this screen is a planning
// dashboard surfacing the deep technical analysis of the platform plus
// the open questions we need to answer to begin building the mobile app.

const GENE_TYPES = [
  { n: 1, name: "scalar", encodes: "bounded continuous numeric" },
  { n: 2, name: "categorical", encodes: "discrete choice" },
  { n: 3, name: "vector", encodes: "fixed-D numeric tuple" },
  { n: 4, name: "expression", encodes: "runtime-evaluated math AST" },
  { n: 5, name: "struct", encodes: "composite record" },
  { n: 6, name: "array", encodes: "ordered homogeneous collection" },
  { n: 7, name: "graph", encodes: "typed nodes + edges" },
  { n: 8, name: "topology", encodes: "manifold / SDF surface" },
  { n: 9, name: "temporal", encodes: "time-varying signal / ADSR" },
  { n: 10, name: "regulatory", encodes: "gene-expression control net" },
  { n: 11, name: "field", encodes: "continuous spatial distribution" },
  { n: 12, name: "symbolic", encodes: "grammar / dialogue tree" },
  { n: 13, name: "quantum", encodes: "superposition + entanglement" },
  { n: 14, name: "gematria", encodes: "numerological encoding" },
  { n: 15, name: "resonance", encodes: "harmonic frequency profile" },
  { n: 16, name: "dimensional", encodes: "embedding-space coords" },
  { n: 17, name: "sovereignty", encodes: "ECDSA P-256 ownership (immutable)" },
];

const LAYERS = [
  { n: 7, name: "Studio", desc: "React + WebGL + WebRTC" },
  { n: 6, name: "Intelligence", desc: "GSPL Agent + 8 sub-agents" },
  { n: 5, name: "Evolution", desc: "GA + MAP-Elites + CMA-ES" },
  { n: 4, name: "Engines", desc: "26 Domain Pipelines" },
  { n: 3, name: "GSPL", desc: "Lexer → Parser → Typing → VM" },
  { n: 2, name: "Seeds", desc: "UniversalSeed + 17 Gene Types" },
  { n: 1, name: "Kernel", desc: "xoshiro256** + FIM + Tick" },
];

const SUB_AGENTS = [
  "SeedArchitect",
  "EvolutionStrategist",
  "FitnessCrafter",
  "DomainExpert",
  "QualityAssessor",
  "CompositionPlanner",
  "Optimizer",
  "CreativeDirector",
];

const DOMAINS_BUILT = [
  "character", "sprite", "music", "audio", "visual2d",
  "geometry3d", "animation", "procedural", "narrative", "ui",
  "physics", "ecosystem", "game", "fullgame", "alife",
];

const DOMAINS_PLANNED = [
  "shader", "particle", "typography", "architecture", "vehicle",
  "furniture", "fashion", "robotics", "circuit", "food", "choreography",
];

const CANDIDATES = [
  { id: "A", name: "Pocket Studio", tag: "creator-first", desc: "Touch-optimized 17-gene editor. Tap to grow. Mutate / breed / publish." },
  { id: "B", name: "Marketplace", tag: "consumer-first", desc: "Browse / fork / collect signed .gseed packages. Lineage tree visualizer." },
  { id: "C", name: "GSPL Companion", tag: "developer-first", desc: "Inspect seeds, watch evolution runs, chat with the 8 sub-agents." },
  { id: "D", name: "The Garden", tag: "GSPL 5.0 / poetic", desc: "Seeds as living plants. Garden Mind health 0–100. Cross-pollination." },
  { id: "E", name: "Hybrid", tag: "recommended", desc: "Garden home → Pocket Studio editor → Marketplace → Companion tab." },
];

const QUESTIONS = [
  "Audience priority — creators, collectors, or developers first?",
  "Online vs on-device — embed kernel + 1–2 engines, or thin client to backend?",
  "Sovereignty UX — generate ECDSA P-256 keypair on-device (Secure Enclave / Keystore) or pair with desktop?",
  "Mobile-tier-1 engines — visual2d, audio, character, narrative? Defer fullgame / geometry3d?",
  "Marketplace scope — read-only browse, or full publish flow with on-device signing?",
  "Garden Mind — primary tab or ambient assistant?",
];

const SEVEN_AXES = [
  "Signed", "Typed", "Lineage-tracked", "Graph-structured",
  "Confidence-bearing", "Rollback-able", "Differentiable",
];

export default function Index() {
  const [pick, setPick] = useState<string | null>("E");
  const [note, setNote] = useState("");

  const stats = useMemo(
    () => [
      { v: "26", l: "Domains" },
      { v: "17", l: "Gene Types" },
      { v: "8", l: "Sub-Agents" },
      { v: "7", l: "Layers" },
      { v: "482", l: "Tests" },
      { v: "85K", l: "LOC" },
    ],
    []
  );

  return (
    <ScrollView style={s.root} contentContainerStyle={s.scroll}>
      {/* HERO */}
      <View style={s.hero}>
        <Text style={s.kicker}>11vatedTech LLC · Kahlil Stephens · April 2026</Text>
        <Text style={s.title}>Paradigm</Text>
        <Text style={s.subtitle}>
          A Genetic Operating System where every digital artifact is a living seed —
          bred, mutated, evolved, and composed.
        </Text>
        <View style={s.tagRow}>
          <View style={s.tag}><Text style={s.tagText}>GSPL 5.0</Text></View>
          <View style={s.tag}><Text style={s.tagText}>UniversalSeed</Text></View>
          <View style={s.tag}><Text style={s.tagText}>ECDSA P-256</Text></View>
          <View style={s.tag}><Text style={s.tagText}>xoshiro256**</Text></View>
        </View>
      </View>

      {/* STATS */}
      <View style={s.statsRow}>
        {stats.map((x) => (
          <View key={x.l} style={s.statCard}>
            <Text style={s.statV}>{x.v}</Text>
            <Text style={s.statL}>{x.l}</Text>
          </View>
        ))}
      </View>

      {/* THESIS */}
      <Section title="The Thesis">
        <Text style={s.body}>
          Paradigm introduces <Text style={s.b}>Genetically Organized Evolution</Text>:
          every digital artifact is encoded as a living genetic blueprint — a seed.
          Seeds are not files. They unfold through developmental stages the way a
          fertilized cell unfolds into an organism. <Text style={s.b}>Same seed +
          same RNG + same engine = bit-identical output, forever.</Text> From that
          determinism comes breeding, lineage, cryptographic sovereignty,
          marketplace royalties, and cross-domain composition via category theory.
        </Text>
      </Section>

      {/* 7 LAYERS */}
      <Section title="The 7-Layer Architecture">
        {LAYERS.map((L) => (
          <View key={L.n} style={s.layerRow}>
            <View style={s.layerN}><Text style={s.layerNText}>L{L.n}</Text></View>
            <View style={{ flex: 1 }}>
              <Text style={s.layerName}>{L.name}</Text>
              <Text style={s.layerDesc}>{L.desc}</Text>
            </View>
          </View>
        ))}
      </Section>

      {/* 17 GENES */}
      <Section title="The 17 Kernel Gene Types">
        <Text style={s.note}>
          Locked by spec/02-gene-system.md. Each ships its own validate / mutate /
          crossover / distance / canonicalize / repair operators.
        </Text>
        {GENE_TYPES.map((g) => (
          <View key={g.n} style={s.geneRow}>
            <Text style={s.geneN}>{String(g.n).padStart(2, "0")}</Text>
            <Text style={s.geneName}>{g.name}</Text>
            <Text style={s.geneDesc} numberOfLines={2}>{g.encodes}</Text>
          </View>
        ))}
      </Section>

      {/* DOMAINS */}
      <Section title="26 Domains">
        <Text style={s.subhead}>Built / shipping</Text>
        <View style={s.chipsWrap}>
          {DOMAINS_BUILT.map((d) => (
            <View key={d} style={[s.chip, s.chipBuilt]}>
              <Text style={s.chipText}>{d}</Text>
            </View>
          ))}
        </View>
        <Text style={[s.subhead, { marginTop: 12 }]}>Planned</Text>
        <View style={s.chipsWrap}>
          {DOMAINS_PLANNED.map((d) => (
            <View key={d} style={[s.chip, s.chipPlanned]}>
              <Text style={s.chipTextDim}>{d}</Text>
            </View>
          ))}
        </View>
      </Section>

      {/* INTELLIGENCE */}
      <Section title="Intelligence Layer — 8 Sub-Agents">
        <View style={s.grid2}>
          {SUB_AGENTS.map((a) => (
            <View key={a} style={s.agentCard}>
              <Text style={s.agentName}>{a}</Text>
            </View>
          ))}
        </View>
        <Text style={[s.note, { marginTop: 10 }]}>
          + Garden Mind (GSPL 5.0): understandIntent → predictGrowth →
          detectDiseases → suggestCrossPollination → analyzeGarden (health 0–100).
        </Text>
      </Section>

      {/* 7 AXES */}
      <Section title="The 7-Axis Substrate Discipline">
        <View style={s.chipsWrap}>
          {SEVEN_AXES.map((x) => (
            <View key={x} style={[s.chip, s.chipAxis]}>
              <Text style={s.chipText}>{x}</Text>
            </View>
          ))}
        </View>
        <Text style={[s.note, { marginTop: 10 }]}>
          "A six-axis substrate is a different thing — it is not GSPL." —
          MVP_DEFINITION.md
        </Text>
      </Section>

      {/* CANDIDATES */}
      <Section title="Mobile App — Candidate Directions">
        <Text style={s.note}>
          Tap the candidate you want to pursue. We&rsquo;ll scope it together
          before building.
        </Text>
        {CANDIDATES.map((c) => {
          const active = pick === c.id;
          return (
            <TouchableOpacity
              key={c.id}
              onPress={() => setPick(c.id)}
              activeOpacity={0.85}
              style={[s.candCard, active && s.candCardActive]}
            >
              <View style={s.candHead}>
                <View style={[s.candBadge, active && s.candBadgeActive]}>
                  <Text style={[s.candBadgeText, active && s.candBadgeTextActive]}>
                    {c.id}
                  </Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.candName}>{c.name}</Text>
                  <Text style={s.candTag}>{c.tag}</Text>
                </View>
                {active && <Text style={s.candCheck}>SELECTED</Text>}
              </View>
              <Text style={s.candDesc}>{c.desc}</Text>
            </TouchableOpacity>
          );
        })}
      </Section>

      {/* QUESTIONS */}
      <Section title="Open Planning Questions">
        {QUESTIONS.map((q, i) => (
          <View key={i} style={s.qRow}>
            <Text style={s.qN}>{i + 1}</Text>
            <Text style={s.qText}>{q}</Text>
          </View>
        ))}
      </Section>

      {/* NOTES INPUT */}
      <Section title="Your Direction">
        <Text style={s.note}>
          Drop your decisions here — audience, on-device vs thin client, mobile
          tier-1 engines, sovereignty UX, marketplace scope.
        </Text>
        <TextInput
          value={note}
          onChangeText={setNote}
          multiline
          placeholder="e.g. Start with Candidate E. Tier-1 engines: visual2d + audio. On-device keypair via Secure Enclave..."
          placeholderTextColor="#6b7280"
          style={s.input}
        />
        <TouchableOpacity
          style={s.cta}
          onPress={() => {
            const sel = CANDIDATES.find((c) => c.id === pick);
            Alert.alert(
              "Planning captured",
              `Direction: ${sel ? sel.name : "(none)"}\n\nNotes: ${note || "(none)"}\n\nReady to begin building when you are.`
            );
          }}
        >
          <Text style={s.ctaText}>Lock In Direction</Text>
        </TouchableOpacity>
      </Section>

      <View style={s.footer}>
        <Text style={s.footerText}>
          Paradigm GSPL Platform · v1.0.0
        </Text>
        <Text style={s.footerDim}>
          Analysis grounded in Paradigm, PAradigm-reference, GSPL, GSPL-Paradigm,
          Paradigm_GSPL_OS · Full doc: planning/PARADIGM_GSPL_ANALYSIS.md
        </Text>
      </View>
    </ScrollView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={s.section}>
      <Text style={s.sectionTitle}>{title}</Text>
      <View style={s.sectionBody}>{children}</View>
    </View>
  );
}

const BG = "#070b14";
const PANEL = "#0f1626";
const PANEL_2 = "#141d33";
const BORDER = "#1f2a44";
const TEXT = "#e6ebf5";
const DIM = "#8b95ad";
const ACCENT = "#7cf0c5";
const ACCENT_2 = "#a78bfa";

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  scroll: { paddingBottom: 64 },

  hero: {
    paddingHorizontal: 22,
    paddingTop: 64,
    paddingBottom: 28,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
  },
  kicker: { color: ACCENT, fontSize: 11, letterSpacing: 2, textTransform: "uppercase", marginBottom: 10 },
  title: { color: TEXT, fontSize: 48, fontWeight: "800", letterSpacing: -1.5 },
  subtitle: { color: DIM, fontSize: 15, lineHeight: 22, marginTop: 10 },
  tagRow: { flexDirection: "row", flexWrap: "wrap", marginTop: 16 },
  tag: {
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999,
    borderWidth: 1, borderColor: BORDER, marginRight: 8, marginBottom: 8,
  },
  tagText: { color: ACCENT_2, fontSize: 11, fontWeight: "600" },

  statsRow: {
    flexDirection: "row", flexWrap: "wrap",
    paddingHorizontal: 14, paddingTop: 16,
  },
  statCard: {
    width: "33.33%", paddingHorizontal: 8, paddingVertical: 10,
    alignItems: "center",
  },
  statV: { color: TEXT, fontSize: 22, fontWeight: "800" },
  statL: { color: DIM, fontSize: 11, marginTop: 2, letterSpacing: 1, textTransform: "uppercase" },

  section: { paddingHorizontal: 18, paddingTop: 28 },
  sectionTitle: {
    color: TEXT, fontSize: 18, fontWeight: "700", marginBottom: 12,
    letterSpacing: -0.3,
  },
  sectionBody: {
    backgroundColor: PANEL, borderRadius: 14, padding: 16,
    borderWidth: 1, borderColor: BORDER,
  },
  body: { color: TEXT, fontSize: 14, lineHeight: 22 },
  b: { color: ACCENT, fontWeight: "700" },
  note: { color: DIM, fontSize: 12, lineHeight: 18, marginBottom: 8 },
  subhead: { color: ACCENT_2, fontSize: 11, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 6 },

  layerRow: { flexDirection: "row", alignItems: "center", paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: BORDER },
  layerN: {
    width: 36, height: 36, borderRadius: 8,
    backgroundColor: PANEL_2, alignItems: "center", justifyContent: "center",
    marginRight: 12,
  },
  layerNText: { color: ACCENT, fontWeight: "800", fontSize: 12 },
  layerName: { color: TEXT, fontSize: 14, fontWeight: "700" },
  layerDesc: { color: DIM, fontSize: 12, marginTop: 1 },

  geneRow: { flexDirection: "row", alignItems: "center", paddingVertical: 6 },
  geneN: { color: ACCENT_2, fontFamily: "monospace", width: 30, fontSize: 12 },
  geneName: { color: TEXT, fontSize: 13, fontWeight: "700", width: 110 },
  geneDesc: { color: DIM, fontSize: 12, flex: 1 },

  chipsWrap: { flexDirection: "row", flexWrap: "wrap" },
  chip: {
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8,
    marginRight: 6, marginBottom: 6, borderWidth: 1,
  },
  chipBuilt: { backgroundColor: "#0d2418", borderColor: "#1f5538" },
  chipPlanned: { backgroundColor: PANEL_2, borderColor: BORDER },
  chipAxis: { backgroundColor: "#1c1535", borderColor: "#3a2d6b" },
  chipText: { color: TEXT, fontSize: 12, fontWeight: "600" },
  chipTextDim: { color: DIM, fontSize: 12 },

  grid2: { flexDirection: "row", flexWrap: "wrap" },
  agentCard: {
    width: "48%", margin: "1%",
    backgroundColor: PANEL_2, borderRadius: 10, padding: 12,
    borderWidth: 1, borderColor: BORDER,
  },
  agentName: { color: TEXT, fontWeight: "700", fontSize: 13 },

  candCard: {
    backgroundColor: PANEL_2, borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: BORDER, marginBottom: 10,
  },
  candCardActive: { borderColor: ACCENT, backgroundColor: "#0d1f1a" },
  candHead: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  candBadge: {
    width: 32, height: 32, borderRadius: 8,
    backgroundColor: BG, alignItems: "center", justifyContent: "center",
    borderWidth: 1, borderColor: BORDER, marginRight: 12,
  },
  candBadgeActive: { backgroundColor: ACCENT, borderColor: ACCENT },
  candBadgeText: { color: ACCENT, fontWeight: "800" },
  candBadgeTextActive: { color: BG },
  candName: { color: TEXT, fontSize: 15, fontWeight: "700" },
  candTag: { color: ACCENT_2, fontSize: 11, marginTop: 1 },
  candCheck: { color: ACCENT, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  candDesc: { color: DIM, fontSize: 13, lineHeight: 19 },

  qRow: { flexDirection: "row", paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: BORDER },
  qN: { color: ACCENT, width: 22, fontWeight: "800" },
  qText: { color: TEXT, fontSize: 13, lineHeight: 19, flex: 1 },

  input: {
    backgroundColor: BG, borderRadius: 10, padding: 12,
    borderWidth: 1, borderColor: BORDER, color: TEXT,
    minHeight: 110, textAlignVertical: "top", fontSize: 13,
  },
  cta: {
    marginTop: 12, backgroundColor: ACCENT, borderRadius: 10,
    paddingVertical: 14, alignItems: "center",
  },
  ctaText: { color: BG, fontWeight: "800", letterSpacing: 0.5 },

  footer: { padding: 22, alignItems: "center" },
  footerText: { color: TEXT, fontSize: 12, fontWeight: "700" },
  footerDim: { color: DIM, fontSize: 10, marginTop: 4, textAlign: "center" },
});
