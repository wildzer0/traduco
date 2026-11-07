import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { createTemplateWithWizard, type WizardOptions, wizardFonts } from "../../lib/api";
import { useT } from "../../lib/i18n";
import type { TemplateDetail } from "../../lib/types";

const COVER_FIELDS = ["codice_documento", "revisione", "data", "cliente", "autore"] as const;
const DEFAULTS: WizardOptions = {
  page: "A4",
  font_body: "Calibri",
  font_heading: "Calibri",
  size_body: 11,
  color: "1F4E79",
  margin_cm: 2.5,
  cover: true,
  cover_fields: ["codice_documento", "revisione", "data"],
  header_text: "{{codice_documento}} – {{nome}}",
  footer_text: "",
  page_numbers: true,
  logo_in_header: true,
  toc: true,
  revisions: true,
  language: "it",
};

const toBase64 = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });

/** "Create a template" in four steps (RF-55) with a live sketch of the first pages. */
export function TemplateWizard({
  projectId,
  onCreated,
  onCancel,
}: {
  projectId: string;
  onCreated: (created: TemplateDetail) => void;
  onCancel: () => void;
}) {
  const t = useT();
  const [step, setStep] = useState(1);
  const [name, setName] = useState("aziendale");
  const [o, setO] = useState<WizardOptions>(DEFAULTS);
  const [logo, setLogo] = useState<File | null>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: fonts = [DEFAULTS.font_body] } = useQuery({
    queryKey: ["wizard-fonts"],
    queryFn: wizardFonts,
  });
  const set = <K extends keyof WizardOptions>(key: K, value: WizardOptions[K]) =>
    setO((prev) => ({ ...prev, [key]: value }));

  const pickLogo = (file: File | undefined) => {
    if (logoUrl) URL.revokeObjectURL(logoUrl);
    setLogo(file ?? null);
    setLogoUrl(file ? URL.createObjectURL(file) : null);
  };

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await createTemplateWithWizard(projectId, {
        nome: name.trim() || "template",
        opzioni: { ...o, color: o.color.replace("#", "") },
        ...(logo ? { logo_base64: await toBase64(logo) } : {}),
      });
      onCreated(created);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const color = `#${o.color.replace("#", "")}`;
  const field = "mt-1 w-full rounded-ui border border-border bg-bg px-2 py-1";
  const check = (label: string, value: boolean, on: (v: boolean) => void) => (
    <label className="mt-2 flex items-center gap-2">
      <input type="checkbox" checked={value} onChange={(e) => on(e.target.checked)} />
      {label}
    </label>
  );

  return (
    <div
      role="dialog"
      aria-label={t("wizard.title")}
      className="mt-3 rounded-ui border border-border p-3"
    >
      <h3 className="m-0 text-[14px] font-semibold">{t("wizard.title")}</h3>
      <p className="m-0 mt-1 text-[12px] text-muted">
        {t("wizard.step", { n: step })} · {t(`wizard.step${step}` as "wizard.step1")}
      </p>

      {step === 1 && (
        <>
          <label className="mt-2 block">
            {t("wizard.name")}
            <input className={field} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="mt-2 block">
            {t("wizard.page")}
            <select
              className={field}
              value={o.page}
              onChange={(e) => set("page", e.target.value as "A4" | "Letter")}
            >
              <option value="A4">A4</option>
              <option value="Letter">Letter</option>
            </select>
          </label>
          <label className="mt-2 block">
            {t("wizard.fontBody")}
            <select
              className={field}
              value={o.font_body}
              onChange={(e) => set("font_body", e.target.value)}
            >
              {fonts.map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
          </label>
          <label className="mt-2 block">
            {t("wizard.fontHeading")}
            <select
              className={field}
              value={o.font_heading}
              onChange={(e) => set("font_heading", e.target.value)}
            >
              {fonts.map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
          </label>
          <label className="mt-2 block">
            {t("wizard.size")}
            <input
              className={field}
              type="number"
              min={8}
              max={16}
              step={0.5}
              value={o.size_body}
              onChange={(e) => set("size_body", Number(e.target.value))}
            />
          </label>
          <label className="mt-2 block">
            {t("wizard.color")}
            <input
              className={field}
              type="color"
              value={color}
              onChange={(e) => set("color", e.target.value.slice(1).toUpperCase())}
            />
          </label>
          <label className="mt-2 block">
            {t("wizard.margin")}
            <input
              className={field}
              type="number"
              min={1}
              max={5}
              step={0.5}
              value={o.margin_cm}
              onChange={(e) => set("margin_cm", Number(e.target.value))}
            />
          </label>
        </>
      )}

      {step === 2 && (
        <>
          {check(t("wizard.cover"), o.cover, (v) => set("cover", v))}
          {o.cover && (
            <fieldset className="mt-2 border-0 p-0">
              <legend className="text-[13px]">{t("wizard.coverFields")}</legend>
              {COVER_FIELDS.map((f) => (
                <label key={f} className="mt-1 flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={o.cover_fields.includes(f)}
                    onChange={(e) =>
                      set(
                        "cover_fields",
                        e.target.checked
                          ? [...o.cover_fields, f]
                          : o.cover_fields.filter((x) => x !== f),
                      )
                    }
                  />
                  {t(`wizard.field.${f}` as "wizard.field.data")}
                </label>
              ))}
            </fieldset>
          )}
        </>
      )}

      {step === 3 && (
        <>
          <label className="mt-2 block">
            {t("wizard.header")}
            <input
              className={field}
              value={o.header_text}
              onChange={(e) => set("header_text", e.target.value)}
            />
          </label>
          <label className="mt-2 block">
            {t("wizard.footer")}
            <input
              className={field}
              value={o.footer_text}
              onChange={(e) => set("footer_text", e.target.value)}
            />
          </label>
          {check(t("wizard.pageNumbers"), o.page_numbers, (v) => set("page_numbers", v))}
          <label className="mt-2 block">
            {t("wizard.logo")}
            <input
              className={field}
              type="file"
              accept="image/png,image/jpeg"
              onChange={(e) => pickLogo(e.target.files?.[0])}
            />
          </label>
          {logo && (
            <>
              {check(t("wizard.logoHeader"), o.logo_in_header, (v) => set("logo_in_header", v))}
              <button
                type="button"
                className="mt-1 text-[12px] underline"
                onClick={() => pickLogo(undefined)}
              >
                {t("wizard.logoRemove")}
              </button>
            </>
          )}
        </>
      )}

      {step === 4 && (
        <>
          {check(t("wizard.toc"), o.toc, (v) => set("toc", v))}
          {check(t("wizard.revisions"), o.revisions, (v) => set("revisions", v))}
          <label className="mt-2 block">
            {t("wizard.language")}
            <select
              className={field}
              value={o.language}
              onChange={(e) => set("language", e.target.value as "it" | "en")}
            >
              <option value="it">Italiano</option>
              <option value="en">English</option>
            </select>
          </label>
        </>
      )}

      <figure aria-label={t("wizard.preview")} className="m-0 mt-3 flex gap-2">
        <Sheet o={o} color={color} logoUrl={logoUrl} cover />
        <Sheet o={o} color={color} logoUrl={logoUrl} />
      </figure>

      {error && (
        <p role="alert" className="m-0 mt-2 text-[13px] text-red">
          {error}
        </p>
      )}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={step === 1 ? onCancel : () => setStep(step - 1)}
          className="rounded-ui border border-border px-3 py-1.5 hover:bg-surface-2"
        >
          {step === 1 ? t("wizard.cancel") : t("wizard.back")}
        </button>
        {step < 4 ? (
          <button
            type="button"
            onClick={() => setStep(step + 1)}
            className="rounded-ui bg-accent px-3 py-1.5 text-accent-fg"
          >
            {t("wizard.next")}
          </button>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() => void create()}
            className="rounded-ui bg-accent px-3 py-1.5 text-accent-fg disabled:opacity-50"
          >
            {t("wizard.create")}
          </button>
        )}
      </div>
    </div>
  );
}

