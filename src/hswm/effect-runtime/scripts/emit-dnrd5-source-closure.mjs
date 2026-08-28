#!/usr/bin/env node
/**
 * Emit a reproducible, local-only description of the TypeScript build inputs
 * and outputs used by the DNRD-5 Source-A qualification instrument.
 *
 * This program neither performs a Source-A decision nor dispatches a provider
 * request.  It deliberately has no network or provider dependencies.
 */
import { createHash } from "node:crypto"
import { existsSync, lstatSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync } from "node:fs"
import { basename, dirname, isAbsolute, relative, resolve, sep } from "node:path"
import { fileURLToPath } from "node:url"
import ts from "typescript"

const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const TS_CONFIG = resolve(PACKAGE_ROOT, "tsconfig.dnrd5-source-closure.json")
const SOURCE_ROOT = resolve(PACKAGE_ROOT, "src")
const TYPESCRIPT_ROOT = resolve(PACKAGE_ROOT, "node_modules", "typescript")
const PACKAGE_REAL_ROOT = realpathSync(PACKAGE_ROOT)
const SHA256 = (bytes) => createHash("sha256").update(bytes).digest("hex")
const compareText = (left, right) => left < right ? -1 : left > right ? 1 : 0
const FORBIDDEN_LOADER_IDENTIFIERS = new Set([
  "AsyncFunction",
  "Function",
  "WebAssembly",
  "createRequire",
  "eval",
  "global",
  "globalThis",
  "getBuiltinModule",
  "require",
  "self",
  "window"
])
const FORBIDDEN_RUNTIME_MODULES = new Set([
  "node:child_process",
  "node:module",
  "node:vm",
  "node:vm/promises",
  "node:worker_threads"
])
const FORBIDDEN_PROPERTY_NAMES = new Set(["__proto__", "constructor", "prototype"])
const SAFE_INTRINSIC_PROTOTYPE_BASES = new Set([
  "Array",
  "Object",
  "SharedArrayBuffer",
  "Uint8Array"
])

class ClosureFailure extends Error {
  constructor(code, message) {
    super(message)
    this.code = code
  }
}

const fail = (code, message) => {
  throw new ClosureFailure(code, message)
}

