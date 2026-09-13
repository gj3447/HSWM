/**
 * Source-bound Float64 reduction for the NumPy 2.5.2 x86 baseline einsum
 * contiguous/contiguous/output-stride-zero kernel. Two lanes, separate
 * multiplication and addition, reverse nesting within each eight-value block.
 * This fixes the selected S2S reference backend; it is not a universal BLAS port.
 * Official source commit: 48fecee5453aa1d31e6b79dcb3969dc1a6d1a891
 * numpy/_core/src/multiarray/einsum_sumprod.c.src
 * SHA-256: d1c8e05b55eb31561169558bda7ddfd05e7ab4d7fac27a4123f33a3a494a220b
 * See assets/licenses/NUMPY_NUMERICAL_REFERENCE_NOTICE.txt.
 */
export const sumNativeS2SContiguousProducts = (size: 16 | 18, product: (index: number) => number): number => {
    let even = 0, odd = 0;
    for (let start = 0; start < 16; start += 8) {
        even = product(start) + (product(start + 2) + (product(start + 4) + (product(start + 6) + even)));
        odd = product(start + 1) + (product(start + 3) + (product(start + 5) + (product(start + 7) + odd)));
    }
    if (size === 18) {
        even += product(16);
        odd += product(17);
    }
    return even + odd;
};