/** A rough sketch of a page: enough to see fonts, colour, cover, header and footer. */
function Sheet({
  o,
  color,
  logoUrl,
  cover = false,
}: {
  o: WizardOptions;
  color: string;
  logoUrl: string | null;
  cover?: boolean;
}) {
  if (cover && !o.cover) return null;
  const ratio = o.page === "A4" ? 297 / 210 : 11 / 8.5;
  const pad = `${Math.round(o.margin_cm * 4)}px`;
  const small = Math.max(5, o.size_body * 0.55);
  return (
    <div
      aria-hidden
      className="flex flex-1 flex-col overflow-hidden border border-border bg-white text-black"
      style={{
        aspectRatio: `1 / ${ratio}`,
        padding: pad,
        fontFamily: o.font_body,
        fontSize: small,
      }}
    >
      {!cover && (
        <div
          className="flex items-center justify-between border-b border-border pb-1"
          style={{ fontSize: 5 }}
        >
          <span>{o.header_text}</span>
          {o.logo_in_header && logoUrl && <img src={logoUrl} alt="" style={{ height: 8 }} />}
        </div>
      )}
      {cover ? (
        <div className="mt-6 text-center">
          {logoUrl && <img src={logoUrl} alt="" className="mx-auto mb-2" style={{ height: 18 }} />}
          <div style={{ color, fontFamily: o.font_heading, fontSize: small * 2, fontWeight: 700 }}>
            Titolo
          </div>
          {o.cover_fields.map((f) => (
            <div key={f} style={{ fontSize: small }}>
              {f.replace("_", " ")}
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-1 flex-1">
          <div
            style={{ color, fontFamily: o.font_heading, fontSize: small * 1.5, fontWeight: 700 }}
          >
            1 Capitolo
          </div>
          <div className="mt-1 h-1 bg-surface-2" />
          <div className="mt-1 h-1 bg-surface-2" />
          <div className="mt-1 h-1 w-2/3 bg-surface-2" />
        </div>
      )}
      <div className="flex justify-between" style={{ fontSize: 5 }}>
        <span>{o.footer_text}</span>
        {o.page_numbers && !cover && <span>1</span>}
      </div>
    </div>
  );
}
