# Ask endpoint — question routing over approved statements

- Status: Proposed. Awaiting owner approval; no implementation until approved.
- Date: 2026-11-17
- Depends on: G2 advisor sign-off (all rules in `rules/mvp_rules.yaml` are `status: draft`)
- Related: `design/prototypes/04-celestial-gold-refined.html` (Ask card), S14 prediction ledger, Gap 10 rewording guardrails

## 1. Problem

The app can show fixed interpretation surfaces (daily insight, life areas, annual forecast) but cannot answer a
question the user actually typed. The prototype demonstrates an Ask card with five chips across six areas
(`career`, `finances`, `health`, `home`, `relationships`, `growth`), and the backend has no route behind it.
Without a contract, the client would either fake answers or the first implementation would let a model answer
freely — which the blueprint excludes.

## 2. Non-goals

- No conversation, history, follow-ups, or memory. One question in, one answer out.
- No health, growth, travel, litigation, education, or children areas in v1. The backend has four
  `LifeAreaCategory` values; inventing more is a rule-library project, not an endpoint project.
- No generative astrological content. The model never produces placements, grades, sources, or timeframes.
- No changes to `guardrails.validate_rephrase`, `verify_text`, ledger probabilities, or G-gate semantics.
- No Flutter work. This spec is backend-only; UI approval remains a separate gate.

## 3. G7-scope conformance (required)

Blueprint part 1, line 6 excludes a "Free-Form AI Chat Assistant" via `G7-scope`. Ask is admissible only as
**routing over pre-approved statements**, and this spec is written to stay on that side of the line:

1. The question is read by a deterministic lexicon, never by a model.
2. The model, when enabled, receives one already-guarded sentence and returns a rewording of it. It never sees
   the question.
3. Output is always a statement that already exists in the rule library and passed `verify_text` at generation.
4. Areas without a rule produce a refusal card (`uncovered`), never a generated answer.
5. There is no state between requests and no free-text model output reaches the client.

Precondition: the astrologer advisor who signs off G2 also confirms that this boundary is "question routing",
not "free-form chat". If that confirmation is withheld, the feature does not ship even with LLM disabled,
because the classification surface is the disputed part.

## 4. Current state (verified 2026-11-17)

| Fact | Evidence |
| --- | --- |
| No `/ask` route exists | `build_router` ends at matching/glossary/trust/festivals/privacy/user routes, `app/api/routes.py:127` |
| Four life areas only | `LifeAreaCategory = Literal["career","relationships","finances","home"]`, `app/api/schemas.py:10` |
| Area readings are one statement per rule, unconditional | `generate_life_area_readings`, `app/interpretation/readings.py:63` |
| Eight rules, one per area, all draft | `rules/mvp_rules.yaml` (career, relationships, finances, home, 3 yoga, 1 dosha_context) |
| Draft rules are rejected unless explicitly allowed | `load_rules`, `app/interpretation/rules.py:51`; production forces `allow_draft_rules=false`, `app/config.py:65` |
| Rewording is off by default and capped | `SafeRephraser.rephrase`, `app/interpretation/llm.py:23` |
| Ledger requires an authenticated `user_id` and an outcome criterion | `register`, `app/ledger/service.py:44`; route `app/api/routes.py:511` |
| Ledger `register` overwrites existing rows via `s.merge` | `app/ledger/service.py:78` |
| Telemetry event types are a closed literal | `app/api/schemas.py:12` |
| G6 requires exact i18n key parity across en/hi/mr | `scripts/check_guardrails.py:85` |
| G7 forbids module names matching `free_form_chat` | `FORBIDDEN_MODULES`, `scripts/check_guardrails.py:14` |

Consequence: Ask cannot answer more than four intents, and in production it cannot answer anything until the
advisor approves the area rules. That is the correct behaviour, not a limitation to work around.

## 5. Data flow

