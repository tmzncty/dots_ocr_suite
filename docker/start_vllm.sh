#!/bin/bash
set -ex

# 接收参数：物理卡号 (0 或 1)
TARGET_PHYSICAL_ID=$1
# 接收环境变量端口，默认 8000
PORT=${VLLM_PORT:-8000}

echo "--- vLLM Launcher ---"
echo "Target Physical GPU: $TARGET_PHYSICAL_ID"
echo "Target Port: $PORT"

# === 1. 智能显卡选择逻辑 (核心修复) ===
# 获取当前容器可见的 GPU 数量
GPU_COUNT=$(python3 -c "import torch; print(torch.cuda.device_count())")
echo "Visible GPUs in container: $GPU_COUNT"

if [ "$GPU_COUNT" -eq "1" ]; then
    echo "Isolation Mode: Active. (Container only sees 1 GPU)"
    # 隔离生效时，容器内唯一的显卡索引永远是 0
    export CUDA_VISIBLE_DEVICES=0
elif [ "$GPU_COUNT" -gt "1" ]; then
    echo "Isolation Mode: Inactive. (Container sees multiple GPUs)"
    # 隔离失效时，我们需要手动指定使用哪张物理卡
    export CUDA_VISIBLE_DEVICES=$TARGET_PHYSICAL_ID
else
    echo "Error: No GPUs found!"
    exit 1
fi

echo "Selected CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"

# === 2. Patch vLLM (保持不变) ===
if ! grep -q "modeling_dots_ocr_vllm" $(which vllm) 2>/dev/null; then
    echo 'Patching vLLM entrypoint...'
    sed -i '/^from vllm\.entrypoints\.cli\.main import main/a from DotsOCR import modeling_dots_ocr_vllm' $(which vllm)
    echo 'Patch applied.'
fi

# === 3. 优化环境 ===
export NCCL_P2P_DISABLE=1
export CUDA_LAUNCH_BLOCKING=1

# === 4. 启动 vLLM ===
# 注意：tensor-parallel-size 始终为 1，因为我们已经通过 CUDA_VISIBLE_DEVICES 锁定了一张卡
exec vllm serve /workspace/weights/DotsOCR \
    --host 0.0.0.0 \
    --port "$PORT" \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.7 \
    --max-num-batched-tokens 2048 \
    --chat-template-content-format string \
    --served-model-name dots-ocr \
    --trust-remote-code \
    --enforce-eager \
    --disable-log-stats