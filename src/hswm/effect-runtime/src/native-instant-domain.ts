/** Pure offset-bearing timestamp decoding, preserving Python's microsecond comparison. */
export const nativeInstantMicroseconds = (value: unknown): bigint | null => {
  if (typeof value !== "string") return null
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:[.,](\d+))?(Z|[+-]\d{2}:?\d{2}(?::?\d{2}(?:[.,]\d+)?)?)$/u.exec(value)
  if (m === null) return null
  const year=Number(m[1]),month=Number(m[2]),day=Number(m[3]),hour=Number(m[4]),minute=Number(m[5]),second=Number(m[6])
  if (year < 1 || year > 9999) return null
  const date=new Date(0)
  date.setUTCFullYear(year,month-1,day);date.setUTCHours(hour,minute,second,0)
  if(date.getUTCFullYear()!==year||date.getUTCMonth()!==month-1||date.getUTCDate()!==day||date.getUTCHours()!==hour||date.getUTCMinutes()!==minute||date.getUTCSeconds()!==second)return null
  const fraction=BigInt((m[7]??"").slice(0,6).padEnd(6,"0")),zone=m[8]
  if(zone===undefined)return null
  if(zone==="Z")return BigInt(date.getTime())*1000n+fraction
  const z=/^([+-])(\d{2}):?(\d{2})(?::?(\d{2})(?:[.,](\d+))?)?$/u.exec(zone)
  if(z===null)return null
  const zh=Number(z[2]),zm=Number(z[3]),zs=Number(z[4]??0)
  if(zh>23||zm>59||zs>59)return null
  const offset=BigInt(zh*3600+zm*60+zs)*1000000n+BigInt((z[5]??"").slice(0,6).padEnd(6,"0"))
  return BigInt(date.getTime())*1000n+fraction-(z[1]==="+"?offset:-offset)
}
