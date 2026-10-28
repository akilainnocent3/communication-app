"use client";

import { useState } from "react";
import { toast } from "sonner";
import { usePageTitle } from "@/components/shell/trail";
import { useSession } from "@/components/shell/session-provider";
import { Button } from "@/components/tailgrids/core/button";
import { Page, PageHeader } from "@/components/ui/page";
import { RequestState } from "@/components/ui/request-state";
import { SectionCard } from "@/components/ui/section-card";
import { errorMessage } from "@/services/api/client";
import type { OfficeHours } from "@/services/api/types";
import { useCallsWrite } from "@/platforms/calls/api/actions";
import { callsKeys } from "@/platforms/calls/api/keys";
import { useOfficeHours } from "@/platforms/calls/api/queries";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const INPUT = "h-9 rounded-lg border border-card-border bg-card-surface-area px-2 text-sm text-text-primary disabled:opacity-60";

export default function OfficeHoursPage() {
  usePageTitle({ page: "Office hours", section: "Calls" });
  const hours = useOfficeHours();
  return (
    <Page>
      <PageHeader eyebrow="Tools" title="Office hours" description="Calls outside these hours count as after hours. Each office uses its own time zone and holidays." />
      {hours.isPending || hours.error ? <RequestState loading={hours.isPending} error={hours.error ? errorMessage(hours.error) : undefined} onRetry={() => hours.refetch()} /> : (
        <div className="space-y-4">{hours.data!.map((row) => <OfficeCard key={row.office} row={row} />)}</div>
      )}
    </Page>
  );
}

function OfficeCard({ row }: { row: OfficeHours }) {
  const { can } = useSession();
  const disabled = !can("calls.manage_settings");
  const write = useCallsWrite<OfficeHours>(callsKeys.hours());
  const [tz, setTz] = useState(row.timezone);
  const [week, setWeek] = useState<Record<string, string[][]>>(row.week as Record<string, string[][]>);
  const [holidays, setHolidays] = useState(row.holidays.join(", "));
  const range = (day: string): string[] => week[day]?.[0] ?? ["", ""];
  const setRange = (day: string, index: 0 | 1, value: string) => {
    const current = range(day);
    const next = index === 0 ? [value, current[1]] : [current[0], value];
    setWeek({ ...week, [day]: next[0] && next[1] ? [next] : next[0] || next[1] ? [next] : [] });
  };
  return (
    <SectionCard title={row.office_name} description={row.configured ? "Custom hours" : "Default hours (Mon–Fri 08–17, Sat 08–13)"}>
      <form className="space-y-3" onSubmit={(e) => {
        e.preventDefault();
        const clean = Object.fromEntries(Object.entries(week).map(([d, r]) => [d, (r ?? []).filter((x) => x[0] && x[1])]));
        write.mutate({ path: `calls/office-hours/${row.office}/`, method: "PUT", body: { timezone: tz, week: clean, holidays: holidays.split(",").map((h) => h.trim()).filter(Boolean) } },
          { onSuccess: () => toast.success("Office hours saved") });
      }}>
        <label className="grid max-w-xs gap-1 text-sm"><span className="font-medium">Time zone</span><input disabled={disabled} value={tz} onChange={(e) => setTz(e.target.value)} className={INPUT} /></label>
        <table className="text-sm"><tbody>
          {DAYS.map((label, index) => {
            const day = String(index + 1);
            const [start, end] = range(day);
            return (
              <tr key={day}>
                <th scope="row" className="py-1 pr-3 text-left font-normal text-text-secondary">{label}</th>
                <td className="py-1"><input disabled={disabled} type="time" aria-label={`${label} opens`} value={start} onChange={(e) => setRange(day, 0, e.target.value)} className={INPUT} /></td>
                <td className="px-2 text-text-tertiary">–</td>
                <td className="py-1"><input disabled={disabled} type="time" aria-label={`${label} closes`} value={end} onChange={(e) => setRange(day, 1, e.target.value)} className={INPUT} /></td>
                <td className="pl-2 text-xs text-text-tertiary">{(week[day] ?? []).length > 1 ? `+${(week[day] ?? []).length - 1} more` : !start ? "Closed" : ""}</td>
              </tr>
            );
          })}
        </tbody></table>
        <label className="grid gap-1 text-sm"><span className="font-medium">Holidays (YYYY-MM-DD, comma separated)</span><input disabled={disabled} value={holidays} onChange={(e) => setHolidays(e.target.value)} className={`${INPUT} w-full`} /></label>
        {!disabled && <Button type="submit" isPending={write.isPending}>Save</Button>}
      </form>
    </SectionCard>
  );
}
