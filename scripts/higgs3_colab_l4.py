import base64
import glob
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import requests
import soundfile as sf

OUT = Path("/content/out"); OUT.mkdir(exist_ok=True, parents=True)
LOG = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)
LOG(subprocess.run('nvidia-smi -L',shell=True,capture_output=True,text=True).stdout)
VENV="/content/h3env"
subprocess.run(["rm","-rf",VENV])
if not Path(VENV,"bin","vllm").exists():
    subprocess.run(["pip","install","-q","uv"],check=False)
    subprocess.run(["uv","venv",VENV,"--python","3.12"],check=True)
    subprocess.run(["uv","pip","install","-p",VENV+"/bin/python","-q","vllm==0.30.0","vllm-omni==0.30.0","huggingface_hub"],check=True)
LOG("venv ready")
ymls=glob.glob(VENV+"/lib/python3.12/site-packages/vllm_omni/deploy/higgs_multimodal_qwen3.yaml")
assert ymls, "deploy yaml not found"
yml=Path(ymls[0]); cfg=yml.read_text()
cfg = cfg.replace("attention_backend: FLASHINFER","attention_backend: TRITON_ATTN").replace("max_model_len: 8192","max_model_len: 4096")
yml.write_text(cfg); LOG("patched", yml)
env = dict(os.environ, VLLM_ATTENTION_BACKEND="TRITON_ATTN", VLLM_USE_FLASHINFER_SAMPLER="0")
srv = subprocess.Popen([VENV+"/bin/vllm","serve","bosonai/higgs-audio-v3-tts-4b","--host","127.0.0.1","--port","8095","--trust-remote-code","--omni","--dtype","bfloat16"],env=env,stdout=open("/content/vllm.log","w"),stderr=subprocess.STDOUT)
ok=False
for _ in range(240):
    time.sleep(10)
    try:
        if requests.get("http://127.0.0.1:8095/v1/models",timeout=5).ok: ok=True;break
    except Exception:
        if srv.poll() is not None: break
LOG("server ready", ok)
if not ok: sys.exit("server failed; see /content/vllm.log")
ref = "data:audio/wav;base64,"+base64.b64encode(Path("/content/ref.wav").read_bytes()).decode()
rt = Path("/content/ref.txt").read_text()
arms = {
 "A_tough_irish": "In Dublin, the leaders of the new republic assembled to challenge the authority of the Crown. Pádraig Pearse and Seán MacDiarmada had proclaimed the provisional government in nineteen sixteen, but it was the First Dáil Éireann that solidified the republican mandate. Eamon de Valera was chosen as president, while Cathal Brugha took charge of the Ministry of Defence, supported by the volunteers of Cumann na mBan. When the offices of Taoiseach and Tánaiste were debated decades later, Sinn Féin insisted that true legitimacy had already been won.",
 "B_quote_plain": "‘I will not sign it,’ he said, his voice shaking. ‘Not while good men lie in the ground for the sake of what it betrays.’",
 "C_quote_sadness_slow": "<|emotion:sadness|><|prosody:speed_slow|>‘I will not sign it,’ he said, his voice shaking. ‘Not while good men lie in the ground for the sake of what it betrays.’",
 "D_quote_anger": "<|emotion:anger|>‘I will not sign it,’ he said, his voice shaking. ‘Not while good men lie in the ground for the sake of what it betrays.’",
}
res={}
for name,text in arms.items():
    t0=time.time()
    r=requests.post("http://127.0.0.1:8095/v1/audio/speech",json={"model":"bosonai/higgs-audio-v3-tts-4b","input":text,"response_format":"wav","ref_audio":ref,"ref_text":rt,"max_new_tokens":2048,"seed":42},timeout=900)
    if not r.ok: LOG(name,"HTTP",r.status_code,r.text[:300]); continue
    w,sr=sf.read(io.BytesIO(r.content),dtype="float32"); el=time.time()-t0; d=len(w)/sr
    rms=float(np.sqrt((w**2).mean())); md=float(np.abs(np.diff(w)).mean()); pk=float(np.abs(w).max())
    sf.write(OUT/f"{name}.wav",w,sr)
    res[name]=dict(dur=d,wall=el,rtf=el/d,rms=rms,mean_abs_diff=md,peak=pk)
    LOG(name,res[name])
json.dump(res,open(OUT/"results.json","w"),indent=1)
srv.terminate(); LOG("DONE")
