#!/usr/bin/env node
/** AST boundary check for the new local adaptive runtime lane. */
import { readdirSync, readFileSync } from "node:fs"
import { join, resolve } from "node:path"
import ts from "typescript"

const argv = process.argv.slice(2)
const rootFlag = argv.indexOf("--root")
const root = resolve(rootFlag < 0 ? "src" : argv[rootFlag + 1] ?? "src")
const target = (name) => /^adaptive-.*\.ts$/.test(name) || ["hswm-dev-process.ts", "hswm-live-process.ts", "reluvator-check-process.ts"].includes(name)
const violations = []
const files = readdirSync(root).filter(target).sort()

for (const file of files) {
  const path = join(root, file)
  const source = ts.createSourceFile(path, readFileSync(path, "utf8"), ts.ScriptTarget.Latest, true)
  const report = (node, rule) => {
    const line = source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1
    violations.push({ file, line, rule })
  }
  const effectNames = new Set()
  const namespaceNames = new Set()
  const runNames = new Set()
  for (const statement of source.statements) {
    if (ts.isImportDeclaration(statement) && ["effect", "effect/Effect"].includes(statement.moduleSpecifier.text)) {
      const bindings = statement.importClause?.namedBindings
      if (bindings && ts.isNamespaceImport(bindings)) {
        (statement.moduleSpecifier.text === "effect/Effect" ? effectNames : namespaceNames).add(bindings.name.text)
      }
      if (bindings && ts.isNamedImports(bindings)) for (const specifier of bindings.elements) {
        const imported = specifier.propertyName?.text ?? specifier.name.text
        if (imported === "Effect") effectNames.add(specifier.name.text)
        if (/^run/.test(imported)) runNames.add(specifier.name.text)
      }
    }
    if (ts.isVariableStatement(statement) && !(statement.declarationList.flags & ts.NodeFlags.Const)) report(statement, "MODULE_MUTABLE")
  }
  const directDomain = file === "adaptive-domain.ts" || file === "adaptive-runtime.ts"
  const visit = (node) => {
    if (ts.isThrowStatement(node)) report(node, "THROW")
    if (ts.isFunctionLike(node) && node.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.AsyncKeyword)) report(node, "ASYNC")
    if (directDomain && ts.isImportDeclaration(node) && typeof node.moduleSpecifier.text === "string" && /^(node:)?(fs|http|https|child_process|sqlite)(\/|$)/.test(node.moduleSpecifier.text)) report(node, "DOMAIN_IO_IMPORT")
    if (ts.isCallExpression(node)) {
      if (ts.isIdentifier(node.expression) && runNames.has(node.expression.text)) report(node, "EFFECT_RUN")
      if (ts.isPropertyAccessExpression(node.expression) && ts.isIdentifier(node.expression.expression) && effectNames.has(node.expression.expression.text) && /^run/.test(node.expression.name.text)) report(node, "EFFECT_RUN")
      if (ts.isPropertyAccessExpression(node.expression) && ts.isPropertyAccessExpression(node.expression.expression) && ts.isIdentifier(node.expression.expression.expression) && namespaceNames.has(node.expression.expression.expression.text) && node.expression.expression.name.text === "Effect" && /^run/.test(node.expression.name.text)) report(node, "EFFECT_RUN")
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
}
process.stdout.write(`${JSON.stringify({ schema_version: "hswm-adaptive-functional-lint/v1", files, violations })}\n`)
if (violations.length > 0) process.exitCode = 1