const canonical = (value) => {
  if (value === null || typeof value !== "object") return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`
  return `{${Object.keys(value).sort(compareText).map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`
}

const packagePath = (path) => {
  const answer = relative(PACKAGE_ROOT, path).split(sep).join("/")
  if (!answer || answer === ".." || answer.startsWith("../")) {
    fail("PATH_OUTSIDE_PACKAGE_ROOT", `closure path escaped the package root: ${basename(path)}`)
  }
  return answer
}

const descriptor = (path, stablePath) => {
  const label = stablePath ?? packagePath(path)
  if (!existsSync(path)) fail("INPUT_MISSING", `required local input is missing: ${label}`)
  const stats = lstatSync(path)
  if (!stats.isFile() || stats.isSymbolicLink()) fail("INPUT_NOT_REGULAR_FILE", `required local input is not a regular file: ${label}`)
  if (stablePath === undefined) {
    const resolvedPath = realpathSync(path)
    const fromPackage = relative(PACKAGE_REAL_ROOT, resolvedPath)
    if (!fromPackage || fromPackage === ".." || fromPackage.startsWith(`..${sep}`) || isAbsolute(fromPackage)) {
      fail("INPUT_REALPATH_OUTSIDE_PACKAGE_ROOT", `required local input escaped through a parent symlink: ${label}`)
    }
  }
  const bytes = readFileSync(path)
  return { byteLength: bytes.length, path: label, sha256: SHA256(bytes) }
}

const emittedDescriptors = (root) => {
  const answer = []
  const visit = (directory) => {
    for (const entry of readdirSync(directory, { withFileTypes: true }).sort((a, b) => compareText(a.name, b.name))) {
      const path = resolve(directory, entry.name)
      if (entry.isDirectory()) visit(path)
      else if (entry.isFile() && !entry.isSymbolicLink()) {
        const bytes = readFileSync(path)
        answer.push({ byteLength: bytes.length, path: relative(root, path).split(sep).join("/"), sha256: SHA256(bytes) })
      } else fail("EMIT_NONREGULAR_ENTRY", "TypeScript emitted a non-regular filesystem entry")
    }
  }
  visit(root)
  return answer
}

const importSpecifier = (node) => {
  if (!ts.isStringLiteralLike(node)) return undefined
  return node.text
}

const importNames = (node) => {
  if (ts.isImportDeclaration(node)) {
    const clause = node.importClause
    if (!clause) return []
    const names = []
    if (clause.name) names.push({ imported: "default", local: clause.name.text, typeOnly: clause.isTypeOnly })
    if (clause.namedBindings && ts.isNamespaceImport(clause.namedBindings)) {
      names.push({ imported: "*", local: clause.namedBindings.name.text, typeOnly: clause.isTypeOnly })
    } else if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
      for (const element of clause.namedBindings.elements) {
        names.push({
          imported: element.propertyName?.text ?? element.name.text,
          local: element.name.text,
          typeOnly: clause.isTypeOnly || element.isTypeOnly
        })
      }
    }
    return names.sort((left, right) => compareText(`${left.imported}\0${left.local}`, `${right.imported}\0${right.local}`))
  }
  if (ts.isExportDeclaration(node) && node.exportClause && ts.isNamedExports(node.exportClause)) {
    return node.exportClause.elements.map((element) => ({
      imported: element.propertyName?.text ?? element.name.text,
      local: element.name.text,
      typeOnly: node.isTypeOnly || element.isTypeOnly
    })).sort((left, right) => compareText(`${left.imported}\0${left.local}`, `${right.imported}\0${right.local}`))
  }
  if (ts.isImportEqualsDeclaration(node)) {
    return [{ imported: "export=", local: node.name.text, typeOnly: node.isTypeOnly }]
  }
  return []
}

const allowedLocalPropertyBase = (node) =>
  node.kind === ts.SyntaxKind.ThisKeyword ||
  (ts.isIdentifier(node) && !FORBIDDEN_LOADER_IDENTIFIERS.has(node.text)) ||
  (ts.isPropertyAccessExpression(node) && allowedLocalPropertyBase(node.expression))

const allowedComputedPropertyKey = (node) => {
  if (ts.isStringLiteralLike(node)) {
    return !FORBIDDEN_LOADER_IDENTIFIERS.has(node.text) && !FORBIDDEN_PROPERTY_NAMES.has(node.text)
  }
  if (ts.isNumericLiteral(node) || ts.isIdentifier(node)) return true
  if (ts.isPropertyAccessExpression(node)) {
    return allowedLocalPropertyBase(node.expression)
  }
  if (ts.isElementAccessExpression(node)) {
    return allowedComputedPropertyKey(node.argumentExpression) &&
      allowedLocalPropertyBase(node.expression)
  }
  if (ts.isBinaryExpression(node)) {
    return new Set([
      ts.SyntaxKind.MinusToken,
      ts.SyntaxKind.AsteriskToken,
      ts.SyntaxKind.SlashToken,
      ts.SyntaxKind.PercentToken,
      ts.SyntaxKind.AsteriskAsteriskToken,
      ts.SyntaxKind.LessThanLessThanToken,
      ts.SyntaxKind.GreaterThanGreaterThanToken,
      ts.SyntaxKind.GreaterThanGreaterThanGreaterThanToken,
      ts.SyntaxKind.AmpersandToken,
      ts.SyntaxKind.BarToken,
      ts.SyntaxKind.CaretToken
    ]).has(node.operatorToken.kind) &&
      allowedComputedPropertyKey(node.left) &&
      allowedComputedPropertyKey(node.right)
  }
  return ts.isCallExpression(node) &&
    ts.isIdentifier(node.expression) &&
    node.expression.text === "String" &&
    node.arguments.length === 1 &&
    allowedComputedPropertyKey(node.arguments[0])
}

/**
 * The selected source closure permits only ordinary array/record indexing:
 * literal keys, local index identifiers, direct local/this properties, and
 * a one-argument `String()` wrapper around one of those values. Computed
 * expressions are rejected because they can hide runtime-loader property
 * names (for example `"ev" + "al"`).
 */
export const assertStaticClosureSyntax = (sourceFile) => {
  const visit = (node) => {
    if (ts.isIdentifier(node) && FORBIDDEN_LOADER_IDENTIFIERS.has(node.text)) {
      fail("RUNTIME_LOADER_FORBIDDEN", `${node.text} is outside the static DNRD-5 import closure in ${packagePath(sourceFile.fileName)}`)
    }
    if (ts.isElementAccessExpression(node)) {
      const key = importSpecifier(node.argumentExpression)
      if (key !== undefined && (FORBIDDEN_LOADER_IDENTIFIERS.has(key) || FORBIDDEN_PROPERTY_NAMES.has(key))) {
        fail("RUNTIME_LOADER_FORBIDDEN", `an indirect runtime loader is outside the static DNRD-5 import closure in ${packagePath(sourceFile.fileName)}`)
      }
      if (!allowedComputedPropertyKey(node.argumentExpression)) {
        fail("RUNTIME_LOADER_FORBIDDEN", `computed property access is outside the static DNRD-5 import closure in ${packagePath(sourceFile.fileName)}`)
      }
    }
    if (ts.isPropertyAccessExpression(node) && FORBIDDEN_PROPERTY_NAMES.has(node.name.text)) {
      const intrinsicPrototype = node.name.text === "prototype" &&
        ts.isIdentifier(node.expression) &&
        SAFE_INTRINSIC_PROTOTYPE_BASES.has(node.expression.text)
      if (!intrinsicPrototype) {
        fail("RUNTIME_LOADER_FORBIDDEN", `dangerous property access is outside the static DNRD-5 import closure in ${packagePath(sourceFile.fileName)}`)
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
}

const importBindings = (sourceFile, program) => {
  const bindings = []
  if (typeof program.getResolvedModuleFromModuleSpecifier !== "function") {
    fail("PROGRAM_RESOLUTION_API_MISSING", "the pinned TypeScript Program lacks its resolved-module lookup")
  }
  assertStaticClosureSyntax(sourceFile)
  const add = (node, moduleSpecifier, kind, specifier, typeOnly) => {
    if (!typeOnly && FORBIDDEN_RUNTIME_MODULES.has(specifier)) {
      fail("RUNTIME_LOADER_FORBIDDEN", `${specifier} is outside the static DNRD-5 import closure in ${packagePath(sourceFile.fileName)}`)
    }
    const resolved = program.getResolvedModuleFromModuleSpecifier(moduleSpecifier, sourceFile)?.resolvedModule
    const target = resolved?.resolvedFileName
    const targetKind = specifier.startsWith("node:")
      ? "node-builtin"
      : target?.startsWith(`${SOURCE_ROOT}${sep}`)
        ? "local-source"
        : target?.includes(`${sep}node_modules${sep}`)
          ? "locked-package"
          : "unclassified"
    if (!target && targetKind !== "node-builtin") {
      fail("MODULE_RESOLUTION_FAILED", `TypeScript did not resolve ${specifier} from ${packagePath(sourceFile.fileName)}`)
    }
    if (targetKind === "unclassified") {
      fail("MODULE_RESOLUTION_OUTSIDE_CLOSURE", `TypeScript resolved ${specifier} outside the selected source or locked package roots`)
    }
    bindings.push({
      kind,
      names: importNames(node),
      position: node.getStart(sourceFile),
      source: specifier,
      target: target && existsSync(target) ? descriptor(target) : null,
      targetKind,
      typeOnly
    })
  }
  const visit = (node) => {
    if (ts.isImportDeclaration(node) && node.moduleSpecifier) {
      const specifier = importSpecifier(node.moduleSpecifier)
      if (specifier !== undefined) add(node, node.moduleSpecifier, "static-import", specifier, node.importClause?.isTypeOnly === true)
    } else if (ts.isExportDeclaration(node) && node.moduleSpecifier) {
      const specifier = importSpecifier(node.moduleSpecifier)
      if (specifier !== undefined) add(node, node.moduleSpecifier, "static-export", specifier, node.isTypeOnly === true)
    } else if (ts.isImportTypeNode(node)) {
      const argument = node.argument
      const specifier = ts.isLiteralTypeNode(argument) ? importSpecifier(argument.literal) : undefined
      if (specifier !== undefined) add(node, argument.literal, "type-import", specifier, true)
    } else if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference)) {
      const expression = node.moduleReference.expression
      const specifier = expression ? importSpecifier(expression) : undefined
      if (specifier === undefined) fail("IMPORT_EQUALS_NONLITERAL", `import-equals must use one string literal in ${packagePath(sourceFile.fileName)}`)
      add(node, expression, "import-equals", specifier, node.isTypeOnly)
    } else if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
      const specifier = node.arguments.length === 1 ? importSpecifier(node.arguments[0]) : undefined
      if (specifier === undefined) fail("DYNAMIC_IMPORT_NONLITERAL", `runtime dynamic import must use one string literal in ${packagePath(sourceFile.fileName)}`)
      add(node, node.arguments[0], "runtime-dynamic-import", specifier, false)
    } else if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === "require") {
      const specifier = node.arguments.length === 1 ? importSpecifier(node.arguments[0]) : undefined
      if (specifier === undefined) fail("REQUIRE_NONLITERAL", `require must use one string literal in ${packagePath(sourceFile.fileName)}`)
      add(node, node.arguments[0], "runtime-require", specifier, false)
    } else if (
      ts.isCallExpression(node) &&
      ((ts.isPropertyAccessExpression(node.expression) && node.expression.name.text === "require") ||
        (ts.isElementAccessExpression(node.expression) && importSpecifier(node.expression.argumentExpression) === "require") ||
        (ts.isIdentifier(node.expression) && node.expression.text === "createRequire") ||
        (ts.isCallExpression(node.expression) && ts.isIdentifier(node.expression.expression) && node.expression.expression.text === "createRequire"))
    ) {
      fail("RUNTIME_LOADER_FORBIDDEN", `an indirect runtime loader is outside the static DNRD-5 import closure in ${packagePath(sourceFile.fileName)}`)
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return bindings.sort((left, right) => left.position - right.position || compareText(left.kind, right.kind))
}

const exportedSymbols = (checker, sourceFile) => {
  const symbol = checker.getSymbolAtLocation(sourceFile)
  if (!symbol) return []
  return checker.getExportsOfModule(symbol).map((item) => item.getName()).sort(compareText)
}

const effectiveCompilerOptions = (options) => ({
  allowImportingTsExtensions: options.allowImportingTsExtensions ?? false,
  declaration: options.declaration ?? false,
  declarationMap: options.declarationMap ?? false,
  exactOptionalPropertyTypes: options.exactOptionalPropertyTypes ?? false,
  module: options.module ?? null,
  moduleResolution: options.moduleResolution ?? null,
  noEmit: options.noEmit ?? false,
  noEmitOnError: options.noEmitOnError ?? false,
  noUncheckedIndexedAccess: options.noUncheckedIndexedAccess ?? false,
  plugins: options.plugins ?? [],
  rootDir: options.rootDir ? packagePath(options.rootDir) : null,
  sourceMap: options.sourceMap ?? false,
  strict: options.strict ?? false,
  target: options.target ?? null,
  types: options.types ?? []
})

const diagnosticsOrThrow = (diagnostics) => {
  if (diagnostics.length === 0) return
  const first = diagnostics[0]
  const file = first.file ? packagePath(first.file.fileName) : "tsconfig.build.json"
  fail("TYPESCRIPT_DIAGNOSTIC", `${file}:${first.start ?? 0}: TS${first.code}: ${ts.flattenDiagnosticMessageText(first.messageText, " ")}`)
}

const main = () => {
  if (!existsSync(TS_CONFIG)) fail("TSCONFIG_MISSING", "tsconfig.dnrd5-source-closure.json is required")
  const parseErrors = []
  const parsed = ts.getParsedCommandLineOfConfigFile(TS_CONFIG, {}, {
    ...ts.sys,
    onUnRecoverableConfigFileDiagnostic: (diagnostic) => parseErrors.push(diagnostic)
  })
  if (!parsed) fail("TSCONFIG_PARSE_FAILED", "tsconfig.dnrd5-source-closure.json could not be parsed")
  diagnosticsOrThrow([...parseErrors, ...parsed.errors])
  const rootNames = parsed.fileNames.filter((path) => path.startsWith(`${SOURCE_ROOT}${sep}`) && path.endsWith(".ts")).sort(compareText)
  if (rootNames.length === 0) fail("SOURCE_SET_EMPTY", "the DNRD-5 source-closure config selected no TypeScript source files")
  // Keeping the output directory at one fixed depth beneath the package root
  // makes declaration/source-map relative paths independent of checkout path.
  const temporaryOutDir = mkdtempSync(resolve(PACKAGE_ROOT, ".dnrd5-source-closure-out-"))
  try {
    const compilerOptions = { ...parsed.options, outDir: temporaryOutDir, noEmit: false }
    const program = ts.createProgram({ rootNames, options: compilerOptions, projectReferences: parsed.projectReferences })
    diagnosticsOrThrow(ts.getPreEmitDiagnostics(program))
    diagnosticsOrThrow(program.emit().diagnostics)
    const emitted = emittedDescriptors(temporaryOutDir)
    if (emitted.length === 0) fail("EMIT_EMPTY", "TypeScript emitted no build files")
    const checker = program.getTypeChecker()
    const programSourceFiles = program.getSourceFiles().map((sourceFile) => sourceFile.fileName)
    const sourceFiles = programSourceFiles
      .filter((path) => path.startsWith(`${SOURCE_ROOT}${sep}`) && path.endsWith(".ts"))
      .sort(compareText)
    const resolvedExternalFiles = programSourceFiles
      .filter((path) => !path.startsWith(`${SOURCE_ROOT}${sep}`))
      .map((path) => descriptor(path))
      .sort((left, right) => compareText(left.path, right.path))
    const sources = sourceFiles.map((path) => {
      const sourceFile = program.getSourceFile(path)
      if (!sourceFile) fail("SOURCE_FILE_UNAVAILABLE", `compiler omitted configured source: ${packagePath(path)}`)
      return {
        ...descriptor(path),
        exportedSymbols: exportedSymbols(checker, sourceFile),
        imports: importBindings(sourceFile, program)
      }
    })
    const entrypoints = rootNames.map(packagePath)
    const result = {
      contractVersion: "hswm-dnrd5-local-source-build-import-closure/v1",
      claimBoundary: "LOCAL_REDERIVATION_ONLY_NO_NETWORK_AUTHORITY_SOURCE_FREEZE_PROVIDER_OCCURRENCE_OR_SCIENTIFIC_RESULT",
      dispatchAuthorized: false,
      dispatchBudget: 0,
      sourceFreezeEligible: false,
      compiler: {
        effectiveOptions: effectiveCompilerOptions(parsed.options),
        nodeExecutable: descriptor(process.execPath, "external-runtime/node"),
        nodeVersion: process.version,
        typescriptFiles: [
          descriptor(resolve(TYPESCRIPT_ROOT, "package.json")),
          descriptor(resolve(TYPESCRIPT_ROOT, "lib", "tsc.js")),
          descriptor(resolve(TYPESCRIPT_ROOT, "lib", "typescript.js"))
        ].sort((left, right) => compareText(left.path, right.path)),
        version: ts.version
      },
      entrypoints,
      inputs: [
        descriptor(resolve(PACKAGE_ROOT, "package.json")),
        descriptor(resolve(PACKAGE_ROOT, "package-lock.json")),
        descriptor(resolve(PACKAGE_ROOT, ".npmrc")),
        descriptor(resolve(PACKAGE_ROOT, "tsconfig.json")),
        descriptor(resolve(PACKAGE_ROOT, "tsconfig.build.json")),
        descriptor(TS_CONFIG)
      ].sort((left, right) => compareText(left.path, right.path)),
      emitted: { files: emitted, rootSha256: SHA256(Buffer.from(canonical(emitted))) },
      resolvedExternalFiles,
      sources,
      terminal: "LOCAL_SOURCE_BUILD_IMPORT_CLOSURE_ONLY_NOT_SOURCE_A_PROVIDER_OR_EFFICACY"
    }
    process.stdout.write(canonical(result))
  } finally {
    rmSync(temporaryOutDir, { recursive: true, force: true })
  }
}

const invokedAsMain = process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(import.meta.url)

if (invokedAsMain) {
  try {
    main()
  } catch (error) {
    const code = error instanceof ClosureFailure ? error.code : "UNEXPECTED_FAILURE"
    const message = error instanceof Error ? error.message : "unknown failure"
    process.stderr.write(`${canonical({ error: { code, message } })}\n`)
    process.exitCode = 1
  }
}
