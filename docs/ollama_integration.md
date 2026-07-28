# Ollama Integration (optional)

The Ollama tab adds an optional **second layer** of gesture recognition on top of the local MediaPipe-based detector. It uses a vision-language model (VLM) — either a cloud service or a local server — to look at a snapshot of the camera feed and classify the gesture.

**This feature is OFF by default.** If you don't enable it, the app uses the local MediaPipe-only gesture detection described in [gestures.md](gestures.md), which provides the built-in gesture vocabulary without sending camera snapshots to an inference endpoint.

> **Current runtime caveat:** on current `main`, [Issue #16](https://github.com/Capslockb/tony-stark-hand-control/issues/16) prevents the processing loop from rescheduling after its first iteration. Repeated MediaPipe gesture processing and repeated Ollama snapshot submission therefore do not continue after **Start**. The flow below describes the intended behavior once that runtime defect is fixed.

> **Security notice:** current `main` contains a publicly exposed credential-like value in the Ollama API-key field. Treat it as invalid, do not reuse it, and replace or clear it before enabling the feature. Revocation/rotation and the source fix are tracked in [Issue #5](https://github.com/Capslockb/tony-stark-hand-control/issues/5). This documentation warning does not resolve the embedded-credential defect.

## When to use Ollama

Use Ollama if you want to:

- **Experiment with snapshot-based classification** for the app's existing fixed gesture vocabulary
- **Compare a VLM result with the local detector** when evaluating the existing gesture labels

Don't use Ollama if:

- You're happy with the built-in gestures
- You want to add new action names without changing the source: responses outside `GESTURE_KEYS` are converted to `none`
- You need sign-language recognition or other temporal/two-hand gestures: the current path classifies independent snapshots and does not implement sequence recognition
- You're on a slow network or no network at all
- You need the lowest possible latency (Ollama adds 1-8 seconds per inference)

## How it works

1. Every Nth frame (default 6, configurable), a copy of the camera feed is submitted to the Ollama endpoint with a prompt like:
   ```
   What hand gesture is being shown? Choose from: left_click, right_click, scroll_up, scroll_down, swipe_left, swipe_right, swipe_up, swipe_down, move_cursor, engage, disengage, none. Respond with only the gesture name.
   ```
2. The model returns one of the recognized gesture names.
3. The local gesture handler fires the corresponding action.
4. A circuit breaker trips after 3 consecutive failures to avoid burning the queue.

## Cloud endpoint (ollama.com)

The current source default is the complete generation endpoint `https://ollama.com/api/generate`. To use it:

1. Get your own API key from https://ollama.com/settings/keys.
2. In the **Ollama** tab of the app:
   - Check **Enable Ollama**.
   - Set Endpoint to `https://ollama.com/api/generate`.
   - Set Model to a vision model that ollama.com supports (e.g. `qwen2.5vl:3b`).
   - Clear any prefilled API-key value and paste only your own newly issued key.
   - Set Query cooldown. The current default is 0.5 seconds and the slider range is 0.1-3.0 seconds.
   - Customize the prompt if you want (defaults to a strict set of gesture names).
   - Click **Save (rebuild Ollama worker)**.

The app considers an eligible frame for submission according to both the every-sixth-frame gate and the configured cooldown. The worker uses a one-item queue, so stale frames may be dropped while a request is in flight; the cooldown is not a promise that the provider will receive one frame at every interval.

**Privacy:** a cloud endpoint receives camera-frame snapshots and the configured prompt. Provider retention and processing policies can change; review the provider's current policy before enabling cloud inference. Do not describe frames as unconditionally unstored unless that claim has been verified against the current policy and service configuration.

## Local endpoint (llama.cpp server)

For privacy and speed, you can run a local LLM server and point the app at it. The most tested setup is **llama.cpp** with the **Qwen2.5-VL-3B** model on a CUDA-capable GPU.

### Known issue: llama.cpp on RTX 5060 Blackwell

**As of June 2026, llama.cpp b9505+ is broken on the RTX 5060 Blackwell (sm_120).** Symptoms:
- Model loads
- Server starts
- First inference returns garbled Chinese or nonsense
- Subsequent inferences work correctly (after the model is "warm")

**Workarounds**:
1. Use llama.cpp build b9505 or earlier on a different GPU
2. Use a different inference server (vLLM, ollama, exllamav2)
3. Wait for an upstream fix

If you're on a different GPU (RTX 30xx, 40xx), llama.cpp works correctly.

### Starting the local server

```bash
# Download the model (one time)
# Qwen2.5-VL-3B is a true VLM that knows gestures
huggingface-cli download Qwen/Qwen2.5-VL-3B-Instruct-GGUF \
    qwen2.5-vl-3b-instruct-q4_k_m.gguf \
    --local-dir models/

# Start the server
./llama_cuda/llama-server.exe \
    -m models/qwen2.5-vl-3b-instruct-q4_k_m.gguf \
    --mmproj models/qwen2.5-vl-3b-mmproj.gguf \
    -ngl 99 \
    --port 8080 \
    --host 127.0.0.1 \
    --jinja \
    --reasoning-format none
```

Performance on RTX 5060: ~14 tok/sec for image+text generation, ~2.2 seconds per 30-token response. For 1-token gesture labels: ~250 ms per inference.

### Wiring the app to the local server

In the **Ollama** tab:
- Set Endpoint to `http://127.0.0.1:8080`
- Set Model to the same name you used with `-m` (or any string — the server doesn't check)
- The current GUI requires a non-empty API-key field. If your local adapter ignores `Authorization`, enter a non-secret placeholder such as `local-only`; do not reuse a real credential.
- Click Save

**Note**: the current `OllamaGestureRecognizer` in the app uses the **Ollama API format** (`/api/generate` with multipart image). A local llama-server uses the **OpenAI-compatible format** (`/v1/chat/completions` with image_url in messages). The two are not directly compatible. To use the local server, you'll need a small adapter — see the "Adapting to OpenAI format" section below.

## Ollama API format vs OpenAI format

Ollama cloud uses a custom API:

```
POST https://ollama.com/api/generate
{
    "model": "qwen2.5vl:3b",
    "prompt": "What gesture?",
    "images": ["<base64 jpeg>"],
    "stream": false
}
```

llama-server (and most other local servers) use the OpenAI-compatible format:

```
POST http://127.0.0.1:8080/v1/chat/completions
{
    "model": "qwen2.5-vl-3b-q4km",
    "messages": [
        {"role": "user", "content": [
            {"type": "text", "text": "What gesture?"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
        ]}
    ]
}
```

## Adapting to OpenAI format

If you want to use a local llama-server (or any OpenAI-compatible endpoint), you have two options:

1. **Use a local proxy** that translates Ollama API calls to OpenAI format. Tools like [`ollama-openai-proxy`](https://github.com/imranzxc/ollama-openai-proxy) do this.
2. **Patch `OllamaGestureRecognizer`**. The class is well-isolated — you can subclass it and override `submit_frame` and `_worker` to use the OpenAI format. The base64 encoding and frame submission logic is reusable.

## Custom prompts

The default prompt is:

```
What hand gesture is being shown? Choose from: left_click, right_click, scroll_up, scroll_down, swipe_left, swipe_right, swipe_up, swipe_down, move_cursor, engage, disengage, none. Respond with only the gesture name.
```

You can edit this in the Ollama tab, but the runtime still filters the response through the fixed `GESTURE_KEYS` list. A response that does not contain one of those labels becomes `none`. Supporting a genuinely new gesture name therefore requires a reviewed source change to the vocabulary and its action mapping; changing the prompt alone is not enough.

## Performance

- **Cloud (ollama.com)**: 5-8 seconds per inference in the recorded test environment. The 0.5-second default cooldown does not make a multi-second cloud request real-time; the single-item queue drops stale submissions while work is pending.
- **Local (llama.cpp)**: 200-400 ms per inference. Fast enough for an every-sixth-frame submission gate in some environments, subject to the configured cooldown.
- **Ollama cloud circuit breaker**: trips after 3 failures, stays tripped for 30 seconds. Prevents burning the queue during outages.

## Disabling

To turn off Ollama completely:
1. Open the **Ollama** tab
2. **Uncheck** "Enable Ollama gesture recognition"
3. Click Save

The Ollama worker thread will exit cleanly and the local MediaPipe detector remains selected. On current `main`, recurring local processing remains blocked by [Issue #16](https://github.com/Capslockb/tony-stark-hand-control/issues/16).

## See also

- [Architecture: OllamaGestureRecognizer](architecture.md#ollamagesturerecognizer)
- [Gestures](gestures.md) — the built-in gesture set
