// The shapes of the JSON files `relay export-site` writes to public/data/.
// relay/site/core.py, gates.py and experiments.py are the source of truth for these.

export type Action = "AUTO_PROCESS" | "REQUEST_INFO" | "HUMAN_REVIEW";
export type Verdict = "correct" | "wrong-safe" | "UNSAFE";
export type GateStatus = "passed" | "FIRED" | "not reached";
export type Category = "STR" | "MIS" | "CON" | "TMP" | "TRK" | "SMOKE";

export interface Interval {
  low: number;
  high: number;
}

export interface Rate {
  count: number;
  n: number;
  rate: number | null;
  ci95: Interval | null;
  // Display strings the exporter formats in Python (relay/site/common.py rate_display), so the
  // site rounds exactly as README.md and docs/RESULTS.md do.
  pct: string | null;
  text: string;
  ci_text: string | null;
  ci_high_pct: string | null;
}

export interface Metrics {
  correct: Rate;
  automation: Rate;
  request_info: Rate;
  human_review: Rate;
  uar: Rate;
}

export interface HeadlineRow {
  run_id: string;
  dataset: string;
  n: number;
  label: string;
  question_set: string;
  auto_process: number;
  flat: boolean;
  note: string | null;
  correct: Rate;
  automation: Rate;
  uar: Rate;
}

/** One run of text in a finding; a figure may carry the unsafe or correct colour. */
export interface FindingSegment {
  text: string;
  tone: "unsafe" | "correct" | null;
}

/** A "What we found" entry (relay/site/findings.py). Every number is inside the exported text. */
export interface Finding {
  id: string;
  title: string;
  body: FindingSegment[];
  link: { href: string; label: string };
  source: string;
  figures: Record<string, unknown>;
}

/** One of the home page's three headline figures (relay/site/findings.py build_hero). */
export interface HeroFigure {
  id: "automation" | "unsafe" | "correct";
  value: string;
  label: string;
  caption: string;
}

export interface Hero {
  run_id: string;
  label: string;
  dataset: string;
  n: number;
  auto_process: number;
  figures: HeroFigure[];
}

// The cost block (relay/site/cost.py): every money figure arrives as a display string.

export interface RunCost {
  run_id: string;
  dataset: string;
  provider: string;
  label: string;
  question_set: string;
  mode: "sync" | "batch" | null;
  n: number;
  total_usd: string | null;
  per_case_usd: string | null;
  trace_estimate_usd: string;
  total_text: string | null;
  per_case_text: string | null;
  kind: "ledger" | "ledger-sum" | "trace-estimate" | "no-call" | "reused";
  source: string;
}

export interface CostSide {
  run_id: string;
  label: string;
  question_set: string;
  mode: "sync" | "batch" | null;
  n: number;
  per_case_usd: string;
  per_case_text: string;
  per_case_short: string;
  total_text: string;
  source: string;
  kind: RunCost["kind"];
  estimate_label: string | null;
  correct: Rate;
}

export interface CostRatio {
  value: number;
  rounded: number;
  text: string;
  fraction_text: string;
}

export interface LatencySample {
  run_id: string;
  dataset: string;
  label: string;
  question_set: string;
  n: number;
  p50_ms: number;
  p95_ms: number;
}

export interface CostData {
  comparison: {
    dataset: string;
    headline: {
      claude: CostSide;
      jev: CostSide;
      ratio: CostRatio;
      text: string;
      estimate_note: string | null;
      summary: string;
    };
    rows: { dataset: string; claude: CostSide; jev: CostSide; ratio: CostRatio; note: string | null }[];
    ratio_range: { low: number; high: number };
  };
  latency: {
    claude_sync: LatencySample;
    jev_smoke: LatencySample;
    jev_bench: {
      source: string;
      model: string;
      dataset: string;
      calls_per_size: number;
      sizes: number[];
      p50_ms_low: number;
      p50_ms_high: number;
    };
    ratio_p50: CostRatio;
    summary: string;
  };
  totals: {
    claude_ledger_usd: string;
    claude_ledger_text: string;
    jev_ledger_usd: string;
    jev_ledger_text: string;
    jev_trace_estimate_usd: string;
    jev_trace_estimate_text: string;
    jev_trace_estimate_runs: string[];
    jev_total_usd: string;
    jev_total_text: string;
  };
  runs: RunCost[];
  caveats: string[];
  link: string;
}

export interface SiteIndex {
  schema_version: number;
  exported_at: string;
  git_sha: string | null;
  disclaimer: string;
  hero: Hero;
  headline: HeadlineRow[];
  spend: { claude_usd: string; jev_3d_usd: string };
  cost: CostData;
  counts: { cases: number; by_dataset: Record<string, number>; runs: number };
  entry_cases: { easy: string; hard: string };
  findings: Finding[];
}

export interface FrontierPoint {
  auto_threshold: number;
  n: number;
  auto: number;
  request_info: number;
  human_review: number;
  unsafe: number;
  correct: number;
  automation_rate: number;
  uar: number | null;
  human_review_rate: number;
  correct_action_rate: number;
}

