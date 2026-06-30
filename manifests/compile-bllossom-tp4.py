"""
Bllossom Korean-fine-tuned Llama-3-8B 모델을 RBLN-CA22 × 4 (TP=4)로 컴파일.
- 한국어 token 깨짐 회피 후보 #1
- HF: MLP-KTLim/llama-3-Korean-Bllossom-8B (공개, non-gated)

Run on etri-001 venv:
  /usr/bin/python3.10 ~/compile-bllossom-tp4.py 2>&1 | tee ~/compile-bllossom.log

Output: ~/rbln-Bllossom-Llama-3-Korean-8B-tp4-bs1-s8192/
"""
import os
from optimum.rbln import RBLNAutoModelForCausalLM
from transformers import AutoTokenizer

MODEL_ID = "MLP-KTLim/llama-3-Korean-Bllossom-8B"
OUTPUT   = os.path.expanduser("~/rbln-Bllossom-Llama-3-Korean-8B-tp4-bs1-s8192")

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
