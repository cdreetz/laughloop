import json

results_file = "outputs/evals/swe-grep--openai--gpt-5.4/39eadf84/results.jsonl"

with open(results_file) as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        data = json.loads(line)
        print(f"=== Example {i} ===")

        # Check what answer looks like
        answer = data.get("answer", "")
        print(f"Answer (first 200): {str(answer)[:200]}")

        # Check the file_path fields in task
        task = data.get("task", {})
        if isinstance(task, dict):
            print(f"Task file_path: {task.get('file_path', 'NOT PRESENT')}")
            print(f"Task file_path_2: {task.get('file_path_2', 'NOT PRESENT')}")

        # Check completion - does model actually reference file paths?
        completion = data.get("completion", [])
        if isinstance(completion, list):
            last_assistant = None
            for msg in completion:
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    last_assistant = msg
            if last_assistant:
                content = last_assistant.get("content", "")
                if isinstance(content, str):
                    print(f"Last assistant msg (last 300): {content[-300:]}")

        print()
