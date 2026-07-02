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
STORE = os.environ.get("MODEL_STORE", os.path.expanduser("~"))  # 공유 모델 스토어 마운트 경로
os.environ.setdefault("HF_HOME", os.path.join(STORE, "hub"))     # HF 다운로드도 스토어 hub 캐시로
OUTPUT_DIR = os.environ.get("OUTPUT", os.path.join(STORE, "compiled", MODEL_ID.replace("/", "--"), "rbln", "rbln-ca22-tp4-s8192"))
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
