import json

results_file = "outputs/evals/swe-grep--openai--gpt-4.1-mini/5cdc3f05/results.jsonl"

with open(results_file) as f:
    data = json.loads(f.readline())

print("Reward:", data.get("reward"))
print("correct_answer:", data.get("correct_answer_reward_func"))
print("correct_file_paths:", data.get("correct_file_paths_reward_func"))
print("parallel_tool_calls:", data.get("parallel_tool_calls_reward_func"))
print("stop_condition:", data.get("stop_condition"))
print("is_completed:", data.get("is_completed"))
print("num_turns:", data.get("num_turns"))

# Check completion - is there a final text answer?
completion = data.get("completion", [])
print(f"\nCompletion msgs: {len(completion)}")
for i, msg in enumerate(completion):
    if isinstance(msg, dict):
        role = msg.get("role", "")
        has_tc = "tool_calls" in msg and msg["tool_calls"]
        content = msg.get("content", "")
        content_preview = str(content)[:100] if content else "(empty)"
        if role == "assistant" and not has_tc:
            print(f"  [{i}] FINAL ANSWER role={role}: {content_preview}")
        elif role == "assistant":
            print(f"  [{i}] role={role} tool_call=True")
        elif role == "tool":
            print(f"  [{i}] role=tool")