```
POST /v1/readings/ask
 1. auth → user_id                        (401 if absent)
 2. ask_enabled?                          (503 ask_disabled)
 3. question shape check                  (422 if invalid)
 4. classify(question) → area | abstain   (no chart, no model, no quota)
 5. abstain → 200 uncovered               (no chart, no model, no ledger, no quota)
 6. infer target_date from a 4-digit year (optional)
 7. chart → dasha → transits → life-area statement + optional daily insight
 8. canonical text from catalog           (verify_text already enforced at generation)
 9. optional reword: SafeRephraser on the primary statement only + validate_answer
10. quota consumed (only after a successful answer)
11. ledger register_or_get(canonical text)
12. respond (+ telemetry event)
```

Classification precedes chart computation by design: an unmappable question must not spend an ephemeris call,
a model call, or a quota unit.

## 6. HTTP contract

### 6.1 New models (`app/api/schemas.py`)

```python
class AskRequest(BaseModel):
    details: BirthDetailsInput
    question: str = Field(min_length=3, max_length=280)
    target_date: date | None = None


class AskCoverage(BaseModel):
    status: Literal["answered", "uncovered"]
    area: LifeAreaCategory | None
    matched_terms: list[str]
    available_areas: list[LifeAreaCategory]   # canonical order: career, relationships, finances, home


class LLMProvenance(BaseModel):
    used: bool
    model: str | None = None
    fallback_reason: str | None = None


class AskResponse(BaseModel):
    request_id: str
    coverage: AskCoverage
    statement: ExplainedStatement | None
    context: list[ExplainedStatement] = []
    ledger_entry_id: str | None = None
    llm: LLMProvenance
    disclaimer: str
```

`statement` is the area statement. `context` carries at most one canonical timing statement (daily insight),
never reworded. `disclaimer` is `trust.professional_advice_disclaimer` for `details.language`.

### 6.2 Route

`POST /v1/readings/ask`, declared inside `build_router(settings)` next to the other readings routes, with
`auth_user: str = Depends(current_user_dep)`. No alias route. Requires `AskRequest` as the body because two
models cannot be flattened into one body.

### 6.3 Answered example (en, LLM off)

```json
{
  "request_id": "7f0c1f39-5a1e-4b6e-9a51-0f0e0a4c1d21",
  "coverage": {"status": "answered", "area": "career", "matched_terms": ["job"], "available_areas": ["career", "relationships", "finances", "home"]},
  "statement": {
    "statement_id": "RULE_PARASHARI_CAREER_10H_4_7",
    "category": "career",
    "time_window": "Active Moon-Ketu Dasha (until 2027-08-12)",
    "simple_text": "…catalog text…",
    "pro_text": "…catalog text…",
    "why_this": {
      "rule_id": "RULE_PARASHARI_CAREER_10H",
      "placement_evidence": "Sun in Leo (House 10, D9 Aries); Dasha: Moon-Ketu",
      "classical_source": "Brihat Parashara Hora Shastra (BPHS), Ch. 21 (Karma Bhava)",
      "tradition": "Parashari",
      "strength_grade": "supported",
      "method_note": "Sidereal Lahiri, Whole-Sign Houses"
    },
    "safety_verified": true
  },
  "context": [],
  "ledger_entry_id": "ASK-3a9e12c07b4d5f61",
  "llm": {"used": false, "model": null, "fallback_reason": null},
  "disclaimer": "…trust.professional_advice_disclaimer…"
}
```

### 6.4 Uncovered example

```json
{
  "request_id": "0b6d…",
  "coverage": {"status": "uncovered", "area": null, "matched_terms": [], "available_areas": ["career", "relationships", "finances", "home"]},
  "statement": null,
  "context": [],
  "ledger_entry_id": null,
  "llm": {"used": false, "model": null, "fallback_reason": null},
  "disclaimer": "…trust.professional_advice_disclaimer…"
}
```

The client renders `ask.coverage.uncovered_body` and the `available_areas` names from `area.*` i18n keys.
`matched_terms` is empty on every abstention (zero matches or tie), and lists the matched terms only
when an area is selected.
Health and growth chips in the prototype must map to this card until rules exist.

### 6.5 Status codes

