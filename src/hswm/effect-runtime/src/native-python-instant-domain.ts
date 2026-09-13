/** Pure Python datetime.fromisoformat offset-aware subset, including ISO week dates. */
const supportedUtc = (micros: bigint): bigint | null => micros >= -62135596800000000n && micros <= 253402300799999999n ? micros : null
export const nativePythonInstantMicroseconds = (input: unknown): bigint | null => {
  if (typeof input !== "string") return null
  const match = /^(\d{4}(?:-\d{2}-\d{2}|\d{4}|-W\d{2}(?:-\d)?|W\d{2}\d?))(.)(.+)$/su.exec(input)
  if (match === null) return null
  const dateText = match[1]!, timeText = match[3]!
  const year = Number(dateText.slice(0, 4))
  if (year < 1 || year > 9999) return null
  const date = new Date(0)
  if (dateText.includes("W")) {
    const week = /^\d{4}-?W(\d{2})(?:-?(\d))?$/u.exec(dateText)
    if (week === null) return null
    const number = Number(week[1]), weekday = Number(week[2] ?? "1")
    if (number < 1 || number > 53 || weekday < 1 || weekday > 7) return null
    date.setUTCFullYear(year, 0, 4)
    date.setUTCHours(0, 0, 0, 0)
    date.setUTCDate(date.getUTCDate() - (date.getUTCDay() + 6) % 7 + (number - 1) * 7)
    const thursday = new Date(date.getTime())
    thursday.setUTCDate(thursday.getUTCDate() + 3)
    if (thursday.getUTCFullYear() !== year) return null
    date.setUTCDate(date.getUTCDate() + weekday - 1)
  } else {
    const compact = dateText.replaceAll("-", ""), month = Number(compact.slice(4, 6)), day = Number(compact.slice(6, 8))
    date.setUTCFullYear(year, month - 1, day)
    date.setUTCHours(0, 0, 0, 0)
    if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null
  }
  const time = /^(\d{2}(?::\d{2}(?::\d{2})?|\d{2}(?:\d{2})?)?)(?:[.,](\d+))?(Z|[+-]\d{2}(?::\d{2}(?::\d{2})?|\d{2}(?:\d{2})?)?(?:[.,]\d+)?)$/u.exec(timeText)
  if (time === null) return null
  const clock = time[1]!.replaceAll(":", ""), hour = Number(clock.slice(0, 2)), minute = Number(clock.slice(2, 4) || "0"), second = Number(clock.slice(4, 6) || "0")
  if (hour > 23 || minute > 59 || second > 59) return null
  const fraction = BigInt((time[2] ?? "").slice(0, 6).padEnd(6, "0"))
  const zone = time[3]!
  const local = BigInt(date.getTime()) * 1000n + BigInt(hour * 3600 + minute * 60 + second) * 1000000n + fraction
  if (zone === "Z") return supportedUtc(local)
  const offset = /^([+-])([\d:]+)(?:[.,](\d+))?$/u.exec(zone)
  if (offset === null) return null
  const digits = offset[2]!.replaceAll(":", ""), zh = Number(digits.slice(0, 2)), zm = Number(digits.slice(2, 4) || "0"), zs = Number(digits.slice(4, 6) || "0")
  // Python normalizes oversized minute/second fields; the total must stay below one day.
  const whole = zh * 3600 + zm * 60 + zs
  const micros = whole === 0 ? 0n : BigInt(whole) * 1000000n + BigInt((offset[3] ?? "").slice(0, 6).padEnd(6, "0"))
  if (micros >= 86400000000n) return null
  return supportedUtc(local - (offset[1] === "+" ? micros : -micros))
}
export const nativePythonInstantSeconds = (input: unknown): number | null => {
  const micros = nativePythonInstantMicroseconds(input)
  return micros === null ? null : Number(micros) / 1000000
}
