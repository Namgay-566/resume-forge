"""All AI calls go through this package (see CLAUDE.md).

- `base.AIProvider`: the one interface a vendor implements (`providers/`), chosen by AI_PROVIDER.
- `client.generate_structured(prompt, response_model)`: requires JSON, validates it with
  Pydantic, retries once with the validation error, then raises AIResponseValidationError.
  Every call is logged with token usage and latency (logger "app.ai").
- `prompts/`: every prompt template, one `.j2` file each.
- `rate_limit.ai_rate_limit`: per-user limit for endpoints that call the AI.
"""
