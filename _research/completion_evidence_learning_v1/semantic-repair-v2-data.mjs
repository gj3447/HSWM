/** Reuse the sealed split only after verifying that v1 never opened it. */
import { readFile, readdir } from "node:fs/promises"
import { join } from "node:path"
import { sha256, canonical } from "./domain.mts"
import { loadRepairDataset } from "./semantic-repair-data.mjs"
import { previousTrial, assertSealedPriorTrial } from "./semantic-repair-v2-domain.mts"

export const inventory = async root => {
  const paths=[]
  for(const dir of ["rows","wire"])for(const name of await readdir(join(root,dir)))paths.push(`${dir}/${name}`)
  const records=[]
  for(const path of paths.sort()){
    const raw=await readFile(join(root,path));records.push({path,sha256:sha256(raw),bytes:raw.length})
  }
  return {contract:"lexically-sorted-path-sha256-size-canonical-json/v1",files:records.length,sha256:sha256(canonical(records))}
}

export const loadRepairDatasetV2 = async directory => {
  const previousRoot=".hswm-local/semantic-repair-20261115"
  const receiptBytes=await readFile(`_research/completion_evidence_learning_v1/receipts/${previousTrial.receiptSha256}.json`)
  if(sha256(receiptBytes)!==previousTrial.receiptSha256)throw new Error("Changed prior receipt")
  const receipt=JSON.parse(receiptBytes)
  if(receipt.run_id!==previousTrial.runId||receipt.source_files['summary.json']!==previousTrial.summarySha256||
    receipt.source_files['plan.json']!==previousTrial.planSha256)throw new Error("Prior identity/pins differ")
  for(const [path,hash]of Object.entries(receipt.source_files))
    if(sha256(await readFile(join(previousRoot,path)))!==hash)throw new Error(`Changed prior source: ${path}`)
  for(const [path,hash]of Object.entries(receipt.source_code.files))
    if(sha256(await readFile(path))!==hash)throw new Error(`Changed v1 code: ${path}`)
  const summary=JSON.parse(await readFile(join(previousRoot,"summary.json"),"utf8"))
  assertSealedPriorTrial(summary)
  if((await readdir(previousRoot)).some(n=>["evaluate-started.json","evaluation.json"].includes(n)))throw new Error("Prior evaluation was opened")
  for(const arm of ["baseline","candidate"]){
    if(canonical(await inventory(join(previousRoot,arm)))!==canonical(receipt.row_wire_inventories[arm]))throw new Error("Prior rows/wire changed; exposure uncertain")
  }
  const priorPlan=JSON.parse(await readFile(join(previousRoot,"baseline/plan.json"),"utf8"))
  const dataset=await loadRepairDataset(directory)
  if(canonical(dataset.cases)!==canonical(priorPlan.cases)||canonical(dataset.baselinePrograms)!==canonical(priorPlan.programs))throw new Error("Split or baseline differs from prior trial")
  return {...dataset,previousTrial:{...previousTrial,verifiedUnopenedTest:true}}
}
