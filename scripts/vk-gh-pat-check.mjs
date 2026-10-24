// GitHub Actions PAT diagnostics: no VK calls and no token logging.
import { randomBytes } from 'node:crypto';
import { spawnSync } from 'node:child_process';

const repo = 'lsevmos-gpt/ls-vk';
const pat = process.env.VK_SECRETS_WRITE_PAT || '';
if (process.env.GITHUB_REPOSITORY !== repo ||
    process.env.GITHUB_REF !== 'refs/heads/main' ||
    process.env.GITHUB_EVENT_NAME !== 'push' ||
    process.env.GITHUB_ACTOR !== 'lsevmos-gpt' ||
    process.env.GITHUB_WORKFLOW_REF !==
      'lsevmos-gpt/ls-vk/.github/workflows/vk-gh-pat-check-once.yml@refs/heads/main') {
  throw new Error('UNAUTHORIZED_DIAGNOSTIC_CONTEXT');
}
console.log('PAT_CONFIGURED=' + (pat.length > 10 ? 'YES' : 'NO'));
const isCliAvailable = spawnSync('gh', ['--version'], {encoding:'utf8',timeout:10000});
console.log('GH_CLI=' + (isCliAvailable.status === 0 ? 'INSTALLED' : 'UNAVAILABLE'));

const response = await fetch(
  'https://api.github.com/repos/lsevmos-gpt/ls-vk/actions/secrets/public-key',
  {
    method:'GET',
    headers: {
      authorization:'Bearer ' + pat,
      accept:'application/vnd.github+json',
      'x-github-api-version':'2022-11-28',
      'user-agent':'ls-vk-pat-permission-diagnostic'
    },
    signal:AbortSignal.timeout(15000)
  }
).catch(()=>null);
console.log('GH_SECRETS_PUBLIC_KEY_HTTP='+(response?.status || 'NETWORK_ERROR'));

if (response?.status !== 200 || isCliAvailable.status !== 0) {
  console.log('GH_SECRET_WRITE=NOT_ATTEMPTED');
  process.exitCode=1;
} else {
  const env={
    PATH:process.env.PATH||'',HOME:process.env.HOME||'',
    GH_TOKEN:pat,GH_HOST:'github.com',CI:'true'
  };
  function gh(args,value=''){
    return spawnSync('gh',args,{input:value,encoding:'utf8',env,timeout:25000,maxBuffer:65536});
  }
  const result=gh(['secret','set','VK_REFRESH_WRITE_PROBE','--repo',repo],randomBytes(32).toString('base64url'));
  const status = result.status === 0 ? 'OK' : 'FAIL';
  console.log('GH_SECRET_SET='+status);
  if(status !== 'OK'){
    const err=String(result.stderr || result.error?.message || '');
    let reason = 'UNKNOWN';
    if(/404|not found/i.test(err))reason='HTTP_404_OR_NOT_FOUND';
    else if(/403|forbidden|resource not accessible|not accessible by/i.test(err))reason='HTTP_403_OR_PERMISSION';
    else if(/401|bad credentials|unauthorized/i.test(err))reason='HTTP_401_OR_AUTH';
    else if(/not found in \$PATH|ENOENT|executable file/i.test(err))reason='EXECUTABLE_UNAVAILABLE';
    else if(/timeout/i.test(err))reason='TIMEOUT';
    console.log('GH_SECRET_SET_REASON='+reason);
    process.exitCode=1;
  }else{
    const del=gh(['secret','delete','VK_REFRESH_WRITE_PROBE','--repo',repo]);
    console.log('GH_SECRET_CANARY_CLEANUP='+(del.status===0?'OK':'FAILED'));
  }
}
