// Read-only numerical probes against the unchanged legacy script. Not product tests.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '../../..');
const html = fs.readFileSync(path.join(root, 'legacy', 'startupvalue_dashboard_v2.html'), 'utf8');
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const context = vm.createContext({});
vm.runInContext(source, context);
const run = expression => vm.runInContext(expression, context);
const actualTax = run("calcImposto(120000,60000,'simples',3,3)/12");
assert.equal(actualTax, 50);
const legacyVC = run('calcVC([Array(60).fill(100000)],1,0.3,8)[0]');
const correctedVC = 1200000 * 8 / 1.3 ** 5;
const legacyDCF = run('calcDCF([Array(60).fill(100)],1,true,0.12,0.03)[0]');
const rm = 1.12 ** (1/12) - 1, gm = 1.03 ** (1/12) - 1;
const correctedDCF = Array.from({length:60},(_,i)=>100/(1+rm)**(i+1)).reduce((a,b)=>a+b,0)
  + (100*(1+gm)/(rm-gm))/(1+rm)**60;
const invalidG = run('calcDCF([Array(60).fill(100)],1,true,0.12,0.12)[0]');
const all = [-100,0,0,100,200];
context.sample = all;
const fullMedian = run('percentile(sample,50)');
const positiveMedian = run('percentile(sample.filter(x=>x>0),50)');
assert.equal(fullMedian,0); assert.equal(positiveMedian,150);
const constantHistogram = run('makeHistogram([100,100,100])');
assert(constantHistogram.density.some(x=>!Number.isFinite(x)));
const findings = {
  scope:'Executed unmodified legacy functions in isolated Node VM; independent arithmetic comparisons. Does not validate proposed application.',
  simples:{annualRevenue:120000,legacyMonthlyTax:actualTax,expectedMonthlyTaxUnderLegacyAnnualTable:600,understatementFactor:12},
  vc:{monthlyEbitda:100000,multiple:8,targetReturn:0.3,years:5,legacy:legacyVC,proposedPVExitEquityAssumingZeroNetDebt:correctedVC},
  terminal:{monthlyCF:100,waccAnnual:0.12,gAnnual:0.03,legacyDCF,correctedDCF,legacyWhenGEqualsWacc:invalidG,expectedInvalidG:'validation error'},
  dilution:{preMoney:1000000,requestedOwnership:0.2,legacyInvestment:200000,actualOwnership:200000/1200000,correctInvestment:250000},
  selectionBias:{values:all,fullMedian,positiveMedian,retainedObservations:2,totalObservations:5},
  constantHistogram:{finiteDensity:false,expected:'single mass/bin with all observations'},
  triangular:{legacyMeanForBase100:50+100*2/3,expectedMeanForMin50Mode100Max150:100},
};
fs.writeFileSync(path.join(__dirname,'legacy_probe_results.json'),JSON.stringify(findings,null,2)+'\n');
console.log(JSON.stringify(findings,null,2));