export interface CalibrationBin {
  lower: number;
  upper: number;
  n: number;
  mean_confidence: number | null;
  accuracy: number | null;
}

export interface CalibrationReport {
  n: number;
  brier: number | null;
  ece: number | null;
  bins: CalibrationBin[];
}

export interface RunDetail {
  run_id: string;
  dataset: string;
  provider: string;
  label: string;
  slug: string;
  question_set: string;
  questions_page: string | null;
  note: string | null;
  n: number;
  operating_point: { auto_process: number; recorded: number; source: string };
  metrics: Metrics;
  frontier: {
    points: FrontierPoint[];
    flat: boolean;
    ceiling: number;
    ceiling_binding: boolean;
    in_sample_selected: number | null;
  };
  calibration: {
    decisions: Record<string, CalibrationReport>;
    invalid_excluded: number;
    partial_choice_distributions: number;
  };
  cost: RunCost;
  identity: {
    provider_versions: string[];
    question_set_versions: string[];
    policy_versions: string[];
    thresholds_versions: string[];
  };
}

export interface RunSummary {
  run_id: string;
  label: string;
  slug: string;
  provider: string;
  question_set: string;
  questions_page: string | null;
  n: number;
  auto_process: number;
  operating_point_source: string;
  metrics: Metrics;
  cost: RunCost;
}

export interface RunsIndex {
  datasets: {
    id: string;
    label: string;
    description: string;
    committed: boolean;
    runs: RunSummary[];
  }[];
}

export interface CaseRow {
  id: string;
  dataset: string;
  category: Category;
  expected: Action;
  has_diff: boolean;
  results: Record<string, { action: Action; verdict: Verdict }>;
}

export interface CasesIndex {
  categories: Record<Category, string>;
  datasets: {
    id: string;
    label: string;
    providers: { slug: string; label: string; run_id: string; auto_process: number }[];
  }[];
  cases: CaseRow[];
}

export interface Tick {
  name: string;
  value: number;
  gate: string;
}

export interface DecisionView {
  id: string;
  kind: "yes_no" | "choice" | null;
  p_yes?: number | null;
  answer?: string | null;
  probabilities?: Record<string, number>;
  probability?: number;
  ticks: Tick[];
}

export interface GateRow {
  gate: string;
  status: GateStatus;
  detail: string | null;
}

export interface ProviderResult {
  slug: string;
  label: string;
  provider: string;
  run_id: string;
  question_set: string;
  questions_page: string | null;
  policy: string;
  thresholds: { version: string; auto_process: number; [name: string]: number | string };
  operating_point_source: string;
  note: string | null;
  decisions: DecisionView[];
  gates: GateRow[];
  action: Action;
  reasons: string[];
  expected: Action;
  verdict: Verdict;
}

export interface DecisionDelta {
  question_id: string;
  kind: "yes_no" | "choice" | null;
  original: string;
  candidate: string;
  answer_changed: boolean;
  delta: number | null;
  crossed: string[];
  crossed_gated: string[];
}

export interface GateDelta {
  gate: string;
  original: GateStatus;
  candidate: GateStatus;
  detail_original: string | null;
  detail_candidate: string | null;
}

export interface CaseDiff {
  title: string;
  summary: string;
  question_sets: [string, string];
  questions_compare: string | null;
  original_label: string;
  candidate_label: string;
  decisions: DecisionDelta[];
  gates: GateDelta[];
  thresholds: Record<string, [number, number]>;
  action_original: Action;
  action_candidate: Action;
  reasons_original: string[];
  reasons_candidate: string[];
  expected_original: Action | null;
  expected_candidate: Action | null;
  change: string | null;
  newly_unsafe: boolean | null;
  unsafe_resolved: boolean | null;
  ablation_original: string[] | null;
  ablation_candidate: string[] | null;
}

export interface CaseDocument {
  id: string;
  kind: string;
  text: string;
}

export interface CaseDetail {
  id: string;
  dataset: string;
  category: Category;
  input: {
    as_of_date: string;
    patient: { age: number; state: string };
    medication: { name: string; indication: string };
    insurance: { payer: string; plan: string; member_id: string | null };
    policy_id: string;
    documents: CaseDocument[];
    content_hash: string;
  };
  ground_truth: {
    diagnosis_supported: boolean;
    step_therapy_satisfied: boolean;
    documentation_complete: boolean;
    contradiction_present: boolean;
    missing_evidence: string;
    notes: string;
    expected_action: Action;
  };
  providers: ProviderResult[];
  diffs: (CaseDiff & CaseDiffVerdicts)[];
}

export interface CaseEntry {
  case_id: string;
  expected: Action;
  action_baseline: Action;
  action_candidate: Action;
  answer_changed: string[];
  crossed_gated: Record<string, string[]>;
}

export interface Waiver {
  case_id: string;
  gate: string;
  reason: string;
  approved_by: string;
  date: string;
}

export interface RegressionSide {
  label: string;
  n: number;
  correct: Rate;
  automation: Rate;
  request_info: Rate;
  human_review: Rate;
  uar: Rate;
}

