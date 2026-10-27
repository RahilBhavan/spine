import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const context = vm.createContext({ URLSearchParams, usd:value=>'$'+Math.round(value) });
vm.runInContext(readFileSync('site/workspace.js','utf8'),context);
const markets = {big:{state:{borrow_usd:500,distance_to_capacity:.3}},tight:{state:{borrow_usd:50,distance_to_capacity:.08}},watch:{state:{borrow_usd:100,distance_to_capacity:.2}},uncrossed:{state:{borrow_usd:200,distance_to_capacity:null}}};
assert.equal(context.watchlistRows(markets,'all','borrow')[0][0],'big');
assert.equal(context.watchlistRows(markets,'all','distance')[0][0],'tight');
assert.equal(context.watchlistRows(markets,'all','distance').at(-1)[0],'uncrossed');
assert.equal(context.watchlistRows(markets,'attention','borrow').map(([key])=>key).join(','),'watch,tight');
assert.equal(context.watchlistRows({},'attention','borrow').length,0);
const curve=[{drop:0,borrow_usd:0},{drop:.2,borrow_usd:100},{drop:.7,borrow_usd:500}];
assert.equal(context.shockSample(curve,20).borrow_usd,100);
assert.equal(context.shockSample(curve,19),null);
assert.equal(context.shockSample(curve,0).borrow_usd,0);
assert.equal(context.shockSample(curve,70).borrow_usd,500);
context.readWorkspaceUrl(new URLSearchParams('filter=attention&sort=distance&shock=30'));
let url = new URL('https://spine.test/?market=WETH'); context.writeWorkspaceUrl(url);
assert.equal(url.searchParams.get('market'),'WETH');
assert.equal(url.searchParams.get('filter'),'attention');
assert.equal(url.searchParams.get('sort'),'distance');
assert.equal(url.searchParams.get('shock'),'30');
for(const invalid of ['-1','71','NaN','20.5','Infinity']) {
 context.readWorkspaceUrl(new URLSearchParams('filter=invalid&sort=invalid&shock='+invalid));
 url = new URL('https://spine.test/?filter=old&sort=old&shock=old');context.writeWorkspaceUrl(url);
 assert.equal(url.search,'');
}
const data=JSON.parse(readFileSync('data/summary.json'));
for(const m of Object.values(data.markets)) for(const drop of [0,10,20,30,70]) {
 const sample=context.shockSample(m.liquidatable_curve,drop);
 assert.ok(sample,'Source contains the exact requested sample');
 assert.ok(sample.borrow_usd>=sample.bad_borrow_usd,'Bad-debt subset never exceeds liquidatable borrow');
}
const btc = data.markets.cbBTC;
assert.match(context.capacityExplanation(btc), /× 30%/);
assert.match(context.capacityExplanation(btc), /× 50%/);
assert.match(context.capacityExplanation({...btc,state:{...btc.state,capacity_ab_usd:123}}), /does not expose a matching parameter/);
assert.match(context.capacityExplanation({state:{capacity_ab_usd:null}}), /unavailable/);
console.log('Workspace logic: sorting, filters, URL boundaries and 45 exact source samples passed.');
