"""
LGAI-EXAONE/EXAONE-4.0-1.2B 를 RBLN-CA22 × 4 로 컴파일 시도.
- optimum-rbln의 RBLNExaoneForCausalLM (3.5용) 클래스가 4.0과 호환되는지 검증
- 1.2B 작은 모델이라 컴파일도 빠름 (~10-20분)

Run on npu-node-1 venv:
  /usr/bin/python3.10 ~/compile-exaone4-1b2.py 2>&1 | tee ~/compile-exaone4.log

Output: ~/rbln-EXAONE-4.0-1.2B-tp4-bs1-s8192/
"""
import os
from optimum.rbln import RBLNAutoModelForCausalLM
from transformers import AutoTokenizer

MODEL_ID = "LGAI-EXAONE/EXAONE-4.0-1.2B"
OUTPUT   = os.path.expanduser("~/rbln-EXAONE-4.0-1.2B-tp4-bs1-s8192")

os.makedirs(OUTPUT, exist_ok=True)
print(f"[+] compiling {MODEL_ID} for RBLN-CA22 (TP=4, batch=1, max_seq=8192)")
model = RBLNAutoModelForCausalLM.from_pretrained(
    model_id=MODEL_ID,
    export=True,
    rbln_batch_size=1,
    rbln_max_seq_len=8192,
    rbln_tensor_parallel_size=4,
    rbln_create_runtimes=False,
    rbln_npu="RBLN-CA22",
    trust_remote_code=True,
)
model.save_pretrained(OUTPUT)

tok = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
tok.save_pretrained(OUTPUT)
print(f"[+] DONE → {OUTPUT}")
