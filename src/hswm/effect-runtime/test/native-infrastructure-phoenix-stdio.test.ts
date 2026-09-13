import { mkdtemp, writeFile, rm, chmod } from "node:fs/promises"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { Effect, Either } from "effect"
import { expect, it } from "vitest"
import { runPhoenixViewerMcpSmoke } from "../src/native-infrastructure-smoke-phoenix.js"
const fixture = (hidden: boolean, readError = false) => `#!${process.execPath}
import readline from 'node:readline';
const names=['describeSqlSchema','executeSql','getProject','getProjects'];
const tool=name=>({name,inputSchema:{type:'object'},annotations:{readOnlyHint:true}});
const lines=readline.createInterface({input:process.stdin});
for await(const line of lines){const r=JSON.parse(line);if(r.id===undefined)continue;let result;
if(r.method==='server/discover'){process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:r.id,error:{code:-32601,message:'legacy fixture'}})+'\\n');continue;}
if(r.method==='initialize')result={protocolVersion:'2025-11-25',capabilities:{tools:{}},serverInfo:{name:'isolated-native-test',version:'1'}};
else if(r.method==='tools/list')result=r.params?.cursor?{tools:${hidden ? "[tool('hiddenWrite')]" : "[tool(names[3])]"}}:{tools:names.slice(0,3).map(tool),nextCursor:'page-2'};
else if(r.method==='tools/call')result={content:[],isError:${readError ? "r.params.arguments.sql.startsWith('SELECT')" : "false"},structuredContent:r.params.arguments.sql.startsWith('SELECT')?{rows:[[1]]}:{error:{code:'not_read_only'}}};
else result={};
process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:r.id,result})+'\\n');
}
`
it.each([{hidden:false,readError:false,accepted:true},{hidden:true,readError:false,accepted:false},{hidden:false,readError:true,accepted:false}])("uses real MCP stdio with complete pagination and preserves tool errors: %j", async scenario => {
 const directory=await mkdtemp(join(tmpdir(),"hswm-phoenix-wire-")),launcher=join(directory,"fixture.mjs")
 try{
  await writeFile(launcher,fixture(scenario.hidden,scenario.readError));await chmod(launcher,0o700)
  const result=await Effect.runPromise(Effect.either(runPhoenixViewerMcpSmoke(launcher)))
  expect(Either.isRight(result),Either.isLeft(result)?result.left.detail:"").toBe(scenario.accepted)
  if(Either.isRight(result))expect(result.right).toMatchObject({status:"PASS",tools:["describeSqlSchema","executeSql","getProject","getProjects"],unsafe_sql_code:"not_read_only"})
 }finally{await rm(directory,{recursive:true,force:true})}
},15000)
