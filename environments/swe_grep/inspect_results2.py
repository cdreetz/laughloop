import json

results_file = "outputs/evals/swe-grep--openai--gpt-5.4/39eadf84/results.jsonl"

with open(results_file) as f:
    data = json.loads(f.readline())

# Check if trajectory exists in the result
print("Top-level keys:", sorted(data.keys()))

# Check task for trajectory
task = data.get("task", {})
if isinstance(task, dict):
    print("Task keys:", sorted(task.keys()))

# Look for any key containing 'traj'
for k in data.keys():
    if "traj" in k.lower():
        print(f"Found trajectory key: {k}")
        val = data[k]
        print(f"  Type: {type(val)}, len: {len(val) if hasattr(val, '__len__') else 'N/A'}")

# The completion field - what format is it?
completion = data.get("completion", "")
print(f"\nCompletion type: {type(completion)}")
if isinstance(completion, list):
    print(f"Completion length: {len(completion)}")
    for i, msg in enumerate(completion[:3]):
        if isinstance(msg, dict):
            print(f"  [{i}] role={msg.get('role')}, has tool_calls={bool(msg.get('tool_calls'))}")
            if msg.get("tool_calls"):
                print(f"       tool_calls: {str(msg['tool_calls'])[:200]}")
elif isinstance(completion, str):
    print(f"Completion (str, first 200): {completion[:200]}")

# Check prompt messages for tool call/response patterns
prompt = data.get("prompt", [])
print(f"\nPrompt messages: {len(prompt)}")
for i, msg in enumerate(prompt):
    role = msg.get("role", "")
    has_tc = bool(msg.get("tool_calls"))
    tc_id = msg.get("tool_call_id")
    content_preview = str(msg.get("content", ""))[:100]
    print(f"  [{i}] role={role}, tool_calls={has_tc}, tool_call_id={tc_id}, content={content_preview}")
