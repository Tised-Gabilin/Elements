# Elements: The Story of Matter Across Cosmic Time

**Slogan:** *From the first hydrogen atom to gold in neutron-star collisions.*

---

## 1. The Problem

**Current pain:** Most periodic table apps are still reference grids with filters, search, and quizzes. They teach facts but not origin story. Learners can memorize atomic numbers without understanding the timeline: what formed minutes after the Big Bang, what stars forge, and what only extreme events create.

**Gap in market:** Existing apps are mostly static or quiz-first. Very few offer a visually coherent, time-based narrative of element formation with interactive, explorable 3D visual language.

**Target users:**
- Students (middle school, high school, university intro chemistry/physics)
- Teachers needing a visually engaging classroom explainer
- Science-curious adults who consume educational content on social/video platforms
- Parents looking for high-quality STEM apps

**User desire:** "Show me where this element came from in the universe" is stronger than "show me row/column metadata." This concept can turn chemistry recall into a visual story.

---

## 2. Market Validation

### 2.1 Pipeline Signal (internal scripts)

Run date: 2026-05-12

- Pipeline run succeeded after adding Education to [config/research_pipeline.json](config/research_pipeline.json).
- App Store category 185 (Education) returned no parseable chart entries in AppMagic for this workflow.
- Direct message from fetched AppMagic page: "The category you've selected is not available in this store."
- Implication: for this idea, direct education competitor analysis must be hybrid (pipeline + manual external source).

### 2.2 Direct Competitor Signal (iTunes API, 15-country sampling)

Search method: iTunes Search API across US, CA, GB, DE, FR, AU, CH, IL, TR, MX, BR, TW, JP, KR, IN with queries around "periodic table" and "chemistry periodic table".

| App | Price | Rating (count) | Geo Presence (15-country sample) | What They Show | Monetization Pattern |
|---|---|---:|---:|---|---|
| Periodic Table: Chemistry 2026 | Free | 4.81 (5,129) | 15/15 | Interactive periodic table + element data | Free entry (likely ads/IAP) |
| Chemistry. Periodic table. AI | Free | 4.87 (2,630) | 15/15 | Element cards + chemistry helper | Free entry (likely IAP unlocks) |
| Periodic Table Quiz | Free | 4.78 (387) | 15/15 | Quiz-focused table learning | Free + quiz progression |
| The Elements by Theodore Gray | $9.99 | 4.58 (121) | 15/15 | Premium visual encyclopedia style | Paid upfront |
| EleMend- 3D Periodic Table | Free | 4.67 (67) | 15/15 | 3D-focused table exploration | Free entry (likely upgrade path) |
| ChemistryMaster Periodic Table | Free | 4.92 (52) | 15/15 | Table + chemistry references | Free entry |
| K12 Periodic Table of the Elements | Free | 4.02 (45) | 15/15 | School-oriented educational table | Free entry |
| Periodic Table of Elements+ | Free | 4.60 (42) | 15/15 | Compact element lookup tool | Free entry |

**What this means:**
- Competitors clearly exist.
- Market baseline is overwhelmingly "free app first." 
- There is at least one successful premium precedent at $9.99 (The Elements by Theodore Gray), which strongly validates your proposed one-time unlock direction.

### 2.3 Popularity by Location (search presence signal)

Across sampled storefronts, these names repeatedly appear near the top: "Periodic Table: Chemistry 2026", "Periodic Table Quiz", and "Chemistry. Periodic table. AI".

- US/CA/GB/AU/TR/MX: strong recurring visibility of mainstream periodic-table apps.
- DE/CH: localized chemistry brands also appear (example: German-language periodic table variants).
- JP/KR/TW/IN: periodic-table demand exists, but localized presentation quality likely matters for conversion.

This is not chart-rank proof, but it is strong availability and discoverability signal across diverse geographies.

---

## 3. The Solution

### 3.1 Product Concept

A timeline-native education app that visualizes when and where elements formed during cosmic history.

Narrative arc:
1. Big Bang nucleosynthesis: H, He, trace Li
2. First stars ignition: stellar fusion pathways
3. Supernova nucleosynthesis: heavier elements
4. Neutron-star mergers / r-process: gold, platinum and other heavy nuclei
5. Planetary chemistry context: why Earth has the elemental mix we observe

### 3.2 Core UX

- Horizontal cosmic timeline with major era checkpoints
- Jump navigation: users can jump to any era instantly
- Element nodes mapped to first significant production era
- Tap element -> full visual card:
  - Atomic number, mass, period/group
  - Protons/electrons/neutrons
  - Electron shell model
  - State at STP (gas/liquid/solid)
  - Natural origin pathways (stellar, supernova, r-process, synthetic)

### 3.3 Visual System (critical differentiation)

Your concern is valid: "just atoms" can become visually repetitive. We solve that by using a **material-language approach**, not a single atom style.

- Gases: volumetric, translucent, flowing motion fields
- Metals: reflective crystalline surfaces with lattice motifs
- Liquids (e.g., Bromine, Mercury): fluid shaders, viscosity cues
- Nonmetals: textured, reactive visual behavior
- Radioactives/synthetics: unstable pulse and decay motifs

