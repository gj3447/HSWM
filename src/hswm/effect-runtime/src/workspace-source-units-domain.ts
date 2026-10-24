/** Complete ATX Markdown sections, preserving every byte and fenced code. No I/O. */
import { kgSha256 } from "./native-kg-bundle-domain.js"

export const workspaceSourceUnits = (document: string) => {
  const starts: Array<{ offset: number; heading: { level: number; text: string } | null }> = [{ offset: 0, heading: null }]
  let offset = 0
  let fence: { character: string; length: number } | null = null
  for (const line of document.match(/[^\n]*\n|[^\n]+$/g) ?? []) {
    const delimiter = /^ {0,3}(`{3,}|~{3,})([^\r\n]*)/.exec(line)
    if (fence) {
      if (delimiter?.[1]?.[0] === fence.character && delimiter[1].length >= fence.length && !delimiter[2]?.trim()) fence = null
    } else if (delimiter?.[1] && !(delimiter[1][0] === "`" && delimiter[2]?.includes("`"))) {
      fence = { character: delimiter[1][0] ?? "`", length: delimiter[1].length }
    } else {
      const match = /^ {0,3}(#{1,6})[\t ]+([^\r\n]*)/.exec(line)
      if (match?.[1] && match[2] !== undefined) {
        const start = { offset, heading: { level: match[1].length, text: match[2].trim() } }
        if (offset === 0) starts[0] = start
        else starts.push(start)
      }
    }
    offset += line.length
  }
  let byteOffset = 0
  return starts.map((start, i) => {
    const text = document.slice(start.offset, starts[i + 1]?.offset ?? document.length)
    const startByte = byteOffset
    byteOffset += new TextEncoder().encode(text).byteLength
    return { id: `section:${i}`, startByte, endByte: byteOffset, sha256: kgSha256(text), heading: start.heading, text }
  })
}
