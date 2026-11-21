/** Indian digit grouping: 1234567 -> 12,34,567 */
export function inr(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  const neg = n < 0;
  const s = String(Math.abs(Math.round(n)));
  let out = s;
  if (s.length > 3) {
    let head = s.slice(0, -3);
    const tail = s.slice(-3);
    const parts: string[] = [];
    while (head.length > 2) {
      parts.unshift(head.slice(-2));
      head = head.slice(0, -2);
    }
    if (head) parts.unshift(head);
    out = parts.join(",") + "," + tail;
  }
  return (neg ? "-" : "") + out;
}
export const rupee = (n: number | null | undefined) => "₹" + inr(n);
export const dateOnly = (s?: string | null) => (s ? s.slice(0, 10) : "-");
/** Compact: 1,23,45,678 -> "1.23 Cr" / "12.3 L" */
export function crore(n: number): string {
  if (Math.abs(n) >= 1e7) return (n / 1e7).toFixed(2) + " Cr";
  if (Math.abs(n) >= 1e5) return (n / 1e5).toFixed(1) + " L";
  return inr(n);
}
/** Ward codes contain "/" (K/E); URLs use "K-E". */
export const wardSlug = (c: string) => c.replace("/", "-");
export const wardCode = (s: string) => decodeURIComponent(s).replace("-", "/").toUpperCase();
