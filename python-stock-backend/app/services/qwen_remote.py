"""Shared Docker Qwen transport through the existing private SSH connection."""
import json
import os
import shlex
import subprocess

MODEL = 'qwen2.5:7b'


def completion(payload, key=None, user=None):
    request = dict(payload)
    request['model'] = MODEL
    request['stream'] = False
    # Native API permits a bounded context on the 8GB shared host.
    native = {'model': MODEL, 'messages': request['messages'], 'stream': False,
              'options': {'num_ctx': 2048, 'num_predict': min(request.get('max_tokens',160),256), 'temperature':0.2},
              'keep_alive':'10m'}
    if request.get('tools'):
        native['tools'] = request['tools']
    script = "import sys,httpx; r=httpx.post('http://fin-ai-ollama:11434/api/chat',content=sys.stdin.read(),headers={'Content-Type':'application/json'},timeout=580); r.raise_for_status(); print(r.text)"
    command = 'docker run --rm -i --network shared-net --memory 128m --entrypoint python lumina-invest-app:fd -c ' + shlex.quote(script)
    args = ['ssh','-i',key or os.environ['LEAN_SSH_KEY_PATH'],'-o','BatchMode=yes',
            '-o','StrictHostKeyChecking=accept-new','-o','ConnectTimeout=10',
            f"{user or os.environ.get('LEAN_SSH_USER','lean-iv')}@172.31.0.151", command]
    run = subprocess.run(args,input=json.dumps(native,ensure_ascii=False),capture_output=True,text=True,timeout=600)
    if run.returncode:
        raise RuntimeError('공통 Docker Qwen 연결 실패')
    result = json.loads(run.stdout)
    message = result.get('message') or {}
    if not message.get('content') and not message.get('tool_calls'):
        raise RuntimeError('Qwen 응답이 비어 있습니다.')
    for index, call in enumerate(message.get('tool_calls',[])):
        call.setdefault('id',f'qwen_{index}')
        call.setdefault('type','function')
        args = call['function'].get('arguments',{})
        if isinstance(args,dict):
            call['function']['arguments']=json.dumps(args,ensure_ascii=False)
    return {'model':MODEL,'choices':[{'message':message,'finish_reason':'tool_calls' if message.get('tool_calls') else 'stop'}]}
