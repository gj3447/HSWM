/** Pure source-bound USL v2 validation. No locator is resolved or executed here. */
import { createHash } from "node:crypto"
import { isIP } from "node:net"
import { Data, Either } from "effect"
import { validateNativeUslPlan } from "./native-usl-v1-domain.js"
import { nativePythonInstantSeconds } from "./native-python-instant-domain.js"
import { isTaskNumber, renderNativeTaskJson, taskJsonRecord, taskNumberValue, type TaskJson } from "./native-task-json-domain.js"
export class NativeUslV2WireError extends Data.TaggedError("NativeUslV2WireError")<{ readonly detail: string }> {}
type JsonObject = Readonly<Record<string, TaskJson>>
const fail = <A = never>(detail: string): Either.Either<A, NativeUslV2WireError> => Either.left(new NativeUslV2WireError({ detail }))
const object = (v: TaskJson | undefined): v is JsonObject => v !== undefined && taskJsonRecord(v)
const text = (v: TaskJson | undefined): v is string => typeof v === "string" && v.length > 0 && [...v].length <= 4096
const name = (v: TaskJson | undefined): v is string => text(v) && /^[A-Za-z_][A-Za-z0-9_]*$/u.test(v)
const exact = (v: TaskJson | undefined, keys: readonly string[]): v is JsonObject => object(v) && Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v,k))
const equal = (a: TaskJson, b: TaskJson): boolean => renderNativeTaskJson(a) === renderNativeTaskJson(b)
const safe = Number.MAX_SAFE_INTEGER
const wire = (value: TaskJson, depth=0): boolean => {
  if (depth >= 24) return false
  if (value === null || typeof value === "boolean") return true
  if (typeof value === "string") return !/[\uD800-\uDFFF]/u.test(value)
  if (isTaskNumber(value)) return typeof value === "number" && Number.isSafeInteger(value)
  if (Array.isArray(value)) return value.every(v => wire(v,depth+1))
  return Object.entries(value).every(([k,v]) => !/[\uD800-\uDFFF]/u.test(k) && !/^\p{Decimal_Number}+$/u.test(k) && wire(v,depth+1))
}
export const nativeUslV2Digest = (value: TaskJson): Either.Either<string,NativeUslV2WireError> => wire(value)
  ? Either.right(`sha256:${createHash("sha256").update(JSON.stringify(value),"utf8").digest("hex")}`) : fail("USL v2 unsupported wire JSON")
