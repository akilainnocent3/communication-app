import { formatInTimeZone, toZonedTime } from "date-fns-tz";
import { differenceInCalendarDays, formatDistanceToNowStrict } from "date-fns";

export const DEFAULT_TIMEZONE = "Africa/Dar_es_Salaam";

let currentZone = DEFAULT_TIMEZONE;
/** Set once from the signed-in user's profile; every formatter below uses it. */
export function setTimezone(zone: string | undefined | null) {
  currentZone = zone || DEFAULT_TIMEZONE;
}
export function timezone() {
  return currentZone;
}

function toDate(value: string | Date | number) {
  return value instanceof Date ? value : new Date(value);
}

/** Gmail-style list time: "10:42" today, "Tue" this week, "3 Oct" this year, "3 Oct 2024" otherwise. */
export function listTime(value: string | Date) {
  const date = toDate(value);
  const now = new Date();
  const days = differenceInCalendarDays(toZonedTime(now, currentZone), toZonedTime(date, currentZone));
  if (days === 0) return formatInTimeZone(date, currentZone, "HH:mm");
  if (days > 0 && days < 7) return formatInTimeZone(date, currentZone, "EEE");
  if (formatInTimeZone(date, currentZone, "yyyy") === formatInTimeZone(now, currentZone, "yyyy")) return formatInTimeZone(date, currentZone, "d MMM");
  return formatInTimeZone(date, currentZone, "d MMM yyyy");
}

/** "Tue, 3 Oct 2026, 10:42" */
export function fullDate(value: string | Date) {
  return formatInTimeZone(toDate(value), currentZone, "EEE, d MMM yyyy, HH:mm");
}

export function shortDate(value: string | Date) {
  return formatInTimeZone(toDate(value), currentZone, "d MMM yyyy");
}

export function dateTime(value: string | Date) {
  return formatInTimeZone(toDate(value), currentZone, "d MMM, HH:mm");
}

export function ago(value: string | Date) {
  return `${formatDistanceToNowStrict(toDate(value))} ago`;
}

/** "10:42 (2 hours ago)" style used in the thread header. */
export function messageTime(value: string | Date) {
  const date = toDate(value);
  return `${listTime(date)} (${ago(date)})`;
}

export function bytes(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export function compactNumber(value: number) {
  return new Intl.NumberFormat("en", { notation: value >= 10_000 ? "compact" : "standard" }).format(value);
}

export function initials(name: string) {
  const words = name.trim().split(/[\s._@-]+/).filter(Boolean);
  if (!words.length) return "?";
  return ((words[0][0] ?? "") + (words.length > 1 ? words[words.length - 1][0] : "")).toUpperCase();
}

/** A stable soft colour for an avatar from a string (sender email). */
export function avatarHue(seed: string) {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  return Math.abs(hash) % 360;
}

export function minutesLabel(minutes: number | null | undefined) {
  if (minutes === null || minutes === undefined) return "—";
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const hours = minutes / 60;
  if (hours < 48) return `${hours.toFixed(1)} h`;
  return `${(hours / 24).toFixed(1)} d`;
}
