/**
 * Umbrella for the two Node adapters of the HSWM Effect runtime.
 *
 * `effect-posix-filesystem.ts` carries the PosixFileSystem service and
 * `effect-bounded-subprocess.ts` the BoundedSubprocess service.  Files that
 * live inside the DNRD-5 static source closure must import the filesystem
 * module directly; only executables' composition roots need this umbrella.
 */
export * from "./effect-posix-filesystem.js"
export * from "./effect-bounded-subprocess.js"

import { Layer } from "effect"

import { NodeBoundedSubprocessLive, type BoundedSubprocess } from "./effect-bounded-subprocess.js"
import { NodePosixFileSystemLive, type PosixFileSystem } from "./effect-posix-filesystem.js"

/** Both Node adapters; the only layer an executable's composition root needs for POSIX effects. */
export const NodePosixServicesLive: Layer.Layer<PosixFileSystem | BoundedSubprocess> =
  Layer.merge(NodePosixFileSystemLive, NodeBoundedSubprocessLive)
