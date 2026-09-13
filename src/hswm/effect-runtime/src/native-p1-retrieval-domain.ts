/** Frozen PhantomWiki retrieval projection: cached cosine seeds plus strict weighted K<=2 walk. */
import { createHash } from "node:crypto"
import { Data, Either } from "effect"
import type { NativeP1NpyArray } from "./native-p1-npy-domain.js"

export class NativeP1RetrievalError extends Data.TaggedError("NativeP1RetrievalError")<{readonly detail:string}>{}
const failure=(detail:string)=>new NativeP1RetrievalError({detail})
const sha=(text:string):string=>createHash("sha256").update(text,"utf8").digest("hex")
export const nativeP1SourceId=(title:string):string=>`phantom:${sha(title).slice(0,32)}`
const surfaces:Readonly<Record<string,readonly string[]>>=Object.freeze({sister:["sisters","sister"],brother:["brothers","brother"],mother:["mother"],father:["father"],daughter:["daughters","daughter"],son:["sons","son"],wife:["wife"],husband:["husband"],friend:["friends","friend"],job:["occupation"],hobby:["hobby"],gender:["gender"],dob:["date of birth"]})
const person=Object.freeze(["sister","brother","mother","father","daughter","son","wife","husband","friend"])
export interface NativeP1Article {readonly article:string;readonly facts:readonly string[];readonly title:string}
export interface NativeP1Question {readonly answer?:readonly unknown[];readonly id:string;readonly is_aggregation_question?:boolean;readonly question:string;readonly solution_traces?:unknown}
export interface NativeP1Arc {readonly arcId:string;readonly join:string;readonly source:number;readonly sourceClaim:string;readonly sourcePredicate:string;readonly sourceArgumentRole?:string;readonly targetPredicate?:string;readonly target:number;readonly targetClaim:string;readonly targetId:string}
export interface NativeP1Graph {readonly arcs:readonly NativeP1Arc[];readonly targetIds:readonly string[]}
export const buildNativeP1Graph=(articles:readonly NativeP1Article[]):Either.Either<NativeP1Graph,NativeP1RetrievalError>=>{
 if(articles.length===0||articles.some(article=>!article.title||!article.article||!Array.isArray(article.facts)))return Either.left(failure("invalid PhantomWiki articles"))
 const ordered=[...articles].sort((left,right)=>left.title<right.title?-1:left.title>right.title?1:0)
 const index=Object.freeze(Object.fromEntries(ordered.map((article,ordinal)=>[article.title,ordinal])))
 const firstClaim:Record<string,{readonly id:string;readonly predicate:string}>={}
 const pending:Array<{readonly arcId:string;readonly ordinal:number;readonly predicate:string;readonly role:string;readonly target:string;readonly sourceClaim:string}>=[]
 for(const [ordinal,article] of ordered.entries())for(const [factIndex,fact] of article.facts.entries()){
  const parsed=/^([\p{L}\p{N}_]+)\("([^"]+)",\s*"([^"]+)"\)\.$/u.exec(fact.trim());if(parsed===null||parsed[2]!==article.title)continue
  const role=parsed[1]!,target=parsed[3]!,candidates=surfaces[role]??[role]
  let lineOffset=0,predicateStart=-1,predicate=""
  for(const line of article.article.split("\n")){
   if(line.includes(article.title)&&line.includes(target)){const surface=candidates.find(value=>line.includes(value));if(surface!==undefined){predicate=surface;predicateStart=lineOffset+line.indexOf(surface);break}}
   lineOffset+=line.length+1
  }
  if(predicateStart<0)continue
  const objectStart=article.article.indexOf(target,predicateStart)
  if(objectStart<0)continue
  const claim=`claim:${nativeP1SourceId(article.title)}:${factIndex}`
  firstClaim[article.title]??=Object.freeze({id:claim,predicate})
  if(person.includes(role)&&index[target]!==undefined)pending.push(Object.freeze({arcId:`arc:${claim}:${Array.from(article.article.slice(0,objectStart)).length}`,ordinal,predicate,role,target,sourceClaim:claim}))
 }
 const arcs=Object.freeze(pending.flatMap(item=>{const targetClaim=firstClaim[item.target],target=index[item.target];return targetClaim===undefined||target===undefined||target===item.ordinal?[]:[Object.freeze({arcId:item.arcId,join:`person:${item.target}`,source:item.ordinal,sourceClaim:item.sourceClaim,sourcePredicate:item.predicate,sourceArgumentRole:item.role,targetPredicate:targetClaim.predicate,target,targetClaim:targetClaim.id,targetId:nativeP1SourceId(item.target)})]}).sort((left,right)=>left.arcId<right.arcId?-1:left.arcId>right.arcId?1:0))
 return Either.right(Object.freeze({arcs,targetIds:Object.freeze(ordered.map(article=>nativeP1SourceId(article.title)))}))
}
const stop=Object.freeze(["a","an","and","are","as","at","be","by","did","do","does","for","from","how","in","is","it","of","on","or","that","the","this","to","was","were","what","when","where","which","who","whom","whose","why","with","both","such","american","film","dutch","drama","comedy"])
const families=Object.freeze([Object.freeze(["direct","director","directed","directing"]),Object.freeze(["star","starring","stars","actor","actress","cast"]),Object.freeze(["write","written","writer","author","screenplay"]),Object.freeze(["produc","producer","produced"]),Object.freeze(["born","birth","birthplace","nativ"]),Object.freeze(["die","died","death","deceased"]),Object.freeze(["son","daughter","child","father","mother","parent","sister","brother","twin","wife","husband","spouse","married","marriage","consort"]),Object.freeze(["found","founder","founded","founding","establish"]),Object.freeze(["releas","release","published","publication"]),Object.freeze(["border","borders","adjacent","located","location","headquarter","capital"]),Object.freeze(["collabor","work","worked","partner"])])
const stem=(word:string):string=>{for(const suffix of ["ingly","edly","ation","ions","ment","ers","ing","ed","er","es","s"])if(word.length-suffix.length>=4&&word.endsWith(suffix))return word.slice(0,-suffix.length);return word}
const words=(value:string):readonly string[]=>Object.freeze((value.normalize("NFKC").toLowerCase().replaceAll("ß","ss").replaceAll("ς","σ").match(/[\p{L}\p{N}]+/gu)??[]).filter(word=>word.length>=2&&!stop.includes(word)).map(stem).filter(word=>word.length>0&&!stop.includes(word)).filter((word,index,all)=>all.indexOf(word)===index).sort())
const familyFor=(term:string):readonly string[]|undefined=>families.find(values=>values.some(value=>term===value||(Math.min(term.length,value.length)>=4&&(term.startsWith(value)||value.startsWith(term)))))
const aliases=(terms:readonly string[]):readonly string[]=>Object.freeze(terms.flatMap(term=>[term,...(familyFor(term)??[]),...(["e","er","or","ed","ing"].map(suffix=>term+suffix))]).filter((term,index,all)=>all.indexOf(term)===index).sort())
const aliasIndex=(graph:NativeP1Graph):Readonly<Record<string,readonly string[]>>=>{
 const predicates=graph.arcs.flatMap(arc=>arc.targetPredicate===undefined?[arc.sourcePredicate]:[arc.sourcePredicate,arc.targetPredicate]),base=Object.fromEntries(predicates.map(predicate=>[predicate,words(predicate)])),byTerm:Record<string,string[]>={}
 for(const predicate of predicates)for(const term of base[predicate]!)for(const key of [term,...(familyFor(term)??[])])byTerm[key]=[...(byTerm[key]??[]),predicate]
 const entries=Object.entries(base).map(([predicate,terms])=>{
  const shared=terms.filter(term=>term.length>=5).flatMap(term=>(byTerm[term]??[]).flatMap(other=>base[other]??[]))
  return [predicate,Object.freeze([...new Set([...aliases(terms),...shared])])] as const
 })
 return Object.freeze(Object.fromEntries(entries))
}
const coverage=(terms:readonly string[],query:readonly string[]):number=>terms.length===0||query.length===0?0:terms.filter(word=>query.some(term=>word===term||(Math.min(word.length,term.length)>=5&&(word.startsWith(term)||term.startsWith(word))))).length/terms.length
const quality=(query:readonly string[],arc:NativeP1Arc,index:Readonly<Record<string,readonly string[]>>):number=>.75*coverage(index[arc.sourcePredicate]??words(arc.sourcePredicate),query)+.25*coverage(aliases(words(arc.sourceArgumentRole??arc.sourcePredicate)),query)
export const nativeP1Cosine=(documents:readonly number[],query:readonly number[],dimension:number):Either.Either<readonly number[],NativeP1RetrievalError>=>{
 if(!Number.isSafeInteger(dimension)||dimension<1||query.length!==dimension||documents.length===0||documents.length%dimension!==0||[...documents,...query].some(value=>!Number.isFinite(value)))return Either.left(failure("cached embedding dimensions drift"))
 return Either.right(Object.freeze(Array.from({length:documents.length/dimension},(_,row)=>query.reduce((sum,value,column)=>sum+value*documents[row*dimension+column]!,0))))
}
const canonical=(value:unknown):string=>JSON.stringify(value,Object.keys(value as object).sort())
export const nativeP1TraceGolds=(question:NativeP1Question,titles:Readonly<Record<string,number>>):readonly (readonly string[])[]=>{
 const raw=typeof question.solution_traces==="string"?(()=>{try{return JSON.parse(question.solution_traces)}catch{return []}})():question.solution_traces,traces=Array.isArray(raw)?raw:[],fromTrace=traces.slice(0,20).flatMap(trace=>trace!==null&&typeof trace==="object"?[Object.freeze(Object.values(trace).filter((value):value is string=>typeof value==="string"&&titles[value]!==undefined).map(nativeP1SourceId).filter((value,index,all)=>all.indexOf(value)===index).sort())]:[]).filter(values=>values.length>0&&values.length<=8)
 if(fromTrace.length>0)return Object.freeze(fromTrace)
 const answers=(question.answer??[]).filter((value):value is string=>typeof value==="string"&&titles[value]!==undefined).map(nativeP1SourceId).sort()
 return answers.length>0&&answers.length<=8?Object.freeze([Object.freeze(answers)]):Object.freeze([])
}
export const nativeP1RecallAt10=(ranked:readonly string[],golds:readonly (readonly string[])[]):number=>golds.length===0?0:Math.max(...golds.map(gold=>ranked.slice(0,10).filter(value=>gold.includes(value)).length/gold.length))
export const splitNativeP1Questions=(questions:readonly NativeP1Question[],articles:readonly NativeP1Article[]):Either.Either<Readonly<{readonly episodeQuestions:readonly (readonly NativeP1Question[])[];readonly gateQuestions:readonly (readonly NativeP1Question[])[]}>,NativeP1RetrievalError>=>{
 const titles=Object.freeze(Object.fromEntries(articles.map(article=>[article.title,1]))),eligible=questions.filter(question=>question.is_aggregation_question!==true&&nativeP1TraceGolds(question,titles).length>0).sort((left,right)=>sha(canonical({seed:9173,question_id:left.id}))<sha(canonical({seed:9173,question_id:right.id}))?-1:1),required=5*(40+38)
 if(eligible.length<required)return Either.left(failure(`eligible question count ${eligible.length} is below required ${required}`))
 return Either.right(Object.freeze({episodeQuestions:Object.freeze(Array.from({length:5},(_,index)=>Object.freeze(eligible.slice(index*40,(index+1)*40)))),gateQuestions:Object.freeze(Array.from({length:5},(_,index)=>Object.freeze(eligible.slice(200+index*38,200+(index+1)*38))))}))
}
interface Path {readonly edges:readonly string[];readonly joins:readonly string[];readonly nodes:readonly number[];readonly score:number;readonly target:number;readonly claim:string}
const preferred=(candidate:Path,prior:Path|undefined):boolean=>prior===undefined||candidate.score>prior.score||(candidate.score===prior.score&&candidate.edges.join("\u0000")<prior.edges.join("\u0000"))
export const nativeP1Walk=(staticScores:readonly number[],graph:NativeP1Graph,seeds:readonly number[],weights:Readonly<Record<string,number>>,query:string):Either.Either<readonly number[],NativeP1RetrievalError>=>{
 if(staticScores.some(value=>!Number.isFinite(value))||new Set(seeds).size!==seeds.length||staticScores.length!==graph.targetIds.length||seeds.some(seed=>!Number.isInteger(seed)||seed<0||seed>=staticScores.length)||Object.keys(weights).length!==graph.arcs.length||graph.arcs.some(arc=>!Number.isFinite(weights[arc.arcId]??NaN)||(weights[arc.arcId]??1)>0))return Either.left(failure("weighted walk input drift"))
 const adjacency=Object.freeze(Array.from({length:staticScores.length},(_,source)=>graph.arcs.filter(arc=>arc.source===source))),terms=aliases(words(query)),index=aliasIndex(graph),first:Path[]=[]
 for(const seed of seeds){const row=adjacency[seed]!,base=Math.max(0,staticScores[seed]!);for(const arc of row){const score=base*Math.pow(row.length,-.5)*quality(terms,arc,index)*Math.exp(weights[arc.arcId]!);if(score>0)first.push(Object.freeze({edges:Object.freeze([arc.arcId]),joins:Object.freeze([arc.join]),nodes:Object.freeze([seed,arc.target]),score,target:arc.target,claim:arc.targetClaim}))}}
 const best1:Record<number,Path>={},best2:Record<number,Path>={};for(const path of first){if(preferred(path,best1[path.target]))best1[path.target]=path;const row=adjacency[path.target]!.filter(arc=>arc.sourceClaim===path.claim);for(const arc of row){if(path.nodes.includes(arc.target)||path.joins.includes(arc.join))continue;const score=path.score*Math.pow(row.length,-.5)*quality(terms,arc,index)*Math.exp(weights[arc.arcId]!);const next=Object.freeze({edges:Object.freeze([...path.edges,arc.arcId]),joins:Object.freeze([...path.joins,arc.join]),nodes:Object.freeze([...path.nodes,arc.target]),score,target:arc.target,claim:arc.targetClaim});if(score>0&&preferred(next,best2[next.target]))best2[next.target]=next}}
 return Either.right(Object.freeze(staticScores.map((value,target)=>value+.1*Math.max(best1[target]?.score??0,best2[target]?.score??0))))
}
export const nativeP1CachedRecall=(graph:NativeP1Graph,documents:NativeP1NpyArray,questionIds:NativeP1NpyArray,questions:NativeP1NpyArray,question:NativeP1Question,weights:Readonly<Record<string,number>>,golds:readonly (readonly string[])[]):Either.Either<number,NativeP1RetrievalError>=>{
 if(documents.dtype!=="f8"||documents.shape.length!==2||questionIds.dtype!=="unicode"||questionIds.shape.length!==1||questions.dtype!=="f8"||questions.shape.length!==2||documents.shape[0]!==graph.targetIds.length||questions.shape[0]!==questionIds.shape[0]||documents.shape[1]!==questions.shape[1])return Either.left(failure("cached P1 embedding shape drift"))
 const questionIndex=(questionIds.values as readonly string[]).indexOf(question.id);if(questionIndex<0)return Either.left(failure(`cached query is missing ${question.id}`));const dimension=documents.shape[1]!,staticScores=nativeP1Cosine(documents.values as readonly number[],(questions.values as readonly number[]).slice(questionIndex*dimension,(questionIndex+1)*dimension),dimension);if(Either.isLeft(staticScores))return Either.left(staticScores.left)
 const seeds=Object.freeze(staticScores.right.map((score,index)=>Object.freeze({index,score})).sort((left,right)=>right.score-left.score||left.index-right.index).slice(0,3).map(value=>value.index)),walked=nativeP1Walk(staticScores.right,graph,seeds,weights,question.question);if(Either.isLeft(walked))return Either.left(walked.left)
 const ranked=Object.freeze(walked.right.map((score,index)=>Object.freeze({index,score})).sort((left,right)=>right.score-left.score||left.index-right.index).slice(0,10).map(value=>graph.targetIds[value.index]!));return Either.right(nativeP1RecallAt10(ranked,golds))
}
