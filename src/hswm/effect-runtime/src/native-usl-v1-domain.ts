/** Pure v1 USL reachability projection. It never resolves or executes a locator. */
import { nativePythonInstantSeconds } from "./native-python-instant-domain.js"
import { createHash } from "node:crypto"
import { Data, Either } from "effect"
import { isTaskNumber, renderNativeTaskJson, taskJsonRecord, taskNumberValue, type TaskJson } from "./native-task-json-domain.js"

export class NativeUslV1Error extends Data.TaggedError("NativeUslV1Error")<{ readonly detail: string }> {}
type JsonObject = Readonly<Record<string, TaskJson>>
const fail = <A = never>(detail: string): Either.Either<A, NativeUslV1Error> => Either.left(new NativeUslV1Error({ detail }))
const object = (value: TaskJson | undefined): value is JsonObject => taskJsonRecord(value as TaskJson)
const text = (value: TaskJson | undefined): value is string => typeof value === "string" && value.length > 0 && value.length <= 4096
const exact = (value: TaskJson | undefined, keys: readonly string[]): value is JsonObject => object(value) && Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key))
const digest = (value: TaskJson): string => createHash("sha256").update(renderNativeTaskJson(value), "utf8").digest("hex")
const rows = (value: TaskJson | undefined, label: string, maximum = 64): Either.Either<ReadonlyArray<JsonObject>, NativeUslV1Error> => !Array.isArray(value) || value.length > maximum ? fail(label) : value.every(object) ? Either.right(value) : fail(label)
const named = (value: TaskJson | undefined, label: string): Either.Either<ReadonlyMap<string, JsonObject>, NativeUslV1Error> => {
  const parsed = rows(value, label)
  if (Either.isLeft(parsed)) return fail(parsed.left.detail)
  const found = new Map<string, JsonObject>()
  for (const row of parsed.right) {
    if (!text(row["name"]) || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(row["name"]) || found.has(row["name"])) return fail(`duplicate ${label}`)
    found.set(row["name"], row)
  }
  return Either.right(found)
}
const policyPins = (value: TaskJson | undefined): Either.Either<ReadonlyMap<string, JsonObject>, NativeUslV1Error> => {
  const parsed=rows(value,"policy resource");if(Either.isLeft(parsed))return fail(parsed.left.detail);const found=new Map<string,JsonObject>();for(const row of parsed.right){if(!text(row["name"])||found.has(row["name"]))return fail("duplicate policy resource");found.set(row["name"],row)}return Either.right(found)
}
const timestamp = (value: TaskJson | undefined): Either.Either<number, NativeUslV1Error> => {
  if (!text(value)) return fail("resolvedAt")
  const parsed = nativePythonInstantSeconds(value)
  return parsed !== null ? Either.right(parsed) : fail("resolvedAt")
}
const name = (value: TaskJson | undefined, label: string): Either.Either<string, NativeUslV1Error> => text(value) && /^[A-Za-z_][A-Za-z0-9_]*$/.test(value) ? Either.right(value) : fail(label)
const locator = (value: TaskJson | undefined): Either.Either<JsonObject, NativeUslV1Error> => {
  if (!object(value) || !text(value["kind"]) || !["kg", "url", "git_repo", "filesystem"].includes(value["kind"])) return fail("locator")
  const kind = value["kind"]
  const allowed: Readonly<Record<string, readonly string[]>> = { kg:["kind","source","uid"], url:["kind","href"], git_repo:["kind","repo","commit","path","symbol","lineStart","lineEnd"], filesystem:["kind","host","path","lineStart","lineEnd"] }
  const required: Readonly<Record<string, readonly string[]>> = { kg:["kind","source","uid"], url:["kind","href"], git_repo:["kind","repo"], filesystem:["kind","host","path"] }
  if (!Object.keys(value).every(key => allowed[kind]!.includes(key)) || !required[kind]!.every(key => Object.hasOwn(value,key))) return fail("locator fields")
  for (const [key, item] of Object.entries(value)) if (key === "lineStart" || key === "lineEnd") { if (typeof item !== "number" || !Number.isSafeInteger(item) || item < 1) return fail("locator line") } else if (key !== "kind" && !text(item)) return fail("locator text")
  return Either.right(value)
}
interface PlanTables { readonly resources: ReadonlyMap<string, JsonObject>; readonly meanings: ReadonlyMap<string, JsonObject>; readonly links: ReadonlyMap<string, JsonObject> }
export const validateNativeUslPlan = (plan: JsonObject, v2 = false): Either.Either<PlanTables, NativeUslV1Error> => {
  if (!exact(plan,["schema","languageVersion","namespace","resources","meanings","links","declarationStatus"]) || plan["schema"] !== "usl-semantic-plan/v1" || plan["languageVersion"] !== "0.1" || plan["declarationStatus"] !== "DECLARED" || !text(plan["namespace"])) return fail("plan version")
  const resources=named(plan["resources"],"resource"), meanings=named(plan["meanings"],"meaning"), links=named(plan["links"],"link")
  if (Either.isLeft(resources)||Either.isLeft(meanings)||Either.isLeft(links)) return fail("plan declarations")
  const all=[...resources.right.keys(),...meanings.right.keys(),...links.right.keys()]; if(new Set(all).size!==all.length)return fail("duplicate declaration name")
  for(const row of resources.right.values()){if(!exact(row,["name","locator"]))return fail("resource shape");const r=locator(row["locator"]);if(Either.isLeft(r))return fail<PlanTables>(r.left.detail)}
  for(const [meaningName,row] of meanings.right){const keys=Object.keys(row).filter(key=>key!=="contract");if(!(["name","roles","description"].every(key=>keys.includes(key)) && (keys.length===3 || keys.length===4&&keys.includes("grounded"))) || (!v2&&Object.hasOwn(row,"contract")))return fail("meaning shape");if(!Array.isArray(row["roles"])||row["roles"].length<2||row["roles"].length>16||!text(row["description"]))return fail("meaning role count");const roleNames=new Set<string>();for(const role of row["roles"]){if(!exact(role,["name","kind"]))return fail("role shape");const n=name(role["name"],"role name");if(Either.isLeft(n)||roleNames.has(n.right)||!text(role["kind"])||!["kg","url","git_repo","filesystem","any"].includes(role["kind"]))return fail("role");roleNames.add(n.right)}if(Object.hasOwn(row,"grounded")){const g=locator(row["grounded"]);if(Either.isLeft(g)||g.right["kind"]!=="kg")return fail("meaning grounding")}void meaningName}
  for(const row of links.right.values()){if(!exact(row,["name","meaning","participants"]))return fail("link shape");const m=name(row["meaning"],"link meaning");if(Either.isLeft(m)||!meanings.right.has(m.right)||!Array.isArray(row["participants"]))return fail("undeclared link meaning");const roles=meanings.right.get(m.right)!["roles"];if(!Array.isArray(roles)||row["participants"].length!==roles.length)return fail("participant count");for(let i=0;i<roles.length;i++){const p=row["participants"][i], role=roles[i];if(!exact(p,["role","resource"])||!object(role)||p["role"]!==role["name"]){return fail("participant role order")}const r=name(p["resource"],"participant resource");if(Either.isLeft(r)||!resources.right.has(r.right))return fail("undeclared participant resource");const resource=resources.right.get(r.right)!, loc=locator(resource["locator"]);if(Either.isLeft(loc)||role["kind"]!=="any"&&loc.right["kind"]!==role["kind"])return fail("participant type mismatch")}}
  return Either.right({resources:resources.right,meanings:meanings.right,links:links.right})
}

