# OllamaCloud Integration for Gesture Recognition

## Overview
The Tony Stark hand control system can optionally integrate with OllamaCloud for advanced gesture recognition using vision‑language models (VLMs) like `gemma4:31b-cloud`. This enables more natural and context‑aware gesture interpretation beyond simple distance‑based heuristics.

## How It Works
1. **Frame Capture**: The system captures the current video frame from the first successfully opened camera.
2. **Encoding**: The frame is JPEG‑compressed and base64‑encoded.
3. **API Call**: A POST request is sent to the OllamaCloud endpoint with:
   - The model name (e.g., `gemma4:31b-cloud`)
   - A prompt asking for gesture classification
   - The base64‑encoded image
   - Authorization bearer token
4. **Response Parsing**: The model returns a text response, which is parsed to extract a gesture label.
5. **Execution**: The recognized gesture is executed (overriding computer‑vision gestures for that frame).

## Gesture Classes
The system prompts the model to choose from these discrete classes:
- `left_click` – thumb and index finger close together
- `right_click` – thumb and middle finger close together
- `scroll_up` – thumb and ring finger close together
- `scroll_down` – thumb and pinky finger close together
- `swipe_left` – rapid leftward motion of index finger
- `swipe_right` – rapid rightward motion of index finger
- `swipe_up` – rapid upward motion of index finger
- `swipe_down` – rapid downward motion of index finger
- `move_cursor` – index finger moving (default state)
- `engage` – open palm (deliberate engagement)
- `disengage` – closed fist or hand out of frame
- `none` – no clear gesture detected

## Configuration
To enable OllamaCloud gesture recognition, set these variables in `tony_stark_hud_control.py` (or via the **Ollama tab** in the GUI):
```python
ollama_endpoint = "https://ollama.com/api/generate"  # or your cloud endpoint
ollama_model = "gemma4:31b-cloud"                    # or another VLM
ollama_api_key = "your-api-key-here"                 # provided by user
```

### Notes on the Provided Credentials
During this session, the user provided:
- API key: <REDACTED — revoked; obtain a fresh key from the Ollama dashboard>
- Suggested model: `gemma4:31b-cloud`
- Inferred endpoint: `https://ollama.com/api/generate` (verified reachable)

## Implementation Details
The `OllamaGestureRecognizer` class handles:
- **Threaded API calls**: To avoid blocking the main processing loop, requests run in a background daemon thread.
- **Request queuing**: Only the most recent frame is processed (oldest dropped if queue full).
- **Cooldown limiting**: By default, one request every 0.5 seconds to prevent excessive API usage.
- **Response normalization**: Various model outputs are mapped to the standard gesture classes.
- **Fallback behavior**: If the API call fails or returns an unrecognized gesture, the system ignores it and continues with computer‑vision gestures.
- **Throttled error printing**: The worker's exception handler is gated by a 30-second timestamp (`_last_ollama_err_print`) so a network outage prints one line per 30s, not one per frame.

## Performance Considerations
- **Latency**: Each API call adds ~200‑500ms latency (depends on network and model size).
- **Frequency**: Limited by cooldown + main-loop frame-skip (default 6 ticks ≈ 200ms at 30fps). Not suitable for real‑time tracking but good for discrete gesture confirmation.
- **Bandwidth**: Each frame sends ~50‑100KB JPEG (adjustable via compression quality if needed).
- **Reliability**: Designed to gracefully degrade to computer‑vision modes if OllamaCloud is unreachable.

## Troubleshooting
### Common Issues
1. **"Could not resolve host"**
   - Solution: Verify the endpoint URL (use `ollama.com`, not `cloud.ollama.com` unless specifically instructed).
   - Test with: `curl -s https://ollama.com/api/tags`

2. **Unauthorized (401) errors**
   - Solution: Check API key format; ensure it's a valid bearer token.
   - The token should be a string; no additional formatting needed beyond `Bearer <token>`.

3. **Model not found**
   - Solution: Verify the model exists in your OllamaCloud account.
   - List available models: `curl -s -H "Authorization: Bearer <token>" https://ollama.com/api/tags`

4. **Timeouts** (`HTTPSConnectionPool: Read timed out`)
   - Solution: Increase the timeout in the `requests.post` call (currently 8 seconds).
   - If timeouts are persistent, the network cannot reach ollama.com — see PITFALL below for an offline alternative.