The atom model remains data-accurate, but each element also gets a "material identity" so visuals stay memorable.

---

## 4. Revenue Model

## Option A (your baseline)

- Free: first 7 elements + first timeline chapter
- Paid unlock: $10 one-time for full 118-element experience
- Best for: clear value message, no subscription fatigue

## Option B (conversion-optimized)

- Free: first 12 elements + 2 timeline eras
- One-time full unlock: $7.99
- Optional $2.99 visual pack (cinematic themes)
- Best for: improving conversion from hesitant users while preserving lifetime model

## Option C (education-institution friendly)

- Free: first 7 elements
- One-time personal unlock: $9.99
- Classroom bundle: $19.99 (teacher mode, projector-friendly scenes, worksheet export)
- Best for: B2C + small B2B/education creator angle

### Recommended pricing strategy

Start with **Option A** for launch because it aligns with your concept and has precedent (premium chemistry app at ~$10). If conversion is low after first 4-6 weeks, test Option B.

---

## 5. Technical Implementation

### 5.1 Stack (MVP)

| Layer | Proposed Choice |
|---|---|
| Client | iOS first (SwiftUI + SceneKit/RealityKit) or Unity if cross-platform 3D velocity is higher priority |
| Data | Local JSON bundle for element data + origin metadata |
| Rendering | Hybrid: generated textures + procedural shaders + lightweight 3D assets |
| Monetization | StoreKit one-time non-consumable purchase |
| Offline | Full offline content after install |

### 5.2 Content Pipeline (Image 2 -> 3D)

1. Generate style-consistent concept sheets per element class
2. Convert selected assets to mesh/reference with 3D tools
3. Normalize mesh complexity and materials for mobile performance
4. Add procedural effects to avoid each element feeling like a static icon

### 5.3 Performance Constraints

- Keep mobile scene budgets strict (draw calls, texture memory, overdraw)
- Prefer reusable shader families by element class
- Limit per-element custom geometry in MVP

### 5.4 MVP Scope Recommendation

Ship a **very tight prototype: 10 elements across 3 eras**.

Prototype coverage:
- Era 1: Big Bang nucleosynthesis (H, He, Li)
- Era 2: Stellar forging (C, O, Ne, Si, Fe)
- Era 3: Heavy-element pathway (Au, U, plus one synthetic example)

This is enough to prove the timeline mechanic, visual language, and interaction model without committing to full 118-element production.

---

## 6. Risks and Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| Visual repetition across elements | High | Material-language system + class-based shader design + era-specific environments |
| High art production overhead | High | Start with 10 prototype elements, then expand only after visual system proves itself |
| Scientific oversimplification criticism | Medium | Add source notes and "how we simplified" labels per scene |
| Weak conversion from free to paid | Medium | Gate by narrative depth (eras), not only by element count; test Option B if needed |
| Competitor discoverability pressure | Medium | Strong ASO with "timeline", "origin of elements", "3D chemistry" positioning |

---

## 7. Go-To-Market

### 7.1 Positioning

"The periodic table as a cosmic story, not a spreadsheet."

### 7.2 ASO keywords

- EN: periodic table 3d, chemistry timeline, elements origin, nucleosynthesis, atom visualizer
- DE: periodensystem 3d, chemie elemente, nukleosynthese
- TR: periyodik tablo 3d, elementler, kimya uygulamasi
- ES: tabla periodica 3d, origen de los elementos, quimica

### 7.3 Launch channels

- Short cinematic clips of era transitions on X/TikTok/YouTube Shorts
- Teacher/education creator outreach
- Side-by-side comparison creative: static table app vs timeline experience

---

## 8. Build Recommendation

## Should we build it?

**Yes, with a scoped MVP.**

### Why yes

- Competitor landscape is real but mostly table/quiz-first.
- There is space for a premium visual narrative product.
- Your one-time pricing thesis is validated by existing paid precedent.
- Concept has strong shareability potential if visuals are exceptional.

### Conditions for success

1. Do not ship as a generic periodic table clone.
2. Prioritize visual identity and narrative flow over breadth.
3. Launch with fewer elements but much higher quality.

### Decision

**Proceed to a 10-element discovery prototype (2-3 weeks) + art pipeline spike before any broader production.**

---

## 9. Competitor/Business Checklist Coverage

- Should we build it: **Yes (scoped MVP).**
- Do we have competitors: **Yes (many direct periodic-table apps).**
- Their pricing models: **Mostly free-first; one notable paid app at $9.99.**
- What they are showing: **Table lookup, quizzes, some limited 3D.**
- Popularity by locations: **Recurring discoverability across US/CA/GB/DE/FR/AU/CH/IL/TR/MX/BR/TW/JP/KR/IN search sampling.**

---

## 10. Next Execution Step

Create a visual prototype with exactly 10 elements and 3 eras:
- Era 1: Big Bang (H, He, Li)
- Era 2: Stellar forging (C, O, Ne, Si, Fe)
- Era 3: Heavy elements (Au, U)

If this prototype feels "wow" in user testing, expand to 20-25 elements before considering any wider production plan.