const resolution = (value: TaskJson | undefined, expected: JsonObject): Either.Either<JsonObject, NativeUslV1Error> => {
  if (!exact(value,["locator","resolvedLocator","contentHash","resolvedAt","guaranteeLevel","matchCount"])) return fail("resolution shape")
  const source=locator(expected), seen=locator(value["locator"]); if(Either.isLeft(source)||Either.isLeft(seen)||digest(source.right)!==digest(seen.right)||!text(value["resolvedLocator"])||typeof value["contentHash"]!=="string"||!/^[0-9a-f]{64}$/.test(value["contentHash"])||!text(value["guaranteeLevel"])||!["pure","sandboxed","trust_host"].includes(value["guaranteeLevel"])||typeof value["matchCount"]!=="number"||!Number.isSafeInteger(value["matchCount"])||value["matchCount"]<0) return fail("resolution")
  const resolvedAt=value["resolvedAt"],at=timestamp(resolvedAt); if(!text(resolvedAt)||Either.isLeft(at)) return fail("resolvedAt")
  return Either.right(value)
}
const observations = (value: TaskJson | undefined, expected: ReadonlyMap<string, JsonObject>, grounding: boolean): Either.Either<ReadonlyMap<string, JsonObject>, NativeUslV1Error> => {
  const found=named(value,grounding?"groundings":"report resources"); if(Either.isLeft(found)||found.right.size!==expected.size||[...expected.keys()].some(key=>!found.right.has(key))) return fail("report observation names do not match plan")
  for(const [key,row] of found.right){if(!exact(row,["name","status","resolution","issue"])||!text(row["status"])||!["RESOLVES","ORPHAN","AMBIGUOUS"].includes(row["status"]))return fail("report observation shape");const target=expected.get(key)![grounding?"grounded":"locator"];if(!object(target))return fail("report observation locator");if(row["status"]==="RESOLVES"){if(row["issue"]!==null)return fail("resolving observation issue");const checked=resolution(row["resolution"],target);if(Either.isLeft(checked)||checked.right["matchCount"]!==1)return fail("resolving observation is not unique")}else{if(!exact(row["issue"],["reason","detail"])||!text(row["issue"]["reason"])||!text(row["issue"]["detail"]))return fail("unresolved observation issue");if(row["status"]==="ORPHAN"&&row["resolution"]!==null)return fail("orphan observation resolution");if(row["status"]==="AMBIGUOUS"&&row["resolution"]!==null&&Either.isLeft(resolution(row["resolution"],target)))return fail("resolution")}}
  return Either.right(found.right)
}
const validateV1ReportPolicy = (report: JsonObject, policy: JsonObject, plan: JsonObject, tables: PlanTables, allowedReads: TaskJson): Either.Either<void, NativeUslV1Error> => {
  if(!exact(report,["schema","namespace","status","resources","groundings","links","semanticTruth"])||report["schema"]!=="usl-program-observation/v1"||report["namespace"]!==plan["namespace"]||report["semanticTruth"]!=="NOT_EVALUATED"||!text(report["status"])||!["RESOLVES","UNRESOLVED"].includes(report["status"]))return fail("report identity or semantic truth")
  const grounded=new Map([...tables.meanings].filter(([,meaning])=>Object.hasOwn(meaning,"grounded"))); const resourceRows=observations(report["resources"],tables.resources,false),groundingRows=observations(report["groundings"],grounded,true);if(Either.isLeft(resourceRows))return fail(resourceRows.left.detail);if(Either.isLeft(groundingRows))return fail(groundingRows.left.detail);const resolves=[...resourceRows.right.values(),...groundingRows.right.values()].every(row=>row["status"]==="RESOLVES");if((report["status"]==="RESOLVES")!==resolves)return fail("report aggregate status")
  const reportLinks=named(report["links"],"report link");if(Either.isLeft(reportLinks)||reportLinks.right.size!==tables.links.size||[...tables.links.keys()].some(key=>!reportLinks.right.has(key)))return fail("report link names do not match plan");for(const [linkName,row] of reportLinks.right){const link=tables.links.get(linkName)!;if(!exact(row,["name","meaning","participants","resourcesResolve","semanticTruth"])||row["meaning"]!==link["meaning"]||row["semanticTruth"]!=="NOT_EVALUATED"||typeof row["resourcesResolve"]!=="boolean"||digest(row["participants"]!)!==digest(link["participants"]!))return fail("report link meaning or semantic truth");const participants=link["participants"];if(!Array.isArray(participants)||row["resourcesResolve"]!==participants.every(participant=>object(participant)&&text(participant["resource"])&&resourceRows.right.get(participant["resource"])?.["status"]==="RESOLVES"))return fail("report link resource status")}
  if(!exact(policy,["schema_version","namespace","plan_digest","max_age_seconds","bindings","resources"])||policy["schema_version"]!=="hswm-usl-observation-policy/v1"||policy["namespace"]!==plan["namespace"]||policy["plan_digest"]!==digest(plan)||!isTaskNumber(policy["max_age_seconds"]!)||!Number.isFinite(Number(taskNumberValue(policy["max_age_seconds"]!)))||Number(taskNumberValue(policy["max_age_seconds"]!))<=0||Number(taskNumberValue(policy["max_age_seconds"]!))>86400)return fail("policy identity or plan digest")
  if(!Array.isArray(allowedReads)||allowedReads.some(entry=>!Array.isArray(entry)||entry.length!==2||!text(entry[0])||!text(entry[1])))return fail("allowed_reads");const permitted=new Set(allowedReads.map(entry=>JSON.stringify(entry)));const bindings=rows(policy["bindings"],"policy bindings");if(Either.isLeft(bindings)||bindings.right.length===0)return fail("policy bindings");const selected=new Set<string>(),targets=new Set<string>();for(const binding of bindings.right){if(!exact(binding,["link","role","field"])||Either.isLeft(name(binding["link"],"policy link"))||Either.isLeft(name(binding["role"],"policy role"))||Either.isLeft(name(binding["field"],"policy field")))return fail("policy binding shape");const link=binding["link"] as string,target=JSON.stringify([binding["role"],binding["field"]]);if(!tables.links.has(link)||selected.has(link))return fail("duplicate or unknown selected link");if(targets.has(target))return fail("duplicate policy role field");if(!permitted.has(target))return fail("unauthorized mapped read");selected.add(link);targets.add(target)}
  const pinRows=rows(policy["resources"],"policy resources");if(Either.isLeft(pinRows))return fail(pinRows.left.detail);const pins=new Map<string,JsonObject>();for(const row of pinRows.right){if(!text(row["name"])||pins.has(row["name"]))return fail("duplicate policy resource");pins.set(row["name"],row)}const required=new Set<string>();for(const linkName of selected){const link=tables.links.get(linkName)!;if(!Array.isArray(link["participants"]))return fail("policy selected link");for(const participant of link["participants"]){if(!object(participant)||!text(participant["resource"]))return fail("policy selected participant");required.add(participant["resource"])}const meaning=tables.meanings.get(String(link["meaning"]));if(meaning!==undefined&&Object.hasOwn(meaning,"grounded"))required.add(`meaning:${String(meaning["name"])}`)}if(pins.size!==required.size||[...required].some(key=>!pins.has(key)))return fail("policy resource pins do not exactly cover selected links");for(const row of pins.values())if(!exact(row,["name","content_hash","resolved_locator"])||typeof row["content_hash"]!=="string"||!/^[0-9a-f]{64}$/.test(row["content_hash"])||!text(row["resolved_locator"]))return fail("policy resource shape")
  return Either.right(undefined)
}

