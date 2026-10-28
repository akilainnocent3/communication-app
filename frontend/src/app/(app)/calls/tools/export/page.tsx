"use client";

import { useState } from "react";
import { usePageTitle } from "@/components/shell/trail";
import { DownloadIcon } from "@/components/ui/icons";
import { Page, PageHeader } from "@/components/ui/page";
import { SectionCard } from "@/components/ui/section-card";
import { m } from "@/i18n";
import { query } from "@/services/api/client";
import { scopeParam, useCallsScope } from "@/platforms/calls/api/queries";

const INPUT = "h-9 rounded-lg border border-card-border bg-card-surface-area px-2 text-sm text-text-primary";

export default function ExportPage() {
  usePageTitle({ page: "Export", section: "Calls" });
  const [scope] = useCallsScope();
  const [folder, setFolder] = useState("all");
  const [after, setAfter] = useState("");
  const [before, setBefore] = useState("");
  const href = (format: "csv" | "xlsx") => `/api/v1/calls/export/${query({ device: scopeParam(scope), folder, after: after || undefined, before: before || undefined, file_format: format })}`;
  return (
    <Page>
      <PageHeader eyebrow="Tools" title="Export calls" description="CSV or Excel, for the selected phone(s). Numbers are masked on phones where you lack export access. Notes are never exported. Every export is logged." />
      <SectionCard>
        <div className="flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-sm"><span className="font-medium">Calls</span>
            <select value={folder} onChange={(e) => setFolder(e.target.value)} className={INPUT}>{Object.entries(m.calls.folders).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
          </label>
          <label className="grid gap-1 text-sm"><span className="font-medium">From</span><input type="date" value={after} onChange={(e) => setAfter(e.target.value)} className={INPUT} /></label>
          <label className="grid gap-1 text-sm"><span className="font-medium">To</span><input type="date" value={before} onChange={(e) => setBefore(e.target.value)} className={INPUT} /></label>
          <a href={href("csv")} className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-primary-500 px-3 text-sm font-medium text-white hover:bg-primary-600" download><DownloadIcon size={16} />CSV</a>
          <a href={href("xlsx")} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-card-border px-3 text-sm font-medium hover:bg-background-gray-secondary_alt" download><DownloadIcon size={16} />Excel</a>
        </div>
      </SectionCard>
    </Page>
  );
}
