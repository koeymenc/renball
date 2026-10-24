# [PROJECT TITLE]

**Author:** Can Luca Köymen
**Site:** [renball.com](https://renball.com)
**Date:** [Month Year]

---

## Abstract

[3–5 sentences. State the question, the data, the method, the headline result.]

---

## 1. Research Question

> [State the question in one clear sentence.]

**Null hypothesis (H₀):** [If applicable.]
**Alternative hypothesis (H₁):** [If applicable.]

---

## 2. Data

**Sources:**
- [Source 1 — URL]
- [Source 2 — URL]

**Sample size:** [N matches / players / shots]
**Time period:** [Start season] to [End season]
**Competitions:** [PL, La Liga, Serie A, Bundesliga, Ligue 1]

**Cleaning & filtering decisions:**
- [Decision 1 and why]
- [Decision 2 and why]

---

## 3. Methodology

**Approach:** [Short narrative of what was done.]

**Statistical tests:**
- [Test name] — used to compare [groups]. Assumptions: [list].
- [Test name] — used to compare [groups]. Assumptions: [list].

**Software stack:**
- Python 3.x
- pandas, numpy, statsmodels, scipy, matplotlib
- [Other packages used]

---

## 4. Results

### 4.1 [Sub-result 1]

[Describe what the chart/table shows. Include numbers.]

| Group | N | Conversion Rate | 95% CI |
|---|---|---|---|
| [Group A] | [n] | [%] | [CI] |
| [Group B] | [n] | [%] | [CI] |

**Test result:** Z = [value], p = [value]
**Effect size:** [difference with 95% CI]. **Power / MDE:** [smallest effect this sample could detect at 80% power]. **Equivalence (if claiming "no difference"):** [TOST margin and result].
**Interpretation:** [Plain English.]

### 4.2 [Sub-result 2]

[Same structure.]

---

## 5. Practical takeaways

| Audience | Takeaway | Evidence |
|---|---|---|
| Coaches — training & tactics | [From data.json takeaways] | [Strong / Moderate / Exploratory] |
| Managers — match-day decisions | [ … ] | [ … ] |
| Clubs — recruitment & contracts | [ … or "No defensible claim"] | — |
| Agents — positioning a player | [ … ] | [ … ] |

### Evidence labels

- **Strong** — large sample; the 95% interval excludes zero (or, for a "no effect" claim, sits inside a pre-stated equivalence margin); survives the main controls; holds across leagues or seasons.
- **Moderate** — consistent direction and plausible size, with one gap: the interval touches zero, a single method or sample, or only partial replication.
- **Exploratory** — small samples, an interval that comfortably includes zero, untested confounders, or a pattern found by looking rather than tested. A question worth asking, not advice.

---

## 6. Limitations

- [Limitation 1 — e.g. excluded knockout/extra-time penalties]
- [Limitation 2 — e.g. no shootout data]
- [Limitation 3 — e.g. unobserved confounders like fatigue, score state]

---

## 7. Conclusion

[2–3 paragraph wrap-up. What the result means, what it doesn't mean, what's next.]

---

## References

1. [Source name — Year — URL]
2. [Source name — Year — URL]

---

*Methodology document generated alongside [analysis.html](analysis.html) and [slides.pdf](slides.pdf). Source code available in the [/code](code/) folder.*