| Condition | Code | Body |
| --- | --- | --- |
| Missing/invalid auth | 401 | existing auth error |
| `ask_enabled` false | 503 | `{"error": "ask_disabled"}` |
| question blank, >280 chars, or not text | 422 | `{"error": "ask_question_invalid"}` |
| Area unmapped, tie, or no area statement | 200 | `coverage.status="uncovered"`, `statement=null` |
| Weekly free quota exhausted | 429 | `{"error": "ask_quota_exhausted"}` |
| Chart/dasha/transit failure | 502 | `{"error": "chart_unavailable"}` |
| Rules fail G2 load | 503 at startup | existing `RuleSchemaError` path |

`uncovered` is a 200 because it is a correct product answer, not a failure.

### 6.6 Target-date inference

An explicit `target_date` wins. Otherwise, if the question contains exactly one four-digit year in
`20xx`, use 15 January of that year, clamped to `[today, today + 3 years]`. If it contains none or several,
use today in the birth timezone (existing `_today_in_tz`). No month, weekday, or relative-phrase parsing in v1.

## 7. Classification (deterministic)

`app/interpretation/ask.py`:

```python
@dataclass(frozen=True)
class AreaLexicon:
    terms: dict[LifeAreaCategory, tuple[str, ...]]
    present_cues: tuple[str, ...]

def classify_question(question: str, lexicon: AreaLexicon) -> tuple[LifeAreaCategory | None, list[str]]
```

Data lives in `rules/ask_lexicon.yaml` (not Python) so Hindi/Marathi terms do not trip G3-static or G6-hardcoded
scanning and can be revised without a code change:

```yaml
career: ["job", "career", "promotion", "appraisal", "work", "role", "interview", "नौकरी", "करियर", "नोकरी"]
relationships: ["marriage", "partner", "spouse", "relationship", "commit", "विवाह", "शादी", "नाते"]
finances: ["money", "finance", "loan", "debt", "saving", "invest", "salary", "पैसा", "कर्ज", "पैसे"]
home: ["home", "house", "property", "rent", "move", "renovate", "घर", "मकान", "जमीन", "घरबदल"]
```

Rules:

- Latin terms match on word boundaries; Devanagari terms match on substring (matras are not `\w`).
- Score = number of distinct matched terms per area. Highest score wins.
- Zero matches or a tie between two areas → abstain → `uncovered`, with `matched_terms: []`. Abstaining on
  a tie is preferred over guessing.
- Case-folded input only. Question length is already bounded by the request model.
- Known limitation: negation ("not about money") is not understood and routes to the named area. Accepted
  for v1 and covered by an explicit test so it is a documented behaviour, not a surprise.

## 8. Composition and optional rewording

- Primary answer = `generate_life_area_readings(...)[area][0]`. If the area returns no statement, `uncovered`.
- Context = `generate_daily_insight` only when the question contains a present-time cue
  (`today|now|this week|currently|आज|अभी|आता`), matching the same lexicon-matching rules.
- The LLM rewrites the **primary statement only**. `context` is returned canonical. This keeps
  `validate_answer` a single-sentence check and fixes the statement order.
- `SafeRephraser.rephrase` is reused unchanged; the provider adapter still receives only the guarded sentence.
- When `llm_rephrase_enabled` is false (default), the endpoint is fully functional and `llm.used=false`.

## 9. `guardrails.validate_answer` (new, additive)

`validate_rephrase` stays exactly as specified by the blueprint, including its digit rule. To avoid a
contradiction (the blueprint gate rejects digits absent from the original, while an answer may legitimately echo
the year from the question), the existing checks are extracted into one private function with default arguments
that reproduce current behaviour byte for byte:

```python
def _validate_grounding(
    original: str,
    rephrased: str,
    *,
    extra_digits: frozenset[str] = frozenset(),
    require_sources: bool = True,
) -> None:
    ...

def validate_rephrase(original: str, rephrased: str) -> bool:
    _validate_grounding(original, rephrased)   # identical behaviour; existing tests unchanged
    return True
```

The new wrapper adds question-relative checks on top:

