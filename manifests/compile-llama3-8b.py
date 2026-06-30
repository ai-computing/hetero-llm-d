"""
Compile meta-llama/Meta-Llama-3-8B-Instruct for RBLN-CA22 x4 (TP=4).
Run on npu-node-1 inside ~/vllm_test/venv (vllm_rbln 0.10.2.post1).

  source ~/vllm_test/venv/bin/activate
  python ~/llm-d-setup/manifests/compile-llama3-8b.py 2>&1 | tee ~/compile-llama3-8b.log

Output: ~/rbln-Meta-Llama-3-8B-Instruct/
"""
import os
from optimum.rbln import RBLNAutoModelForCausalLM
from transformers import AutoTokenizer

MODEL_ID = "meta-llama/Meta-Llama-3-8B-Instruct"
OUTPUT_DIR = os.path.expanduser("~/rbln-Meta-Llama-3-8B-Instruct")

os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"[+] compiling {MODEL_ID} for RBLN (TP=4, batch=1, max_seq_len=8192)")
model = RBLNAutoModelForCausalLM.from_pretrained(
    model_id=MODEL_ID,
    export=True,
    rbln_batch_size=1,
    rbln_max_seq_len=8192,
    rbln_tensor_parallel_size=4,
)
model.save_pretrained(OUTPUT_DIR)

print("[+] saving tokenizer")
tok = AutoTokenizer.from_pretrained(MODEL_ID)
tok.save_pretrained(OUTPUT_DIR)

print(f"[+] DONE → {OUTPUT_DIR}")
