/**
 * How the carrier splits a text: 160/153 GSM-7 septets or 70/67 UCS-2 units per (multipart) segment. Mirrors
 * backend `modules/sms/services/text.py` and the phone's counter, so all three agree.
 */
const GSM7_BASIC = new Set(
  "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà",
);
const GSM7_EXTENDED = new Set("^{}\\[~]|€\f");

export type SegmentInfo = { encoding: "gsm7" | "ucs2"; units: number; segments: number; perSegment: number; remaining: number };

export function segmentInfo(text: string): SegmentInfo {
  const chars = Array.from(text);
  const gsm = chars.every((ch) => GSM7_BASIC.has(ch) || GSM7_EXTENDED.has(ch));
  const units = gsm ? chars.reduce((sum, ch) => sum + (GSM7_EXTENDED.has(ch) ? 2 : 1), 0) : text.length; // JS length = UTF-16 units
  const [single, multi] = gsm ? [160, 153] : [70, 67];
  if (units <= single) return { encoding: gsm ? "gsm7" : "ucs2", units, segments: 1, perSegment: single, remaining: single - units };
  const segments = Math.ceil(units / multi);
  return { encoding: gsm ? "gsm7" : "ucs2", units, segments, perSegment: multi, remaining: segments * multi - units };
}

export function withSignature(body: string, signature: string | undefined, enabled: boolean | undefined): string {
  const sig = (signature ?? "").trim();
  if (!enabled || !sig || body.trimEnd().endsWith(sig)) return body;
  return `${body.trimEnd()}\n${sig}`;
}