```python
def validate_answer(
    *,
    bundle: str,
    question: str,
    area: LifeAreaCategory,
    answer: str,
    lang: LanguageCode,
    lexicon: AreaLexicon,
    require_sources: bool = False,
) -> None:
    _validate_grounding(
        bundle,
        answer,
        extra_digits=frozenset(_digits(question)),
        require_sources=require_sources,
    )
    ...
```

| Check | Rule | Why |
| --- | --- | --- |
| Faithfulness | the shared `_validate_grounding` checks (absolute claims, fear terms, upsell, digits, rule IDs, placements, grades, sources) | unchanged blueprint gate |
| Digits | allowed set = digits(`bundle`) ∪ digits(`question`), compared after `unicodedata.digit` normalization | echoing "2027" from the question must pass; `२०२७` must equal `2027` |
| Area containment | terms from any *other* area in `lexicon` must not appear in `answer` | blocks drift ("your savings will grow" for a career question) |
| No soft refusal | refusal patterns (`cannot answer`, `no information`, `उत्तर नहीं दे सकते`, …) must not appear | blocks a refusal of a covered area |
| No new timeframe | year and month tokens in `answer` must appear in `bundle` or `question` | stops invented windows |
| Shape | 15–420 characters, single paragraph, no `?`, no list markers | one card, not an essay |
| No meta | no `system`, `prompt`, `instruction`, `language model`, `as an AI` | injection echo guard |
| Script | `en` → Latin and no Devanagari; `hi`/`mr` → Devanagari present | wrong-language output falls back |
| Sources | `require_sources=False` for answers | `why_this.classical_source` already carries provenance; forcing it into prose reads like a citation dump |

Any failure means fall back to canonical text and record `fallback_reason` in the audit log. There is no
partial acceptance.

