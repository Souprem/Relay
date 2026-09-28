// Build-time readers for the JSON that `relay export-site` writes to public/data/.
// Only server components and generateStaticParams call these; nothing is fetched at runtime.
import fs from "node:fs";
import path from "node:path";

import type {
  CaseDetail,
  CasesIndex,
  ExperimentsData,
  GatesData,
  RunDetail,
  RunsIndex,
  SiteIndex,
} from "./types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

function read<T>(relative: string): T {
  const file = path.join(DATA_DIR, relative);
  if (!fs.existsSync(file)) {
    throw new Error(
      `Missing ${file}. Export the site data first, from the repository root: ` +
        "uv run relay --env-file .no-such.env export-site --out web/public/data",
    );
  }
  return JSON.parse(fs.readFileSync(file, "utf-8")) as T;
}

export const getIndex = () => read<SiteIndex>("index.json");
export const getCases = () => read<CasesIndex>("cases.json");
export const getCase = (id: string) => read<CaseDetail>(`cases/${id}.json`);
export const getRuns = () => read<RunsIndex>("runs.json");
export const getRun = (runId: string) => read<RunDetail>(`runs/${runId}.json`);
export const getGates = () => read<GatesData>("gates.json");
export const getExperiments = () => read<ExperimentsData>("experiments.json");