/** Validate caller policy pins and project only fresh selected reference reads. */
export const adaptNativeUslV1 = (input: TaskJson): Either.Either<TaskJson, NativeUslV1Error> => {
  if (!exact(input, ["plan", "report", "policy", "allowed_reads", "now", "revision"])) return fail("request shape")
  const plan = input["plan"], report = input["report"], policy = input["policy"]
  if (!object(plan) || !object(report) || !object(policy) || !Array.isArray(input["allowed_reads"]) || !isTaskNumber(input["now"]!) || !Number.isFinite(Number(taskNumberValue(input["now"]!))) || !text(input["revision"])) return fail("observation context")
  const tables=validateNativeUslPlan(plan); if(Either.isLeft(tables))return fail(tables.left.detail)
  const strict=validateV1ReportPolicy(report,policy,plan,tables.right,input["allowed_reads"]!);if(Either.isLeft(strict))return fail(strict.left.detail)
  const planResources=tables.right.resources, planLinks=tables.right.links
  if (report["schema"] !== "usl-program-observation/v1" || report["namespace"] !== plan["namespace"] || report["semanticTruth"] !== "NOT_EVALUATED") return fail("report identity or semantic truth")
  if (policy["schema_version"] !== "hswm-usl-observation-policy/v1" || policy["namespace"] !== plan["namespace"] || policy["plan_digest"] !== digest(plan) || !isTaskNumber(policy["max_age_seconds"]!) || Number(taskNumberValue(policy["max_age_seconds"]!)) <= 0) return fail("policy identity or plan digest")
  const bindings = rows(policy["bindings"], "policy bindings"), pins = policyPins(policy["resources"]), observed = named(report["resources"], "report observation"), groundings = named(report["groundings"], "report grounding")
  if (Either.isLeft(bindings)) return fail(bindings.left.detail)
  if (Either.isLeft(pins)) return fail(pins.left.detail)
  if (Either.isLeft(observed)) return fail(observed.left.detail)
  if (Either.isLeft(groundings)) return fail(groundings.left.detail)
  const allowed = new Set(input["allowed_reads"].map((entry) => Array.isArray(entry) && entry.length === 2 && text(entry[0]) && text(entry[1]) ? JSON.stringify([entry[0],entry[1]]) : ""))
  const outputLinks: TaskJson[] = [], outputObservations: TaskJson[] = []
  const source = digest({ plan_digest: digest(plan), report_digest: digest(report), policy_digest: digest(policy) })
  for (const [linkName, declaredLink] of planLinks) {
    const binding = bindings.right.find(row => row["link"] === linkName)
    if (binding === undefined) {
      outputLinks.push({ name: linkName, meaning: declaredLink["meaning"]!, participants: declaredLink["participants"]!, status: "UNKNOWN", reasons: ["NOT_SELECTED_BY_POLICY"] })
      continue
    }
    if (!exact(binding, ["link", "role", "field"]) || Either.isLeft(name(binding["link"],"policy link")) || Either.isLeft(name(binding["role"],"policy role")) || Either.isLeft(name(binding["field"],"policy field")) || !allowed.has(JSON.stringify([binding["role"],binding["field"]]))) return fail("unauthorized mapped read")
    const bindingLink = binding["link"], bindingRole = binding["role"], bindingField = binding["field"]
    if (!text(bindingLink) || !text(bindingRole) || !text(bindingField)) return fail("policy binding")
    const link = planLinks.get(bindingLink)
    if (link === undefined || !Array.isArray(link["participants"]) || !text(link["meaning"])) return fail("selected link")
    const reasons: string[] = []; let expiry = Infinity
    for (const participant of link["participants"]) {
      if (!object(participant) || !text(participant["resource"])) return fail("participant shape")
      const name = participant["resource"], row = observed.right.get(name), pin = pins.right.get(name)
      if (row !== undefined && pin !== undefined && object(row["resolution"]) && (row["resolution"]["contentHash"] !== pin["content_hash"] || row["resolution"]["resolvedLocator"] !== pin["resolved_locator"])) return fail(`resource pin mismatch: ${name}`)
      if (row === undefined || pin === undefined || row["status"] !== "RESOLVES" || !object(row["resolution"])) { reasons.push(`RESOURCE:${name}_${row === undefined ? "ORPHAN" : String(row["status"])}`); continue }
      const resolution = row["resolution"]
      const expectedResource=planResources.get(name); if(expectedResource===undefined)return fail("resolution"); const sourceLocator=locator(expectedResource["locator"]); if(Either.isLeft(sourceLocator)||!exact(resolution,["locator","resolvedLocator","contentHash","resolvedAt","guaranteeLevel","matchCount"])||digest(resolution["locator"]!)!==digest(sourceLocator.right)||!text(resolution["resolvedLocator"])||typeof resolution["contentHash"]!=="string"||!/^[0-9a-f]{64}$/.test(resolution["contentHash"])||!["pure","sandboxed","trust_host"].includes(String(resolution["guaranteeLevel"]))||typeof resolution["matchCount"]!=="number"||!Number.isSafeInteger(resolution["matchCount"])||resolution["matchCount"]!==1)return fail("resolution")
      if (resolution["contentHash"] !== pin["content_hash"] || resolution["resolvedLocator"] !== pin["resolved_locator"]) return fail(`resource pin mismatch: ${name}`)
      const at = timestamp(resolution["resolvedAt"])
      if (Either.isLeft(at)) return fail(at.left.detail)
      const now = Number(taskNumberValue(input["now"]!)), age = Number(taskNumberValue(policy["max_age_seconds"]!))
      if (at.right > now) { reasons.push(`RESOURCE:${name}_FUTURE_TIMESTAMP`); continue }
      const end = at.right + age
      if (now >= end) reasons.push(`RESOURCE:${name}_STALE`); else expiry = Math.min(expiry, end)
    }
    const meaning=tables.right.meanings.get(link["meaning"])
    if(meaning===undefined)return fail("selected meaning")
    if(Object.hasOwn(meaning,"grounded")){
      const groundingName=meaning["name"], row=groundings.right.get(String(groundingName)), pin=pins.right.get(`meaning:${String(groundingName)}`)
      if(row!==undefined&&pin!==undefined&&object(row["resolution"])&&(row["resolution"]["contentHash"]!==pin["content_hash"]||row["resolution"]["resolvedLocator"]!==pin["resolved_locator"]))return fail(`grounding pin mismatch: ${String(groundingName)}`)
      if(row===undefined||pin===undefined||row["status"]!=="RESOLVES"||!object(row["resolution"]))reasons.push(`GROUNDING:${String(groundingName)}_${row===undefined?"ORPHAN":String(row["status"])}`)
      else {const resolution=row["resolution"], at=timestamp(resolution["resolvedAt"]);if(resolution["contentHash"]!==pin["content_hash"]||resolution["resolvedLocator"]!==pin["resolved_locator"])return fail(`grounding pin mismatch: ${String(groundingName)}`);if(Either.isLeft(at))return fail(at.left.detail);const now=Number(taskNumberValue(input["now"]!)),age=Number(taskNumberValue(policy["max_age_seconds"]!));if(at.right>now)reasons.push(`GROUNDING:${String(groundingName)}_FUTURE_TIMESTAMP`);else if(now>=at.right+age)reasons.push(`GROUNDING:${String(groundingName)}_STALE`);else expiry=Math.min(expiry,at.right+age)}
    }
    const ready = reasons.length === 0
    outputLinks.push({ name: binding["link"]!, meaning: link["meaning"]!, participants: link["participants"]!, status: ready ? "READY" : "UNKNOWN", reasons })
    if (ready) outputObservations.push({ role: binding["role"]!, field: binding["field"]!, value: true, revision: input["revision"]!, expires_at: expiry, source })
  }
  return Either.right({ schema_version: "hswm-usl-observation-projection/v1", status: outputObservations.length === bindings.right.length ? "READY" : "UNRESOLVED", plan_digest: digest(plan), report_digest: digest(report), policy_digest: digest(policy), namespace: plan["namespace"]!, observations: outputObservations, links: outputLinks, mapping_loss: ["reference resolution only", "no semantic truth", "caller-bound report not attestation", "no content extraction/credit/admission"] })
}