Amendment 2026-11-17 (during implementation planning): the original "area addressed" check required an area
lexicon term in the answer. The canonical sentences ("Steady professional progress is supported through
structured planning…") contain no such term, so the check would have rejected valid paraphrases of the very text
it was protecting. Replaced by refusal-pattern detection; drift is still covered by containment and
faithfulness.

Month names are deliberately excluded for `may`, which collides with the modal verb; a reword that introduces
"may" as a month is therefore treated as ordinary prose.

## 10. Rule-library extension

Add `observable_outcome_criteria: str` to the `Rule` dataclass and YAML schema, required for `status: approved`,
optional for `draft`. `load_rules` continues to enforce G2 (reviewer, reviewed_at, status). Without this field
Ask cannot register a ledger entry, and the ledger would be unable to score any answer.

The four area rules must each gain a criterion the advisor can sign, phrased so a user can mark
hit/miss/ambiguous later. This is advisor work, not engineering work, and it is the same G2 gate the
rest of the product already waits on.

## 11. Persistence

### 11.1 Ledger

Ask registers the **canonical `simple_text`**, never the reworded prose, so calibration scores the rule and not
the model. `statement_text` must pass `verify_text` (canonical text already does).

New service method, used only by Ask:

```python
def register_or_get(self, **kwargs) -> PreRegisteredLedgerEntry
```

It returns the existing entry when `entry_id` is already present and never rewrites it. `entry_id` is
`ASK-` + first 16 hex chars of `sha256(f"{user_id}|{statement_id}|{time_window}")`, so repeated questions about
the same statement and window resolve to one ledger prediction instead of inflating counts.

Note for separate review: `register` currently uses `s.merge` (`app/ledger/service.py:78`), which would reset a
previously logged outcome if the same `entry_id` were registered again. `register_or_get` avoids the path for
Ask; the manual `/ledger/register` endpoint keeps its current behaviour in this change.

### 11.2 LLM audit

`LLMAuditRow` gains nullable columns: `prompt_version`, `model`, `bundle_hash`, `question_area`. `bundle_hash`
is `sha256` of `statement_id | rule_id | strength_grade | time_window`. Without these, acceptance rate per area
cannot be computed and a disputed answer cannot be replayed.

### 11.3 Quota

New table `ask_usage(user_id, iso_week_start_utc, count)`, primary key `(user_id, iso_week_start_utc)`,
week starting Monday 00:00 UTC. Consumed only after a successful answer; `uncovered` and errors cost nothing.
Free entitlement is `ask_weekly_free_quota` (default 3). There is no per-user plan claim in auth today, so
every authenticated user is free-tier in v1; Pro wiring is a later entitlement change, not a hidden flag.

### 11.4 Migration

`alembic/versions/0002_ask_usage_and_audit_fields.py` adds the audit columns and the `ask_usage` table.

## 12. Telemetry and i18n

- Add `"ask_answered"` and `"ask_uncovered"` to `TelemetryEventType` (`app/api/schemas.py:12`). Category is
  `life_area`, `rule_id` is the matched rule or empty, `language` is the request language. The question text is
  never recorded.
- New i18n keys, identical in `i18n/en.json`, `hi.json`, `mr.json` (G6 parity): `ask.coverage.uncovered_title`,
  `ask.coverage.uncovered_body`, `ask.coverage.suggestion`, `area.career`, `area.relationships`,
  `area.finances`, `area.home`, `error.ask_question_invalid`, `error.ask_quota_exhausted`, `error.ask_disabled`.
- No user-visible prose in Python (G6-hardcoded).

## 13. Configuration

```python
ask_enabled: bool = False              # kill switch; off until owner approval
ask_weekly_free_quota: int = 3
```

`llm_rephrase_enabled`, `llm_monthly_call_cap`, `anthropic_model` are unchanged. Ask must work with all LLM
settings at their defaults.

## 14. Testing and acceptance

New tests:

| File | Asserts |
| --- | --- |
| `tests/test_ask_classification.py` | per-language routing, word-boundary Latin matching, tie abstains, negation routes as documented |
| `tests/test_validate_answer.py` | Devanagari digit normalization, cross-area drift rejected, soft refusal rejected, invented month rejected, wrong script rejected, meta tokens rejected, canonical sentence passes |
| `tests/test_ask_contract.py` | answered shape, uncovered shape, uncovered does not call chart/LLM/quota (monkeypatched), 422/429/503 paths, `llm.used` false by default |
| `tests/test_ask_ledger.py` | canonical text registered, reworded prose never registered, `register_or_get` dedupes and preserves a logged outcome |
| `tests/test_ask_rephrase.py` | fake client returning another area falls back with `fallback_reason`; accepted reword keeps grade and sources |
| `tests/test_ask_quota.py` | 3 answers then 429; uncovered and failures do not consume |

The existing guardrail test suite must pass without a single assertion being edited. Changing an existing
`validate_rephrase` expectation is a stop signal, not a test update.

Acceptance, all from the repo root:

```
make test lint types guardrails
make openapi-check          # commit the regenerated openapi.json in the same change
python scripts/validate_step.py --all
make gate-g1
make gate-g2
```

`make guardrails` must still print PASS for G3-static, G5-*, G6-*, and G7-scope. No guardrail, threshold, or
probability is weakened by this work.

## 15. Known limitations (accepted for v1)

- Four intents only; health and growth return `uncovered`.
- One rule per area means every question in an area returns the same evidence, only the timing window varies.
- One area per question; compound questions ("job and marriage") take the higher score or abstain on a tie.
- No negation handling and no temporal parsing beyond a single four-digit year.
- Confidence wording comes from `strength_grade`; the answer is a statement of tendency and window, not a
  yes/no verdict, so "Will I…?" questions are answered probabilistically by design.

## 16. Decisions requested from the owner

1. Approve the G7-scope reading in section 3, or stop the feature.
2. Confirm `uncovered` as the shipped behaviour for health and growth until those rules exist.
3. Confirm free-tier quota of 3 questions per week with no paid override in v1.

Defaults in this spec apply if you approve without changes.

## 17. Out of scope for this spec

Frontend Ask card wiring, Pro entitlement claims, additional life areas, conversation history, question
suggestions beyond the static chips, and any change to the Flutter design gate.
