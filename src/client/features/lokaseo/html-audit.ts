import { evaluateAudit, type AuditFacts } from "./model";
export function parseHtmlAudit(html: string): AuditFacts {
  if (!html.trim())
    throw new Error("Tempel kode HTML halaman terlebih dahulu.");
  if (/^https?:\/\/\S+$/i.test(html.trim()))
    throw new Error(
      "Ini alamat situs, bukan kode HTML. Salin kode melalui Lihat sumber halaman, atau pilih berkas .html.",
    );
  if (!/<(?:!doctype\s+html|html|head|body|title|meta|h1)\b/i.test(html))
    throw new Error(
      "Kode halaman belum ditemukan. Tempel kode HTML, bukan teks artikel atau alamat situs.",
    );
  if (html.length > 2_000_000)
    throw new Error("HTML terlalu besar. Batas audit adalah 2 MB karakter.");
  // Inert document. Never insert uploaded markup into the live DOM or execute it.
  const doc = new DOMParser().parseFromString(html, "text/html");
  const metas = [...doc.querySelectorAll("meta")];
  const meta = (name: string) =>
    metas
      .find((m) => m.getAttribute("name")?.toLowerCase() === name)
      ?.getAttribute("content") ?? "";
  const localTypes = new Set([
    "LocalBusiness",
    "Restaurant",
    "Store",
    "CafeOrCoffeeShop",
    "Dentist",
    "Hotel",
    "AutoRepair",
    "ProfessionalService",
    "MedicalBusiness",
    "Bakery",
    "HairSalon",
    "RealEstateAgent",
  ]);
  const hasLocal = (v: unknown): boolean => {
    if (!v || typeof v !== "object") return false;
    if (Array.isArray(v)) return v.some(hasLocal);
    const obj = v as Record<string, unknown>;
    const types = Array.isArray(obj["@type"]) ? obj["@type"] : [obj["@type"]];
    return (
      types.some((t) => typeof t === "string" && localTypes.has(t)) ||
      Object.values(obj).some(hasLocal)
    );
  };
  const facts: AuditFacts = {
    title: doc.title.trim(),
    description: meta("description").trim(),
    h1: doc.querySelectorAll("h1").length,
    lang: doc.documentElement.lang,
    canonical: [...doc.querySelectorAll("link")].some(
      (l) =>
        l.rel.toLowerCase().split(/\s+/).includes("canonical") &&
        !!l.getAttribute("href")?.trim(),
    ),
    images: doc.images.length,
    missingAlt: [...doc.images].filter((i) => !i.hasAttribute("alt")).length,
    viewport: /width\s*=\s*device-width/i.test(meta("viewport")),
    noindex: metas.some(
      (m) =>
        ["robots", "googlebot"].includes(
          m.getAttribute("name")?.toLowerCase() ?? "",
        ) && /\b(?:noindex|none)\b/i.test(m.getAttribute("content") ?? ""),
    ),
    localSchema: [
      ...doc.querySelectorAll('script[type="application/ld+json"]'),
    ].some((s) => {
      try {
        return hasLocal(JSON.parse(s.textContent ?? ""));
      } catch {
        return false;
      }
    }),
  };
  evaluateAudit(facts);
  return facts;
}
