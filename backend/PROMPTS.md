# Su-AI LLMOps & Prompt Versioning Guide

This document outlines how the Large Language Model (LLM) prompts are managed, versioned, and evaluated using the internal LLM-as-a-Judge system.

## 1. Prompt File Structure
All system prompts used by the application are stored externally as plain text files in the `backend/app/prompts/` directory.

- `narrator_v1.txt`: The system prompt for the Narrator LLM, which translates rule engine anomalies into readable technical actions.
- `judge_v1.txt`: The system prompt for the Judge LLM, which evaluates the Narrator's output for hallucinations and regulation compliance.

## 2. Creating a New Prompt Version (A/B Testing)
To iterate and improve the LLM responses without breaking the system, follow this workflow:

1. **Create a new file:** Instead of editing `narrator_v1.txt`, create `narrator_v2.txt`.
2. **Update the code:** In `app/llm_service.py` (or `judge_service.py`), update the filename in `_get_narrator_prompt()` to point to `narrator_v2.txt`. Update the hardcoded `prompt_version = "v2"` metadata in `app/judge_service.py`.
3. **Deploy:** Deploy the application. The system will start using `v2` and tagging all new evaluations in the database with `prompt_version="v2"`.

## 3. The LLMOps Dashboard
The backend provides an admin-only endpoint to evaluate prompt performance.

**Endpoint:** `GET /admin/llmops/dashboard`

This endpoint returns a JSON payload containing:
- `overall_avg_score`: The global average score of all LLM outputs.
- `by_prompt_version`: A breakdown of average scores per prompt version. Use this to determine if `v2` actually scores higher than `v1`.
- `by_provider`: A breakdown of scores by LLM provider (e.g., `openai` vs `ollama`). This helps you decide if the cheaper edge model is performing adequately compared to the cloud model.
- `lowest_scores`: The top 5 lowest-scoring recommendations. Human operators should manually review these to understand *why* the LLM failed and use these failure modes to write the next prompt version.

## 4. Promoting a Version
If the `/admin/llmops/dashboard` shows that `v2` has a significantly higher `avg_score` and fewer instances in `lowest_scores` than `v1`, you can consider `v2` the new standard. Leave the old versions in the repository as a historical record of prompt engineering efforts.
