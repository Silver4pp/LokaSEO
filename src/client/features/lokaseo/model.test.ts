import { describe, expect, it } from "vitest";
import {
  clusterKeywords,
  csvCell,
  evaluateAudit,
  workspaceSchema,
} from "./model";
describe("LokaSEO", () => {
  it("deduplicates Indonesian keywords and prioritizes local intent", () => {
    expect(
      clusterKeywords("Kopi Bogor\nkopi bogor\nharga kopi, cara kopi"),
    ).toEqual({
      "Pencarian lokal": ["kopi bogor"],
      "Siap membeli": ["harga kopi"],
      "Informasi & panduan": ["cara kopi"],
    });
  });
  it("caps unique keywords to protect rendering", () => {
    expect(
      Object.values(
        clusterKeywords(
          Array.from({ length: 510 }, (_, i) => `kata ${i}`).join("\n"),
        ),
      ).flat(),
    ).toHaveLength(500);
  });
  it("neutralizes spreadsheet formulas and escapes quotes", () => {
    expect(csvCell("=1+1")).toBe('"\'=1+1"');
    expect(csvCell('a"b')).toBe('"a""b"');
  });
  it("flags noindex and missing image alt", () => {
    const checks = evaluateAudit({
      title: "Judul halaman contoh bisnis Bogor",
      description: "a".repeat(100),
      h1: 1,
      lang: "id-ID",
      canonical: true,
      images: 1,
      missingAlt: 1,
      viewport: true,
      noindex: true,
      localSchema: true,
    });
    expect(checks.filter((c) => !c.pass).map((c) => c.id)).toEqual([
      "index",
      "alt",
    ]);
  });
  it("rejects malformed backups", () => {
    expect(
      workspaceSchema.safeParse({ version: 1, projects: [], activeId: "x" })
        .success,
    ).toBe(false);
    expect(workspaceSchema.safeParse({ version: 2 }).success).toBe(false);
  });
});

import {
  articleSchema,
  isValidDate,
  localDateKey,
  projectSchema,
  monthDays,
  newProject,
  removeProject,
  searchWorkspace,
  type Workspace,
} from "./model";
const makeWorkspace = (): Workspace => {
  const first = {
    ...newProject("Kedai Bogor", "kedai.example", "Bogor"),
    id: "first",
  };
  const second = {
    ...newProject("Roti Jakarta", "roti.example", "Jakarta"),
    id: "second",
  };
  second.keywords = "harga roti\nroti jakarta";
  second.articles = [
    {
      id: "bread",
      title: "Panduan roti",
      keyword: "roti lokal",
      date: "2026-11-06",
      status: "Ide",
    },
  ];
  return { version: 1, projects: [first, second], activeId: first.id };
};
it("menyimpan jenis usaha sebagai kunci utama tanpa merusak cadangan lama", () => {
  const project = newProject("Kedai Kopi", "kopi.example", "Bogor", "kafe-kedai");
  expect(project.industry).toBe("kafe-kedai");
  // Cadangan dari versi sebelum kolom ini ada harus tetap bisa dibuka.
  const lama = { ...newProject("Lama", "", "Bogor") } as Record<string, unknown>;
  delete lama.industry;
  const parsed = projectSchema.safeParse(lama);
  expect(parsed.success).toBe(true);
  expect(parsed.success && parsed.data.industry).toBe("");
});

it("menerima jenis usaha yang belum dipilih dan menolak yang terlalu panjang", () => {
  const kosong = newProject("Tanpa jenis", "", "");
  expect(projectSchema.safeParse(kosong).success).toBe(true);
  const panjang = { ...kosong, industry: "x".repeat(61) };
  expect(projectSchema.safeParse(panjang).success).toBe(false);
});

it("validates real dates including leap years instead of accepting impossible days", () => {
  expect(isValidDate("2024-02-29")).toBe(true);
  expect(
    articleSchema.safeParse({
      id: "x",
      title: "Roti",
      keyword: "",
      date: "2026-02-30",
      status: "Ide",
    }).success,
  ).toBe(false);
  expect(isValidDate("2026-13-01")).toBe(false);
  expect(isValidDate("1800-01-01")).toBe(false);
});
it("builds Monday-first calendars with every real date and proper padding", () => {
  const days = monthDays("2026-11");
  expect(days).toHaveLength(42);
  expect(days.slice(0, 6)).toEqual(Array(6).fill(null));
  expect(days.filter(Boolean)).toHaveLength(30);
  expect(monthDays("2024-02").filter(Boolean)).toHaveLength(29);
  expect(localDateKey(new Date(2026, 0, 2, 0))).toBe("2026-01-02");
});
it("removes only the selected project and selects a surviving project", () => {
  const ws = makeWorkspace();
  const next = removeProject(ws, "first");
  expect(next.activeId).toBe("second");
  expect(next.projects[0].articles).toHaveLength(1);
  expect(ws.projects).toHaveLength(2);
  expect(removeProject(next, "second")).toBe(next);
});
it("searches content, project metadata, and keywords across projects", () => {
  const results = searchWorkspace(makeWorkspace(), "  ROTI  ");
  expect(new Set(results.map((r) => r.kind))).toEqual(
    new Set(["Proyek", "Konten", "Kata kunci"]),
  );
  expect(results.every((r) => r.projectId === "second")).toBe(true);
  expect(searchWorkspace(makeWorkspace(), "not found")).toEqual([]);
  expect(searchWorkspace(makeWorkspace(), "   ")).toEqual([]);
});
it("validates backup relationships consistently for import and browser loading", () => {
  const ws = makeWorkspace();
  expect(workspaceSchema.safeParse(ws).success).toBe(true);
  expect(
    workspaceSchema.safeParse({ ...ws, activeId: "missing" }).success,
  ).toBe(false);
  expect(
    workspaceSchema.safeParse({
      ...ws,
      projects: [ws.projects[0], ws.projects[0]],
    }).success,
  ).toBe(false);
  ws.projects[0].checks = ["fake-task"];
  expect(workspaceSchema.safeParse(ws).success).toBe(false);
});

import { beginnerProgress, contentIdeas } from "./beginner";
it("does not mistake sample data for beginner progress", () => {
  const project = makeWorkspace().projects[1];
  expect(
    beginnerProgress({ ...project, id: "contoh", checks: ["nap"] }),
  ).toEqual([false, false, false]);
  expect(beginnerProgress(project)).toEqual([true, false, true]);
});
it("completes beginner steps only from actual project work", () => {
  const project = makeWorkspace().projects[0];
  expect(beginnerProgress(project)).toEqual([true, false, false]);
  expect(beginnerProgress({ ...project, checks: ["nap"] })).toEqual([
    true,
    true,
    false,
  ]);
});
it("creates editable content suggestions without invented search data", () => {
  expect(contentIdeas("  ", "Bogor")).toEqual([]);
  const ideas = contentIdeas(" roti ulang tahun ", " Bogor ");
  expect(ideas).toHaveLength(3);
  expect(ideas[0]).toEqual({
    title: "Panduan memilih roti ulang tahun di Bogor",
    keyword: "roti ulang tahun di Bogor",
  });
  expect(contentIdeas("roti", "")[0].title).toBe("Panduan memilih roti");
});

it("neutralizes formulas preceded by whitespace or control characters in CSV exports", () => {
  for (const value of [
    " =1+1",
    "\n=1+1",
    "\ufeff@SUM(1)",
    "\u0000+1",
    "\t=1+1",
  ])
    expect(csvCell(value).startsWith("\"'")).toBe(true);
  expect(csvCell("Normal text")).toBe('"Normal text"');
});