const hswmDigest = (v: TaskJson): string => createHash("sha256").update(renderNativeTaskJson(v),"utf8").digest("hex")
const locator = (value: TaskJson | undefined): Either.Either<string,NativeUslV2WireError> => {
  if (!text(value) || value !== value.trim() || /\s/u.test(value)) return fail("USL v2 locator whitespace")
  if (/^https?:\/\//iu.test(value)) {
    if (!/^[\x00-\x7f]*$/u.test(value) || /[\\<>"`{}\x00-\x20\x7f]/u.test(value)) return fail("USL v2 unsupported URL spelling")
    try {
      const parsed = new URL(value), authority = value.slice(value.indexOf("://")+3).split(/[/?#]/u)[0]!, rawHost=authority.startsWith("[") ? authority.slice(0,authority.indexOf("]")+1) : authority.split(":")[0]!.toLowerCase()
      if (parsed.username || parsed.password || !parsed.hostname || authority.includes("@")) return fail("USL v2 unsupported URL authority")
      if (rawHost.startsWith("[")) { if (isIP(rawHost.slice(1,-1)) !== 6) return fail("USL v2 IPv6") }
      else if (!/^[a-z0-9.-]+$/u.test(rawHost) || /^(?:[0-9]+|0x[0-9a-f]+)$/u.test(rawHost.replace(/\.$/u,"").split(".").at(-1)!) && isIP(rawHost)!==4) return fail("USL v2 unsupported URL host")
      const rawPath = value.slice(value.indexOf("://")+3+authority.length).split(/[?#]/u)[0]!
      if (rawPath.split("/").some(p=>[".","..","%2e",".%2e","%2e.","%2e%2e"].includes(p.toLowerCase())) || value.split("#")[0]!.split("?").slice(1).join("?").includes("'")) return fail("USL v2 normalize URL upstream")
      return Either.right(parsed.href)
    } catch { return fail("USL v2 unsupported URL spelling") }
  }
  if (!(/^kg:\/\/[A-Za-z0-9._-]+\/\S+$/u.test(value) || /^file:\/\/[A-Za-z0-9._-]+\/(?!\/)[^#\s]*(?:#L\d+-L\d+)?$/u.test(value) || /^git:\/\/[^@\s:]+(?:@[0-9a-fA-F]{7,64})?(?::[^:\s@]+(?:::[^@\s]+)?(?:@L\d+-L\d+)?)?$/u.test(value))) return fail("USL v2 locator scheme")
  const lines=/(?:#|@)L(\d+)-L(\d+)$/u.exec(value)
  if (lines!==null && (value.startsWith("file://")||value.startsWith("git://")) && !(Number(lines[1])>=1 && Number(lines[1])<=Number(lines[2]) && Number(lines[2])<=safe)) return fail("USL v2 locator text line range")
  return Either.right(value)
}
const formatted = (v: TaskJson | undefined): Either.Either<string,NativeUslV2WireError> => {
  if (!object(v)) return fail("USL v2 locator object")
  if ((Object.hasOwn(v,"lineStart")||Object.hasOwn(v,"lineEnd")) && !(typeof v["lineStart"]==="number" && typeof v["lineEnd"]==="number" && v["lineStart"]>=1 && v["lineStart"]<=v["lineEnd"] && v["lineEnd"]<=safe)) return fail("USL v2 locator line range")
  let value:string
  if(v["kind"]==="url" && text(v["href"])) value=v["href"]
  else if(v["kind"]==="kg") value=`kg://${String(v["source"])}/${String(v["uid"])}`
  else if(v["kind"]==="filesystem") value=`file://${String(v["host"])}${String(v["path"])}${v["lineStart"]===undefined?"":`#L${String(v["lineStart"])}-L${String(v["lineEnd"])}`}`
  else if(v["kind"]==="git_repo") {
    if (["path","symbol","lineStart","lineEnd"].some(k=>Object.hasOwn(v,k)) && !(text(v["commit"])&&text(v["path"]))) return fail("USL v2 Git locator fields")
    if(text(v["path"]) && (v["path"].startsWith("/")||v["path"].split("/").some(p=>["",".",".."].includes(p)))) return fail("USL v2 Git relative path")
    value=`git://${String(v["repo"])}${v["commit"]===undefined?"":`@${String(v["commit"])}`}${v["path"]===undefined?"":`:${String(v["path"])}`}${v["symbol"]===undefined?"":`::${String(v["symbol"])}`}${v["lineStart"]===undefined?"":`@L${String(v["lineStart"])}-L${String(v["lineEnd"])}`}`
  } else return fail("USL v2 locator kind")
  const checked=locator(value); return Either.isLeft(checked)?checked:Either.right(value)
}
const named = (v: TaskJson | undefined,label:string): Either.Either<ReadonlyMap<string,JsonObject>,NativeUslV2WireError> => {
  if(!Array.isArray(v)||v.length>64) return fail(label)
  const rows=new Map<string,JsonObject>()
  for(const r of v){if(!object(r)||!name(r["name"])||rows.has(r["name"]))return fail(label);rows.set(r["name"],r)}
  return Either.right(rows)
}
const contractValid = (meaning: JsonObject): boolean => {
  if(!text(meaning["description"])||!meaning["description"].trim())return false
  if(!Object.hasOwn(meaning,"contract"))return true
  const c=meaning["contract"],roles=meaning["roles"]
  if(!exact(c,["scope","checks"])||!text(c["scope"])||!c["scope"].trim()||!Array.isArray(c["checks"])||c["checks"].length===0||c["checks"].length>16||!Array.isArray(roles))return false
  const names=new Set<string>()
  for(const check of c["checks"]){if(!exact(check,["name","description","evidenceRoles"])||!name(check["name"])||names.has(check["name"])||!text(check["description"])||!check["description"].trim()||!Array.isArray(check["evidenceRoles"])||check["evidenceRoles"].length===0||check["evidenceRoles"].length>16||new Set(check["evidenceRoles"]).size!==check["evidenceRoles"].length||check["evidenceRoles"].some(r=>typeof r!=="string"||!roles.some(role=>object(role)&&role["name"]===r)))return false;names.add(check["name"])}
  return true
}
const observations = (value: TaskJson | undefined,expected: ReadonlyMap<string,JsonObject>,grounding=false): Either.Either<ReadonlyMap<string,JsonObject>,NativeUslV2WireError> => {
  const result=named(value,"USL v2 observations");if(Either.isLeft(result))return result
  if(!equal([...result.right.keys()],[...expected.keys()]))return fail("USL v2 selected observations")
  for(const [n,row] of result.right){const loc=expected.get(n)![grounding?"grounded":"locator"],key=formatted(loc)
    if(Either.isLeft(key)||!object(loc)||!exact(row,["name","locator","fingerprintScope","status","resolution","issue"])||row["locator"]!==key.right||row["fingerprintScope"]!==(loc["kind"]==="kg"?"KG_METADATA":"RESOLVER_REPRESENTATION")||!text(row["status"])||!["RESOLVES","ORPHAN","AMBIGUOUS","DENIED"].includes(row["status"]))return fail("USL v2 observation binding")
    const resolution=row["resolution"]
    if(resolution!==null && (!exact(resolution,["locator","resolvedLocator","contentHash","resolvedAt","guaranteeLevel","matchCount"])||!equal(resolution["locator"]!,loc)||Either.isLeft(locator(resolution["resolvedLocator"]))||typeof resolution["contentHash"]!=="string"||!/^[0-9a-f]{64}$/u.test(resolution["contentHash"])||nativePythonInstantSeconds(resolution["resolvedAt"])===null||!["pure","sandboxed","trust_host"].includes(String(resolution["guaranteeLevel"]))||typeof resolution["matchCount"]!=="number"||!Number.isSafeInteger(resolution["matchCount"])||resolution["matchCount"]<0))return fail("USL v2 resolution shape")
    if(row["status"]==="RESOLVES"){if(!object(resolution)||resolution["matchCount"]!==1||row["issue"]!==null)return fail("USL v2 unique resolution")}
    else {const issue=row["issue"];if(!exact(issue,["reason","detail"])||!text(issue["detail"])||!text(issue["reason"])||!(row["status"]==="AMBIGUOUS"?["AMBIGUOUS","IO"]:[row["status"]]).includes(issue["reason"])||(resolution!==null&&!(row["status"]==="AMBIGUOUS"&&object(resolution)&&resolution["matchCount"]!==1&&issue["reason"]==="AMBIGUOUS")))return fail("USL v2 unresolved representation")}
  }return result
}
export const validateNativeUslV2Wire = (input: TaskJson): Either.Either<void,NativeUslV2WireError> => {
  if(!exact(input,["plan","report","policy"])||!object(input["plan"])||!object(input["report"])||!object(input["policy"]))return fail("USL v2 request shape")
  const {plan,report,policy}=input, tables=validateNativeUslPlan(plan,true)
  if(Either.isLeft(tables))return fail(tables.left.detail)
  if(!text(plan["namespace"])||plan["namespace"].trim()!==plan["namespace"])return fail("USL v2 namespace whitespace")
  if(!exact(policy,["schema_version","namespace","plan_digest","usl_plan_digest","source_digest","max_age_seconds","bindings","resources"])||policy["schema_version"]!=="hswm-usl-observation-policy/v2"||policy["namespace"]!==plan["namespace"]||policy["plan_digest"]!==hswmDigest(plan)||!isTaskNumber(policy["max_age_seconds"]!)||!Number.isFinite(Number(taskNumberValue(policy["max_age_seconds"]!)))||Number(taskNumberValue(policy["max_age_seconds"]!))<=0||Number(taskNumberValue(policy["max_age_seconds"]!))>86400||!Array.isArray(policy["bindings"])||policy["bindings"].length===0||policy["bindings"].length>64)return fail("USL v2 policy shape")
  const selected=new Set<string>(),mapped=new Set<string>()
  for(const b of policy["bindings"]){if(!exact(b,["link","role","field"])||!name(b["link"])||!name(b["role"])||!name(b["field"])||!tables.right.links.has(b["link"])||selected.has(b["link"])||mapped.has(JSON.stringify([b["role"],b["field"]])))return fail("USL v2 duplicate or invalid binding");selected.add(b["link"]);mapped.add(JSON.stringify([b["role"],b["field"]]))}
  const links=new Map([...tables.right.links].filter(([n])=>selected.has(n))),resourceNames=new Set<string>(),meaningNames=new Set<string>()
  for(const link of links.values()){meaningNames.add(String(link["meaning"]));for(const p of link["participants"] as readonly JsonObject[])resourceNames.add(String(p["resource"]))}
  const resources=new Map([...tables.right.resources].filter(([n])=>resourceNames.has(n))),meanings=new Map([...tables.right.meanings].filter(([n])=>meaningNames.has(n))),groundings=new Map([...meanings].filter(([,m])=>Object.hasOwn(m,"grounded")))
  for(const r of tables.right.resources.values())if(Either.isLeft(formatted(r["locator"])))return fail("USL v2 declared locator")
  for(const m of tables.right.meanings.values())if(!contractValid(m)||(Object.hasOwn(m,"grounded")&&Either.isLeft(formatted(m["grounded"]))))return fail("USL v2 meaning contract")
  if(!Array.isArray(policy["resources"])||policy["resources"].length>64)return fail("USL v2 pins")
  const pinNames=new Set<string>(),needed=new Set([...resources.keys(),...[...groundings.keys()].map(n=>`meaning:${n}`)])
  for(const p of policy["resources"]){if(!exact(p,["name","content_hash","resolved_locator"])||!text(p["name"])||pinNames.has(p["name"])||typeof p["content_hash"]!=="string"||!/^[0-9a-f]{64}$/u.test(p["content_hash"])||!text(p["resolved_locator"]))return fail("USL v2 pin shape");pinNames.add(p["name"])}
  if(pinNames.size!==needed.size||[...needed].some(n=>!pinNames.has(n)))return fail("USL v2 pin coverage")
  if(!exact(report,["schema","namespace","planDigest","meaningsDigest","sourceDigest","digestFormat","status","readScope","metrics","resources","groundings","meanings","links","semanticTruth","observationDigest"])||report["schema"]!=="usl-program-observation/v2"||report["namespace"]!==plan["namespace"]||report["semanticTruth"]!=="NOT_EVALUATED"||report["digestFormat"]!=="sha256:utf8:JSON.stringify/v1")return fail("USL v2 report shape")
  const pd=nativeUslV2Digest(plan),md=nativeUslV2Digest(plan["meanings"]!),rd=nativeUslV2Digest(Object.fromEntries(Object.entries(report).filter(([k])=>k!=="observationDigest")))
  if(Either.isLeft(pd)||Either.isLeft(md)||Either.isLeft(rd)||pd.right!==report["planDigest"]||pd.right!==policy["usl_plan_digest"]||md.right!==report["meaningsDigest"]||rd.right!==report["observationDigest"]||(report["sourceDigest"]!==null&&(typeof report["sourceDigest"]!=="string"||!/^sha256:[0-9a-f]{64}$/u.test(report["sourceDigest"])))||report["sourceDigest"]!==policy["source_digest"])return fail("USL v2 digest binding")
  const observed=observations(report["resources"],resources),grounded=observations(report["groundings"],groundings,true),reportedMeanings=named(report["meanings"],"USL v2 meanings"),reportedLinks=named(report["links"],"USL v2 links")
  if(Either.isLeft(observed))return fail(observed.left.detail);if(Either.isLeft(grounded))return fail(grounded.left.detail);if(Either.isLeft(reportedMeanings))return fail(reportedMeanings.left.detail);if(Either.isLeft(reportedLinks))return fail(reportedLinks.left.detail)
  if(!equal([...reportedMeanings.right.keys()],[...meanings.keys()])||!equal([...reportedLinks.right.keys()],[...links.keys()]))return fail("USL v2 selected declarations")
  for(const [n,row]of reportedMeanings.right){if(!exact(row,["name","digest","definition"]))return fail("USL v2 meaning shape");const a=nativeUslV2Digest(row["definition"]!),b=nativeUslV2Digest(meanings.get(n)!);if(Either.isLeft(a)||Either.isLeft(b)||a.right!==b.right||a.right!==row["digest"])return fail("USL v2 meaning definition")}
  for(const [n,row] of reportedLinks.right){const l=links.get(n)!,m=meanings.get(String(l["meaning"]))!,c=m["contract"],participants=l["participants"] as readonly JsonObject[],a=nativeUslV2Digest(m),b=nativeUslV2Digest({meaning:m["name"]!,description:m["description"]!,roles:m["roles"]!,contract:c??null})
    if(!exact(row,["name","meaning","participants","meaningDigest","contractDigest","resourcesResolve","semanticTruth","verification"])||row["meaning"]!==l["meaning"]||!equal(row["participants"]!,l["participants"]!)||row["semanticTruth"]!=="NOT_EVALUATED"||row["resourcesResolve"]!==participants.every(p=>observed.right.get(String(p["resource"]))?.["status"]==="RESOLVES")||Either.isLeft(a)||Either.isLeft(b)||row["meaningDigest"]!==a.right||row["contractDigest"]!==b.right)return fail("USL v2 link binding")
    const checks=object(c)?c["checks"] as readonly JsonObject[]:[],expected=checks.map(check=>{const evidence=(check["evidenceRoles"] as readonly string[]).map(role=>({role,resource:participants.find(p=>p["role"]===role)!["resource"]!}));return {...check,scope:object(c)?c["scope"]!:null,evidence,evidenceAvailable:evidence.every(e=>observed.right.get(String(e.resource))?.["status"]==="RESOLVES"),status:"NOT_EXECUTED"}})
    if(!equal(row["verification"]!,expected))return fail("USL v2 verification contract/status")
  }
  const rows=[...observed.right.values(),...grounded.right.values()],targets=[...new Set(rows.map(r=>String(r["locator"])))],scope=report["readScope"]
  if(report["status"]!==(rows.every(r=>r["status"]==="RESOLVES")?"RESOLVES":"UNRESOLVED")||!exact(scope,["links","allowedLocators","requestedLocators","resourceBudget"])||!equal(scope["links"]!,[...links.keys()])||!equal(scope["requestedLocators"]!,targets)||typeof scope["resourceBudget"]!=="number"||!Number.isSafeInteger(scope["resourceBudget"])||scope["resourceBudget"]<targets.length||!Array.isArray(scope["allowedLocators"])||scope["allowedLocators"].length>256)return fail("USL v2 read scope")
  const allowed:string[]=[]
  for(const raw of scope["allowedLocators"]){const key=locator(raw);if(Either.isLeft(key)||key.right!==raw)return fail("USL v2 normalized allowlist");allowed.push(key.right)}
  if(!equal(allowed,[...new Set(allowed)].sort()))return fail("USL v2 unique allowlist")
  const admitted=new Set<string>()
  for(const t of targets){const k=locator(t);if(Either.isLeft(k))return fail(k.left.detail);if(allowed.includes(k.right))admitted.add(t)}
  const aliases=new Map<string,string>()
  for(const r of rows){const loc=String(r["locator"]),hash=hswmDigest({status:r["status"]!,resolution:r["resolution"]!,issue:r["issue"]!});if(!admitted.has(loc)&&r["status"]!=="DENIED"||aliases.has(loc)&&aliases.get(loc)!==hash)return fail("USL v2 permission/alias conflict");aliases.set(loc,hash)}
  const metrics={declaredResources:tables.right.resources.size,selectedResources:observed.right.size,uniqueLocators:targets.length,resolverCalls:admitted.size,deniedLocators:new Set(rows.filter(r=>r["status"]==="DENIED").map(r=>r["locator"])).size}
  if(!equal(report["metrics"]!,metrics))return fail("USL v2 metrics consistency")
  return Either.right(undefined)
}

/** Project validated v2 reference observations without executing declared checks. */
export const adaptNativeUslV2 = (input: TaskJson): Either.Either<TaskJson, NativeUslV2WireError> => {
  if (!object(input) || !object(input["plan"]) || !object(input["report"]) || !object(input["policy"]) || !Array.isArray(input["allowed_reads"]) || !isTaskNumber(input["now"]!) || !Number.isFinite(Number(taskNumberValue(input["now"]!))) || !text(input["revision"])) return fail("USL v2 observation context")
  const checked = validateNativeUslV2Wire({ plan: input["plan"], report: input["report"], policy: input["policy"] })
  if (Either.isLeft(checked)) return fail(checked.left.detail)
  const plan = input["plan"], report = input["report"], policy = input["policy"]
  if (!isTaskNumber(policy["max_age_seconds"]!)) return fail("USL v2 policy age")
  const maxAge = Number(taskNumberValue(policy["max_age_seconds"]!))
  const allowed = new Set<string>()
  for (const entry of input["allowed_reads"]) { if (!Array.isArray(entry) || entry.length !== 2 || !text(entry[0]) || !text(entry[1])) return fail("USL v2 allowed reads"); allowed.add(JSON.stringify(entry)) }
  const bindings = policy["bindings"] as ReadonlyArray<JsonObject>
  const selected = new Map<string, JsonObject>()
  for (const binding of bindings) { if (!exact(binding, ["link", "role", "field"]) || !text(binding["link"]) || !text(binding["role"]) || !text(binding["field"]) || selected.has(binding["link"]) || !allowed.has(JSON.stringify([binding["role"],binding["field"]]))) return fail("USL v2 binding"); selected.set(binding["link"], binding) }
  const resources = named(report["resources"], "USL v2 resources"), groundings = named(report["groundings"], "USL v2 groundings"), pins = new Map((policy["resources"] as readonly JsonObject[]).map(p=>[String(p["name"]),p])), meanings = named(plan["meanings"], "USL v2 meanings"), reportLinks = named(report["links"], "USL v2 links")
  if (Either.isLeft(resources)) return fail(resources.left.detail)
  if (Either.isLeft(groundings)) return fail(groundings.left.detail)
  if (Either.isLeft(meanings)) return fail(meanings.left.detail)
  if (Either.isLeft(reportLinks)) return fail(reportLinks.left.detail)
  const reportDigest = hswmDigest(report), policyDigest = hswmDigest(policy)
  const source = hswmDigest({ plan_digest: hswmDigest(plan), report_digest: reportDigest, policy_digest: policyDigest })
  const links: TaskJson[] = [], observations: TaskJson[] = []
  for (const linkValue of plan["links"] as ReadonlyArray<TaskJson>) {
    if (!object(linkValue) || !text(linkValue["name"]) || !selected.has(linkValue["name"])) continue
    const binding = selected.get(linkValue["name"])!, reasons: string[] = []; let expires = Infinity
    if (!Array.isArray(linkValue["participants"])) return fail("USL v2 participant shape")
    for (const participant of linkValue["participants"]) {
      if (!object(participant) || !text(participant["resource"])) return fail("USL v2 participant shape")
      const name = participant["resource"], row = resources.right.get(name), pin = pins.get(name)
      if (row && pin && object(row["resolution"]) && (row["resolution"]["contentHash"] !== pin["content_hash"] || row["resolution"]["resolvedLocator"] !== pin["resolved_locator"])) return fail(`resource pin mismatch: ${name}`)
      if (!row || !pin || row["status"] !== "RESOLVES" || !object(row["resolution"])) { reasons.push(`RESOURCE:${name}_${row?.["status"] ?? "ORPHAN"}`); continue }
      const resolution = row["resolution"]
      if (resolution["contentHash"] !== pin["content_hash"] || resolution["resolvedLocator"] !== pin["resolved_locator"]) return fail(`resource pin mismatch: ${name}`)
      const at = nativePythonInstantSeconds(resolution["resolvedAt"])!, expiry = at + maxAge, now = Number(taskNumberValue(input["now"]!))
      if (!Number.isFinite(at) || at > now) reasons.push(`RESOURCE:${name}_FUTURE_TIMESTAMP`); else if (now >= expiry) reasons.push(`RESOURCE:${name}_STALE`); else expires = Math.min(expires, expiry)
    }
    const meaning = meanings.right.get(String(linkValue["meaning"]))
    if (meaning?.["grounded"] !== undefined) {
      const name = meaning["name"]
      if (!text(name)) return fail("USL v2 meaning shape")
      const row = groundings.right.get(name), pin = pins.get(`meaning:${name}`)
      if (row && pin && object(row["resolution"]) && (row["resolution"]["contentHash"] !== pin["content_hash"] || row["resolution"]["resolvedLocator"] !== pin["resolved_locator"])) return fail(`grounding pin mismatch: ${name}`)
      if (!row || !pin || row["status"] !== "RESOLVES" || !object(row["resolution"])) reasons.push(`GROUNDING:${name}_${row?.["status"] ?? "ORPHAN"}`)
      else {
        const resolution = row["resolution"]
        if (resolution["contentHash"] !== pin["content_hash"] || resolution["resolvedLocator"] !== pin["resolved_locator"]) return fail(`grounding pin mismatch: ${name}`)
        const at = nativePythonInstantSeconds(resolution["resolvedAt"])!, expiry = at + maxAge, now = Number(taskNumberValue(input["now"]!))
        if (!Number.isFinite(at) || at > now) reasons.push(`GROUNDING:${name}_FUTURE_TIMESTAMP`); else if (now >= expiry) reasons.push(`GROUNDING:${name}_STALE`); else expires = Math.min(expires, expiry)
      }
    }
    const ready = reasons.length === 0
    const reportLink = reportLinks.right.get(linkValue["name"])
    links.push({ name: linkValue["name"], meaning: linkValue["meaning"]!, participants: linkValue["participants"]!, status: ready ? "READY" : "UNKNOWN", reasons, ...(reportLink === undefined ? {} : { meaningDigest: reportLink["meaningDigest"]!, contractDigest: reportLink["contractDigest"]!, verification: reportLink["verification"]! }) })
    if (ready) observations.push({ role: binding["role"]!, field: binding["field"]!, value: true, revision: input["revision"], expires_at: expires, source })
  }
  return Either.right({ schema_version: "hswm-usl-observation-projection/v2", status: observations.length === selected.size ? "READY" : "UNRESOLVED", plan_digest: policy["plan_digest"]!, report_digest: reportDigest, policy_digest: policyDigest, namespace: plan["namespace"]!, observations, links, mapping_loss: ["reference resolution only", "no semantic truth", "caller-bound report not attestation", "no content extraction/credit/admission", "declared checks preserved but not executed", "source digest caller-pinned, source not recompiled", "KG_METADATA is not full graph semantics", "noncanonical HTTP URL forms outside the supported subset reject"], meanings: report["meanings"]!, usl: { report_schema: report["schema"]!, plan_digest: report["planDigest"]!, meanings_digest: report["meaningsDigest"]!, source_digest: report["sourceDigest"]!, observation_digest: report["observationDigest"]!, digest_format: report["digestFormat"]!, source_binding: report["sourceDigest"] === null ? "ABSENT" : "CALLER_PINNED_NOT_RECOMPILED" }, read_scope: report["readScope"]!, metrics: report["metrics"]! })
}
