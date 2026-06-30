"""
KISTI-KONI/KONI-Llama3.1-8B-Instruct-20241024 을 RBLN-CA22 × 4 (TP=4)로 컴파일.
- rbln-model-zoo 공식 검증된 한국어 Llama-3.1 fine-tune (UTF-8 byte-fallback drift 회피)
- Llama-3.1 호환 architecture, optimum-rbln LlamaForCausalLM로 처리

Run on npu-node-1 venv:
  /usr/bin/python3.10 ~/compile-koni-tp4.py 2>&1 | tee ~/compile-koni.log

Output: ~/rbln-KONI-Llama3.1-8B-Instruct-tp4-bs1-s8192/
"""
import os
from optimum.rbln import RBLNAutoModelForCausalLM
from transformers import AutoTokenizer

MODEL_ID = "KISTI-KONI/KONI-Llama3.1-8B-Instruct-20241024"
OUTPUT   = os.path.expanduser("~/rbln-KONI-Llama3.1-8B-Instruct-tp4-bs1-s8192")

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
)
model.save_pretrained(OUTPUT)

tok = AutoTokenizer.from_pretrained(MODEL_ID)
tok.save_pretrained(OUTPUT)
print(f"[+] DONE → {OUTPUT}")
