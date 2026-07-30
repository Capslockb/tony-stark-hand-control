# Optional Ollama Snapshot Classification

This dated contributor note describes the repository's optional Ollama-compatible snapshot classifier. It is historical context rather than a support or performance guarantee.

## Current boundary

`OllamaGestureRecognizer` accepts an operator-configured endpoint, model name, API secret, and fixed classification prompt. It JPEG-encodes a camera frame, submits an Ollama-format JSON request to the exact configured endpoint, and maps the response to the built-in gesture vocabulary.

The integration is not open-ended gesture recognition. It processes individual snapshots and does not provide temporal, two-hand, or safety-rated interpretation. The local MediaPipe path remains separate.

## Runtime behavior

The current implementation:

- performs network requests on a daemon worker thread;
- uses a bounded queue and drops stale work when newer input is available;
- applies a submission cooldown;
- uses a request timeout and a consecutive-failure circuit breaker;
- sends an authorization header when an API secret is configured;
- treats unrecognized responses as `none`.

Behavior, available models, latency, pricing, and provider compatibility depend on the configured service and must be checked against the exact current source and provider documentation.

## Security and privacy

Camera snapshots leave the device when a remote endpoint is configured. Do not enable remote processing for visual data that must remain local.

Never commit API secrets, access tokens, account-specific endpoints, or copied credential examples. Any credential that has appeared in repository history or another public surface must be treated as compromised, revoked through the provider, and replaced through an appropriate secret store. Replacement values must not be written to documentation, issues, pull requests, logs, fixtures, or source comments.

## Validation

A focused test should isolate network access and verify request structure, timeout behavior, queue replacement, response normalization, and circuit-breaker recovery without using real credentials or transmitting real camera frames.

Current source, exact-head tests, and provider documentation take precedence over this historical note.