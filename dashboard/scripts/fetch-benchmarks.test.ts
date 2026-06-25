import { describe, expect, it } from "vitest";
import {
  buildCsindexPerfUrl,
  buildFredCsvUrl,
  normalizeCsindexRows,
  normalizeFredRows,
  resolveBenchmarkWindow,
  serializeBenchmarkRows
} from "./fetch-benchmarks";

describe("benchmark fetch helpers", () => {
  it("builds reproducible source URLs for the benchmark refresh script", () => {
    expect(buildCsindexPerfUrl("H00300", "2016-06-21", "2026-06-24")).toContain("indexCode=H00300");
    expect(buildCsindexPerfUrl("H00300", "2016-06-21", "2026-06-24")).toContain("startDate=20160621");
    expect(buildFredCsvUrl("NASDAQXNDX", "2016-06-21", "2026-06-24")).toContain("id=NASDAQXNDX");
    expect(buildFredCsvUrl("NASDAQXNDX", "2016-06-21", "2026-06-24")).toContain("cosd=2016-06-21");
  });

  it("resolves benchmark refresh dates from explicit input instead of a stale hard-coded end date", () => {
    expect(resolveBenchmarkWindow({ endDate: "2026-07-15" })).toEqual({
      startDate: "2016-06-21",
      endDate: "2026-07-15"
    });
    expect(resolveBenchmarkWindow({ env: {}, today: new Date("2026-07-16T03:00:00.000Z") })).toEqual({
      startDate: "2016-06-21",
      endDate: "2026-07-16"
    });
  });

  it("normalizes CSIndex rows and preserves total-return benchmark identity", () => {
    const rows = normalizeCsindexRows(
      [
        {
          tradeDate: "20260624",
          indexCode: "H00300",
          indexNameCnAll: "沪深300全收益指数",
          close: 7344.52
        },
        {
          tradeDate: "20160621",
          indexCode: "H00300",
          indexNameCnAll: "沪深300全收益指数",
          close: 3288.46
        }
      ],
      "H00300",
      "沪深300全收益指数"
    );

    expect(rows).toEqual([
      { date: "2016-06-21", indexCode: "H00300", indexName: "沪深300全收益指数", close: "3288.46" },
      { date: "2026-06-24", indexCode: "H00300", indexName: "沪深300全收益指数", close: "7344.52" }
    ]);
  });

  it("normalizes FRED CSV rows and drops missing observations", () => {
    const rows = normalizeFredRows(
      "observation_date,NASDAQXNDX\n2026-06-18,37102.06\n2026-06-19,\n2026-06-22,37031.72\n",
      "NASDAQXNDX",
      "纳斯达克100全收益指数"
    );

    expect(rows).toEqual([
      { date: "2026-06-18", indexCode: "NASDAQXNDX", indexName: "纳斯达克100全收益指数", close: "37102.06" },
      { date: "2026-06-22", indexCode: "NASDAQXNDX", indexName: "纳斯达克100全收益指数", close: "37031.72" }
    ]);
  });

  it("serializes generated benchmark CSVs with LF line endings", () => {
    const csv = serializeBenchmarkRows([
      { date: "2026-06-18", indexCode: "NASDAQXNDX", indexName: "纳斯达克100全收益指数", close: "37102.06" },
      { date: "2026-06-22", indexCode: "NASDAQXNDX", indexName: "纳斯达克100全收益指数", close: "37031.72" }
    ]);

    expect(csv).toBe(
      "date,indexCode,indexName,close\n" +
        "2026-06-18,NASDAQXNDX,纳斯达克100全收益指数,37102.06\n" +
        "2026-06-22,NASDAQXNDX,纳斯达克100全收益指数,37031.72\n"
    );
    expect(csv).not.toContain("\r");
  });
});
