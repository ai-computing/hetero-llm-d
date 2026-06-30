"""
Compile meta-llama/Llama-3.1-8B-Instruct for RBLN-CA22 x4 (TP=4).
Run on npu-node-1 inside system python or venv with vllm-rbln 0.10.2 stack.

  /usr/bin/python3.10 ~/compile-llama31-8b-tp4.py 2>&1 | tee ~/compile-llama31.log

HF cache has weights already at ~/.cache/huggingface/hub/models--meta-llama--Llama-3.1-8B-Instruct
so this should not re-download.

Output: ~/rbln-Llama-3.1-8B-Instruct-tp4-bs1-s8192/
"""
import os
from optimum.rbln import RBLNAutoModelForCausalLM
from transformers import AutoTokenizer

MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"
OUTPUT_DIR = os.path.expanduser("~/rbln-Llama-3.1-8B-Instruct-tp4-bs1-s8192")

os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f"[+] compiling {MODEL_ID} for RBLN (TP=4, batch=1, max_seq_len=8192)")
model = RBLNAutoModelForCausalLM.from_pretrained(
    model_id=MODEL_ID,
    export=True,
    rbln_batch_size=1,
    rbln_max_seq_len=8192,
    rbln_tensor_parallel_size=4,
    rbln_create_runtimes=False,    # NPU runtime 생성 X
    rbln_npu="RBLN-CA22",          # NPU 실물 없이 컴파일만
)
model.save_pretrained(OUTPUT_DIR)

print("[+] saving tokenizer")
tok = AutoTokenizer.from_pretrained(MODEL_ID)
tok.save_pretrained(OUTPUT_DIR)

print(f"[+] DONE → {OUTPUT_DIR}")
