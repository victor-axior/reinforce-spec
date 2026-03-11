# Glossary

Terminology and definitions used throughout ReinforceSpec documentation.

---

## A

### API Key
A secret token used to authenticate requests to the ReinforceSpec API. Keep secure and rotate regularly.

### Async
Asynchronous programming pattern using Python's `asyncio`. ReinforceSpec's Python SDK uses async/await for non-blocking I/O.

---

## C

### Candidate
A specification submitted for evaluation. Each API call requires at least 2 candidates.

### Circuit Breaker
A pattern that prevents cascading failures by temporarily stopping requests to a failing service after multiple errors.

### Composite Score
The weighted aggregate of all dimension scores, ranging from 0.0 to 1.0. Used to rank candidates.

---

## D

### Dimension
One of 12 evaluation criteria used to score specifications (e.g., security, scalability, compliance). Each dimension receives a score from 0.0 to 1.0.

### Dimension Weight
The relative importance assigned to each dimension when calculating the composite score. Weights sum to 1.0.

---

## E

### Ensemble
A collection of multiple LLM judges that score specifications independently. Scores are aggregated for robustness.

### Evaluation
The process of scoring candidate specifications and selecting the best one.

---

## F

### Feedback
User-provided rating of a selection, used to train the RL model. Submitted via the feedback API with a reward value.

### Feedback Loop
The continuous cycle of selections, user feedback, model training, and improved selections.

---

## H

### Hybrid Selection
The default selection method combining LLM scoring (60%) with RL policy predictions (40%).

---

## I

### Idempotency
The property that repeated identical requests produce the same result. Enabled via the `Idempotency-Key` header.

### Idempotency Key
A unique identifier included in requests to enable safe retries. Keys expire after 24 hours.

---

## J

### Judge
An LLM model that evaluates specifications. Multiple judges form an ensemble for more reliable scoring.

---

## L

### Latency
The time taken to process a request, measured in milliseconds. Includes scoring and selection time.

---

## M

### Multi-Judge
The scoring approach using multiple LLMs (Claude, GPT-4, Gemini) to reduce bias and improve accuracy.

---

## O

### OpenRouter
The LLM routing service used to access multiple model providers through a unified API.

---

## P

### Policy
The trained RL model that learns from feedback to improve selection decisions.

### Policy Version
An identifier for a specific trained policy (e.g., `v001`). Updated after each training run.

---

## R

### Rate Limit
The maximum number of API requests allowed per time period. Varies by subscription tier.

### Replay Buffer
Storage for experiences (selections + feedback) used to train the RL model.

### Request ID
A unique identifier assigned to each API request for tracking and debugging.

### Reward
A numeric feedback signal from -1.0 (terrible) to 1.0 (perfect) indicating selection quality.

### RL (Reinforcement Learning)
Machine learning approach where the model learns from feedback to improve decisions over time.

---

## S

### Scoring
The process of evaluating a specification across 12 dimensions using LLM judges.

### Selection
The chosen specification from a set of candidates, determined by scoring and/or RL policy.

### Selection Method
The algorithm used to choose the best candidate: `scoring_only`, `hybrid`, or `rl_only`.

### Spec / Specification
A document describing system requirements, API design, architecture, or other technical specifications.

### Spec Type
A classification hint for specifications: `api`, `architecture`, `srs`, `prd`, etc.

---

## T

### Training
The process of updating the RL policy using collected feedback from the replay buffer.

---

## W

### Weight Preset
Predefined dimension weight configurations for common use cases: `enterprise`, `startup`, `platform`, `regulated`.

---

## See Also

- [Concepts Overview](../concepts/index.md)
- [Scoring Dimensions](../concepts/scoring-dimensions.md)
- [Selection Methods](../concepts/selection-methods.md)