## Testing the Connection
You can verify your OllamaCloud setup with this Python snippet:
```python
import requests

endpoint = "https://ollama.com/api/generate"
api_key = "your-api-key"
model = "gemma4:31b-cloud"

resp = requests.post(
    endpoint,
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": model,
        "prompt": "Say hello in one word.",
        "stream": False
    }
)
print(resp.json())
```

## Privacy Note
Frames are sent to a third‑party service (OllamaCloud). Do not enable this feature if processing sensitive visual data locally is required.

## PITFALL — local llama.cpp on RTX 5060 (Blackwell, sm_120) is broken as of 2026‑06

This skill's user attempted to set up **local offline LLM gesture recognition** using llama.cpp on an RTX 5060 (Blackwell, compute capability 12.0). The end result was a hard blocker: **all well-known GGUFs produce identical garbled Chinese output `溢价个人观点...` on this GPU, regardless of model, build, or prompt**.

What was tried (and failed):
| Model | Quant | llama.cpp build | CUDA | Result |
|---|---|---|---|---|
| Qwen2.5-VL-3B-Instruct (ggml-org) | Q4_K_M | b9505 | 13.3 | garbage |
| Qwen2.5-VL-3B-Instruct (unsloth) | Q4_K_M | b9505 | 13.3 | garbage |
| Qwen2.5-3B-Instruct (bartowski) | Q4_K_M | b9505 | 13.3 | garbage |
| Qwen2.5-3B-Instruct (bartowski) | Q4_K_M | b9505 | 12.4 | garbage |
| Llama-3.2-3B-Instruct (bartowski) | Q4_K_M | b9505 | 12.4 | garbage |

Tested with `--jinja` (default), with explicit `--chat-template-file qwen25_template.jinja`, with `temperature=0.1`, with a system prompt, with raw `<|im_start|>`-formatted completion, with and without `mmproj` (vision encoder) loaded. The pattern is **identical across all 5 configurations** — `溢价个人观点` (= "personal opinion premium") repeats forever, regardless of input. This is a **sampler/logits bug in llama.cpp b9505 with Blackwell sm_120**, not a tokenizer or template issue.

Other findings from the same attempt:
- `pip install llama-cpp-python` with `CMAKE_ARGS="-DGGML_CUDA=on"` **fails in this environment** because there is no CUDA toolkit (only the driver; `nvcc` is not installed). CMake bails during configuration. Use the prebuilt Windows binaries from `https://github.com/ggerganov/llama.cpp/releases` instead — these ship their own CUDA runtime DLLs.
- The prebuilt Windows CUDA binaries (both cu12.4 and cu13.3) work fine for *loading* the model and serving on port 8080; the bug is in the inference step (sampler outputs garbage).
- `onnxruntime-gpu` works perfectly and exposes the CUDA provider. PyTorch with `cu130` works perfectly on sm_120. The bug is **specific to llama.cpp**, not the CUDA stack.

**Recommendation for a future session:** if the user asks for offline LLM gesture recognition on a Blackwell GPU, **do not try llama.cpp**. The paths that actually work:
1. Use a non-LLM gesture classifier (deterministic MediaPipe landmark geometry — finger distances, palm orientation — runs in <5ms with zero LLM dependency and is more reliable than any VLM).
2. Use a remote Ollama endpoint (e.g., `ollama.com`) — works on every model, just costs API credits.
3. If they insist on local: wait for a llama.cpp release that explicitly supports sm_120. At the time of writing (2026‑06), b9505 is broken on RTX 5060. Check `https://github.com/ggerganov/llama.cpp/releases` for any post-b9505 release notes mentioning Blackwell.

**Do not re-attempt** with another model or quantization level — the bug is in the sampler, not the model file. The 5 attempts above already span Qwen-VL, Qwen-3B, and Llama-3.2 from three different quantizers, with and without vision encoder. The user has already paid ~6 GB of disk and 30+ minutes to confirm this.

If llama.cpp is updated and you want to retry, the model files and llama.cpp builds have been **deleted from disk** by the user (`rm -rf models/ llama_cuda/ llama_cuda_12/ llama_cuda_9509/`), reclaiming ~7 GB. A future attempt will need to redownload both the GGUF and a llama.cpp release newer than b9505.

## Future Improvements
- Local VLM inference (if a compatible llama.cpp release supports sm_120) — see PITFALL above
- Rule-based gesture classifier as the primary path (no LLM dependency, deterministic, <5ms)
- Gesture smoothing across multiple frames to reduce jitter in VLM output
- Confidence scoring to blend VLM and computer‑vision gestures
- Custom prompt engineering for domain‑specific gestures