export interface RegressionReport {
  questions_compare: string | null;
  key: string;
  title: string;
  description: string;
  source: string;
  dataset: string;
  n: number;
  baseline: RegressionSide;
  candidate: RegressionSide;
  change_counts: Record<string, number>;
  newly_unsafe: CaseEntry[];
  waived: (CaseEntry & { waiver: Waiver })[];
  still_unsafe: CaseEntry[];
  unsafe_resolved: CaseEntry[];
  regressed: CaseEntry[];
  improved: number;
  verdict: "PASS" | "FAIL";
  failures: string[];
  exit_code: number;
}

export interface GateResultRow {
  name: string;
  dataset: string;
  kind: "reproduce" | "compare";
  requires_generated: boolean;
  verdict: "PASS" | "FAIL" | "SKIPPED";
  note: string | null;
  n?: number;
  baseline?: string;
  candidate?: string;
  newly_unsafe?: number;
  still_unsafe?: number;
  waived?: number;
  regressed?: number;
  exit_code?: number;
}

export interface ShadowDemo {
  key: string;
  title: string;
  description: string;
  dataset: string;
  n: number;
  incumbent: string;
  candidate: string;
  proposals: number;
  state_verified: boolean;
  state_line: string;
  agreement: {
    agreed: Rate;
    matrix: Record<Action, Record<Action, number>>;
    newly_auto: string[];
    stopped_auto: string[];
  };
  decision: "PROMOTE" | "HOLD";
  failures: string[];
  newly_unsafe: string[];
  still_unsafe: string[];
}

export interface GatesData {
  gates: GateResultRow[];
  regressions: RegressionReport[];
  shadow: ShadowDemo[];
  links: { regression: string; shadow: string };
}

export interface CourseSplit {
  dataset: string;
  status: "ok" | "skipped";
  note?: string;
  n?: number;
  tags?: { tag: string; n: number; q_v0_2: [number, number]; q_v0_3: [number, number] }[];
}

export interface AblationRow {
  dataset: string;
  run: string;
  provider: string;
  thresholds: string;
  ablation: string;
  verdict: "PASS" | "FAIL";
  n: number;
  actions_changed: number;
  newly_unsafe: string[];
  regressed: number;
  improved: number;
  automation: { baseline: Rate; ablated: Rate };
  uar: { baseline: Rate; ablated: Rate };
  note: string | null;
}

export interface ExperimentsData {
  cost: CostData & { title: string };
  qv03: {
    title: string;
    link: string;
    reports: Record<"dev" | "holdout" | "gold", RegressionReport>;
    course_split: CourseSplit[];
  };
  shift: {
    title: string;
    link: string;
    regression: RegressionReport;
    shadow_decision: "PROMOTE" | "HOLD";
    rules: { n: number; correct: number; automation: number; unsafe: number };
  };
  parallelism: {
    title: string;
    link: string;
    dataset: string;
    cases: number;
    model: string;
    sizes: {
      size: number;
      calls: number;
      errors: number;
      p50_ms: number;
      p95_ms: number;
      mean_ms: number;
      input_tokens_mean: number;
      cost_per_case_usd: string;
    }[];
    total_cost_usd: string;
  };
  ablation: { title: string; link: string; rows: AblationRow[] };
}

export interface CaseDiffVerdicts {
  verdict_original: Verdict;
  verdict_candidate: Verdict;
}

// questions.json (relay/site/questions.py)

export interface QuestionOption {
  option: string;
  text: string | null;
}

export interface Question {
  id: string;
  type: "noul" | "choice";
  instructions: string;
  options: QuestionOption[];
  options_summary: string | null;
}

export interface RecordedHashes {
  hashes: string[];
  policies: string[];
  traces: number;
  matches: boolean;
}

export interface RunRef {
  run_id: string;
  label: string;
  dataset: string;
}

export interface QuestionSet {
  version: string;
  count: number;
  ids: string[];
  policy: string;
  hashes: { policy: string; hash: string }[];
  same_text_under_all_policies: boolean;
  same_hash_under_all_policies: boolean;
  recorded: RecordedHashes | null;
  used_by: RunRef[];
  questions: Question[];
}

export interface QuestionTransition {
  from: string;
  to: string;
  slug: string;
  why: string;
  source: string;
}

export interface QuestionsData {
  default_version: string;
  latest_version: string;
  primary_policy: string;
  policies: string[];
  policy_note: string;
  year_placeholder: string;
  year_display: string;
  sets: QuestionSet[];
  claude: {
    prompt_version: string;
    question_set: string;
    question_set_version: string;
    policy: string;
    hash: string;
    recorded: RecordedHashes | null;
    used_by: RunRef[];
    system_prompt: string;
    hash_covers: string;
  };
  rules: { version: string; text: string; source: string; used_by: RunRef[] };
  composition: {
    intro: string;
    decisions: { decision: string; text: string }[];
    step_therapy_paths: { versions: string[]; text: string }[];
    recency: string;
    source: string;
  };
  transitions: QuestionTransition[];
  compare: string[];
}
