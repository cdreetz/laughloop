import json
import sys

results_file = "outputs/evals/swe-grep--openai--gpt-5.4/39eadf84/results.jsonl"

with open(results_file) as f:
    data = json.loads(f.readline())

print("=== PROMPT ===")
prompt = data.get("prompt", [])
if isinstance(prompt, list):
    for msg in prompt:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, str):
            print(f"  [{role}]: {content[:300]}")
        else:
            print(f"  [{role}]: {str(content)[:300]}")

print("\n=== COMPLETION (last 500 chars) ===")
completion = data.get("completion", "")
print(str(completion)[-500:])

print("\n=== ANSWER (first 500 chars) ===")
answer = data.get("answer", "")
print(str(answer)[:500])

print("\n=== TASK ===")
task = data.get("task", {})
if isinstance(task, dict):
    print("Task keys:", list(task.keys()))
    for k, v in task.items():
        print(f"  {k}: {str(v)[:200]}")

print("\n=== REWARD BREAKDOWN ===")
for key in ["parallel_tool_calls_reward_func", "correct_answer_reward_func", "correct_file_paths_reward_func"]:
    print(f"  {key}: {data.get(key)}")

print("\n=== TOOL CALL CHECK ===")
print(f"  total_tool_calls: {data.get('total_tool_calls')}")
print(f"  num_turns: {data.get('num_turns')}")
print(f"  is_completed: {data.get('is_completed')}")
print(f"  stop_condition: {data.get('stop_condition')}")
print(f"  error: {data.get('error')}")
