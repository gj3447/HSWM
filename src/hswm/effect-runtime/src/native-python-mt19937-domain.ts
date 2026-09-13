/** Immutable Python `random.Random(integer_seed)` MT19937 primitives. */
const u32 = (value: number): number => value >>> 0;
export interface NativePythonMt19937State {
    readonly index: number;
    readonly state: readonly number[];
}
const words = (seed: bigint): readonly number[] => { let rest = seed < 0n ? -seed : seed; const out: number[] = []; do {
    out.push(Number(rest & 0xffffffffn));
    rest >>= 32n;
} while (rest !== 0n); return Object.freeze(out); };
/** Python's recurrence observes earlier replacements in this twist pass. */
const twist = (state: readonly number[]): readonly number[] => { const next = [...state]; for (let index = 0; index < 624; index += 1) {
    const mixed = (next[index]! & 0x80000000) | (next[(index + 1) % 624]! & 0x7fffffff);
    next[index] = u32(next[(index + 397) % 624]! ^ (mixed >>> 1) ^ ((mixed & 1) === 0 ? 0 : 0x9908b0df));
} return Object.freeze(next); };
export const nativePythonMt19937InitialState = (seed: bigint): NativePythonMt19937State => { const state: number[] = [19650218]; for (let index = 1; index < 624; index += 1)
    state[index] = u32(Math.imul(1812433253, state[index - 1]! ^ (state[index - 1]! >>> 30)) + index); const key = words(seed); let index = 1, keyIndex = 0; for (let count = Math.max(624, key.length); count > 0; count -= 1) {
    state[index] = u32((state[index]! ^ Math.imul(state[index - 1]! ^ (state[index - 1]! >>> 30), 1664525)) + key[keyIndex]! + keyIndex);
    index += 1;
    keyIndex += 1;
    if (index >= 624) {
        state[0] = state[623]!;
        index = 1;
    }
    if (keyIndex >= key.length)
        keyIndex = 0;
} for (let count = 623; count > 0; count -= 1) {
    state[index] = u32((state[index]! ^ Math.imul(state[index - 1]! ^ (state[index - 1]! >>> 30), 1566083941)) - index);
    index += 1;
    if (index >= 624) {
        state[0] = state[623]!;
        index = 1;
    }
} state[0] = 0x80000000; return Object.freeze({ index: 624, state: Object.freeze(state) }); };
const temper = (value: number): number => { const a = u32(value ^ (value >>> 11)), b = u32(a ^ ((a << 7) & 0x9d2c5680)), c = u32(b ^ ((b << 15) & 0xefc60000)); return u32(c ^ (c >>> 18)); };
export const nativePythonMt19937Next = (random: NativePythonMt19937State): readonly [
    number,
    NativePythonMt19937State
] => { const source = random.index === 624 ? Object.freeze({ index: 0, state: twist(random.state) }) : random; return Object.freeze([temper(source.state[source.index]!), Object.freeze({ index: source.index + 1, state: source.state })]); };
export const nativePythonRandrange = (random: NativePythonMt19937State, upperExclusive: number): readonly [
    number,
    NativePythonMt19937State
] => { const bits = Math.floor(Math.log2(upperExclusive)) + 1; let current = random; for (;;) {
    const [word, next] = nativePythonMt19937Next(current);
    const value = word >>> (32 - bits);
    if (value < upperExclusive)
        return Object.freeze([value, next]);
    current = next;
} };
