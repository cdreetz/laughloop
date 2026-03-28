# laughloop-reward

### Overview
- **Environment ID**: `laughloop-reward`
- **Short description**: RL environment for training funnier AI responses using human humor feedback from the LaughLoop chat app.
- **Tags**: humor, single-turn, rlhf, feedback, train

### Task
- **Type**: single-turn
- **Rubric overview**: Human feedback reward (primary) + optional judge quality score

### Environment Arguments
| Arg | Type | Default | Description |
| --- | ---- | ------- | ----------- |
| `data_dir` | str | `./data/batches` | Directory containing exported JSONL batches |
| `data_file` | str | `latest.jsonl` | Specific batch file to load |
| `judge_model` | str | `gpt-4.1-mini` | Model for humor quality judging |
| `funny_reward` | float | `1.0` | Reward for human-approved funny responses |
| `humor_weight` | float | `0.8` | Weight for human feedback component |
| `judge_weight` | float | `0.2` | Weight for judge quality component |

### Metrics
| Metric | Meaning |
| ------ | ------- |
| `human_feedback_reward` | Average human humor feedback score |
| `judge_humor_score` | Average judge-rated humor quality |
