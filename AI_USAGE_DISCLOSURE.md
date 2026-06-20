# AI Usage Disclosure

**Assessment:** Inside Airbnb Data Engineer Intern — Talent Assessment
**Organisation:** Experne'c Pvt Ltd
**Candidate:** Bavikaran
**Date:** 21 June 2026

---

## 1. Summary

Artificial intelligence coding assistance was used throughout this assessment to accelerate implementation, debug errors, and maintain code quality across a large multi-phase pipeline. All technical decisions, output validation, and analytical judgements were made by the candidate. The AI acted as a pair-programmer, not an autonomous agent.

---

## 2. Tools Used

| Tool | Version | Purpose |
|---|---|---|
| **Claude Code** (Anthropic) | Claude Sonnet 4.6 | Primary AI coding assistant — code generation, debugging, architecture guidance |

No other AI tools (ChatGPT, GitHub Copilot, Gemini, etc.) were used.

---

## 3. How AI Was Used

### 3.1 Code Generation

Claude Code was used to generate boilerplate and implementation code for:

- FastAPI route modules (`analytics.py`, endpoint handlers)
- Feature engineering scripts (`listing_features.py`, `clustering_features.py`, `host_features.py`)
- ML model training and evaluation pipelines (`train_price_model.py`, `evaluate_model.py`, `explain_model.py`)
- K-Means clustering modules (`cluster_listings.py`, `cluster_hosts.py`)
- Cluster profiling and naming logic (`cluster_profiles.py`, `host_cluster_profiles.py`)
- Cross-city transfer analysis (`cross_city_transfer.py`)
- Residual analysis scripts (`residual_analysis.py`)

In each case, the candidate reviewed the generated code, ran it, inspected the outputs, and directed corrections when results were incorrect or incomplete.

### 3.2 Debugging

AI assistance was used to diagnose and fix errors encountered during execution, including:

- `UnicodeEncodeError` on Windows when printing non-ASCII characters
- `KeyError` in cluster naming functions caused by mismatched aggregated column names
- Incorrect `_pick_k()` index reference (`iloc[1]` vs `iloc[0]`) causing wrong k selection
- `ValueError` in f-string formatting of optional fields
- sklearn `UserWarning` about feature names when passing numpy arrays to a scaler fitted on a DataFrame

### 3.3 Architecture and Design Guidance

The candidate used AI assistance to:

- Design the FastAPI-first project structure (all pipeline steps exposed as endpoints)
- Structure the GroupShuffleSplit strategy for host-aware train/test splitting
- Plan the 9-feature listing clustering feature set and 13-feature host feature set
- Design the priority-ordered cluster naming rule system

### 3.4 Documentation

AI assistance was used to draft:

- The `README.md` (reviewed and approved by the candidate)
- This disclosure document

---

## 4. What the Candidate Contributed

- **All analytical judgements** — choice of k=5 for listing clustering, acceptance of k=3/k=2 for host clustering, cluster name selection and validation
- **All output review** — inspecting every generated CSV, parquet, and JSON to confirm correctness
- **Data understanding** — interpreting what the Inside Airbnb fields mean, identifying the review-score inflation pattern, understanding the TargetEncoder cross-city failure
- **Direction and scope** — deciding which features to include, which models to compare, which bias dimensions to analyse
- **Running all code** — every script was executed by the candidate on their local machine; the AI cannot execute code autonomously
- **Validation** — confirming that cluster names matched the actual statistics (e.g. catching that "Occasional Hosts" had 99% response rate, distinguishing them from "Passive Listers" at 53%)
- **Assessment strategy** — determining the order of phases, which steps to prioritise, and when outputs were good enough

---

## 5. What the AI Did Not Do

- The AI did not have independent access to the dataset, the repository, or the runtime environment
- The AI did not make autonomous decisions — every action required the candidate to review and approve
- The AI did not run, test, or validate any code independently; all execution happened on the candidate's machine
- The AI did not select hyperparameters autonomously — all LightGBM hyperparameters were chosen by the candidate based on CV results
- The AI did not write the EDA findings or statistical interpretations — those were derived from the candidate's own analysis of the notebook outputs

---

## 6. Compliance Statement

The use of AI coding assistance described above is consistent with standard industry practice for software engineering roles. The work submitted reflects the candidate's own understanding, decision-making, and analytical capability. The candidate is able to explain every component of the pipeline, justify every design decision, and reproduce any part of the work independently.

---

*Signed: Bavikaran*
*Date: 21 June 2026*
