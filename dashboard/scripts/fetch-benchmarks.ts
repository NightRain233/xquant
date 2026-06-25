import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import Papa from "papaparse";

type BenchmarkRow = {
  date: string;
  indexCode: string;
  indexName: string;
  close: string;
};

type CsindexPerfRow = {
  tradeDate: string;
  indexCode: string;
  indexNameCnAll?: string;
  indexNameCn?: string;
  close: number | string;
};

type CsindexPerfResponse = {
  code: string;
  msg?: string;
  data?: CsindexPerfRow[];
};

type BenchmarkJob = {
  id: string;
  outputFile: string;
  source: "csindex" | "fred";
  code: string;
  name: string;
};

const START_DATE = "2016-06-21";
const OUTPUT_DIR = "outputs/benchmarks";
const BENCHMARK_COLUMNS = ["date", "indexCode", "indexName", "close"];

const jobs: BenchmarkJob[] = [
  {
    id: "active-partial-equity-fund",
    outputFile: "csi932055_active_partial_equity_fund.csv",
    source: "csindex",
    code: "932055",
    name: "中证主动偏股型基金指数"
  },
  {
    id: "csi300-total-return",
    outputFile: "csi_h00300_csi300_total_return.csv",
    source: "csindex",
    code: "H00300",
    name: "沪深300全收益指数"
  },
  {
    id: "nasdaq100-total-return",
    outputFile: "fred_nasdaqxndx_nasdaq100_total_return.csv",
    source: "fred",
    code: "NASDAQXNDX",
    name: "纳斯达克100全收益指数"
  }
];

export function buildCsindexPerfUrl(indexCode: string, startDate: string, endDate: string): string {
  const params = new URLSearchParams({
    indexCode,
    startDate: startDate.replace(/-/g, ""),
    endDate: endDate.replace(/-/g, "")
  });

  return `https://www.csindex.com.cn/csindex-home/perf/index-perf?${params.toString()}`;
}

export function buildFredCsvUrl(seriesId: string, startDate: string, endDate: string): string {
  const params = new URLSearchParams({
    id: seriesId,
    cosd: startDate,
    coed: endDate
  });

  return `https://fred.stlouisfed.org/graph/fredgraph.csv?${params.toString()}`;
}

export function normalizeCsindexRows(rows: CsindexPerfRow[], fallbackCode: string, fallbackName: string): BenchmarkRow[] {
  return rows
    .map((row) => {
      const tradeDate = row.tradeDate;

      return {
        date: `${tradeDate.slice(0, 4)}-${tradeDate.slice(4, 6)}-${tradeDate.slice(6, 8)}`,
        indexCode: row.indexCode || fallbackCode,
        indexName: row.indexNameCnAll || row.indexNameCn || fallbackName,
        close: String(row.close)
      };
    })
    .filter((row) => row.date.length === 10 && Number(row.close) > 0)
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function normalizeFredRows(csvText: string, seriesId: string, indexName: string): BenchmarkRow[] {
  const parsed = Papa.parse<Record<string, string>>(csvText.replace(/^\uFEFF/, ""), {
    header: true,
    skipEmptyLines: true
  });

  if (parsed.errors.length > 0) {
    const [firstError] = parsed.errors;
    throw new Error(`Failed to parse FRED ${seriesId}: ${firstError.message}`);
  }

  return parsed.data
    .map((row) => ({
      date: row.observation_date,
      indexCode: seriesId,
      indexName,
      close: row[seriesId]
    }))
    .filter((row) => row.date && Number(row.close) > 0)
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function resolveBenchmarkWindow(options: {
  startDate?: string;
  endDate?: string;
  today?: Date;
  env?: Record<string, string | undefined>;
} = {}): { startDate: string; endDate: string } {
  const env = options.env ?? process.env;

  return {
    startDate: options.startDate ?? env.BENCHMARK_START_DATE ?? START_DATE,
    endDate: options.endDate ?? env.BENCHMARK_END_DATE ?? (options.today ?? new Date()).toISOString().slice(0, 10)
  };
}

export function serializeBenchmarkRows(rows: BenchmarkRow[]): string {
  return `${Papa.unparse(rows, { columns: BENCHMARK_COLUMNS, newline: "\n" })}\n`;
}

async function fetchText(url: string): Promise<string> {
  const response = await fetch(url, {
    headers: {
      "user-agent": "Mozilla/5.0"
    }
  });

  if (!response.ok) {
    throw new Error(`Request failed ${response.status}: ${url}`);
  }

  return response.text();
}

async function fetchCsindexBenchmark(job: BenchmarkJob, startDate: string, endDate: string): Promise<BenchmarkRow[]> {
  const payload = JSON.parse(await fetchText(buildCsindexPerfUrl(job.code, startDate, endDate))) as CsindexPerfResponse;

  if (payload.code !== "200") {
    throw new Error(`CSIndex ${job.code} failed: ${payload.msg ?? payload.code}`);
  }

  return normalizeCsindexRows(payload.data ?? [], job.code, job.name);
}

async function fetchFredBenchmark(job: BenchmarkJob, startDate: string, endDate: string): Promise<BenchmarkRow[]> {
  return normalizeFredRows(await fetchText(buildFredCsvUrl(job.code, startDate, endDate)), job.code, job.name);
}

async function writeBenchmarkCsv(repoRoot: string, job: BenchmarkJob, rows: BenchmarkRow[]): Promise<string> {
  if (rows.length < 2) {
    throw new Error(`Benchmark ${job.id} returned insufficient rows`);
  }

  const outputPath = join(repoRoot, OUTPUT_DIR, job.outputFile);
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, serializeBenchmarkRows(rows), "utf8");
  return outputPath;
}

export async function refreshBenchmarks(
  repoRoot: string,
  startDate = resolveBenchmarkWindow().startDate,
  endDate = resolveBenchmarkWindow().endDate
): Promise<string[]> {
  const outputPaths: string[] = [];

  for (const job of jobs) {
    const rows =
      job.source === "csindex"
        ? await fetchCsindexBenchmark(job, startDate, endDate)
        : await fetchFredBenchmark(job, startDate, endDate);
    outputPaths.push(await writeBenchmarkCsv(repoRoot, job, rows));
  }

  return outputPaths;
}

async function main() {
  const repoRoot = join(process.cwd(), "..");
  const { startDate, endDate } = resolveBenchmarkWindow();
  const outputPaths = await refreshBenchmarks(repoRoot, startDate, endDate);
  for (const outputPath of outputPaths) {
    console.log(outputPath);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  await main();
}
