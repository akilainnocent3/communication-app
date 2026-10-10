import type { Participant } from "@/services/api/types";

/** Gmail-style sender line: "me, Amina, Juma (3)" with unread senders marked. */
export function senderLine(participants: Participant[] | undefined, count?: number) {
  const list = participants ?? [];
  const names = list.map((p) => (p.is_me ? "me" : firstName(p.name || p.email)));
  const unique = names.filter((name, index) => names.indexOf(name) === index);
  const text = unique.length > 3 ? `${unique[0]} … ${unique.slice(-2).join(", ")}` : unique.join(", ");
  return { text: text || "(no sender)", count: count && count > 1 ? count : undefined };
}

export function firstName(name: string) {
  const clean = name.replace(/["']/g, "").trim();
  if (clean.includes("@")) return clean.split("@")[0];
  return clean.split(/\s+/)[0] || clean;
}

export function displayName(address: { name?: string; email: string } | null | undefined) {
  if (!address) return "Unknown sender";
  return address.name?.trim() || address.email;
}
