import asyncio
import os
import random
import subprocess
from pathlib import Path

import chatan


def setup_repo() -> Path:
    repo = Path("./vscode")
    if not repo.exists():
        subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/microsoft/vscode.git"],
            check=True,
        )
    return repo


def get_file_path() -> str:
    repo = setup_repo()
    files = list(repo.rglob("*.ts"))
    files = [
        f
        for f in files
        if "node_modules" not in str(f) and f.is_file() and f.stat().st_size < 30000
    ]
    if not files:
        raise RuntimeError("No TypeScript files found in repository")
    return str(random.choice(files))


def get_file_chunk(file_path: str) -> str:
    return Path(file_path).read_text(errors="ignore")[:12000]


GROUND_TRUTH_PROMPT = """
Pick something from this page to act as a 'ground truth' answer.
Only return the answer, do not respond with any other text or explanation.
The answer should be asked in a way that someone could search the codebase in order to find the related file and provide the answer.
It should not be so general that it makes it hard to answer but also not so general that it can be guessed correctly without having to look at the code.
You're job is to return the answer. Do not return a question.

The page:\n{file_chunk}

Now provide a 'ground truth' answer from the page.
"""


USER_QUERY_PROMPT = """
Given this page:\n{file_chunk}
And this ground truth: {ground_truth}
Play the role of a user who is asking a question, where the answer to the question is the provided ground truth.
Do not refer to the file.
Imagine the hypothetical user you are role playing is working in this project, they are not looking at this file, but they have a question in which it can be answered by someone else after they search through the codebase.
The downstream use case is potential user questions and the corresponding answers we can use to finetune an LLM to get better at search codebases with grep given different user questions.
Only respond with the question and no other text or explanation.
"""

CHECK_GROUND_TRUTH_PROMPT = """
Does this ground truth: {ground_truth}
Make sense for this user query: {user_query}

The user query will be given to a coding agent so it should represent a user query in which the coding agent can answer by searching through the codebase.
The ground truth should be something the agent can find in the codebase in its attempt to answer the user query.

Return Yes if they both make sense and are obtainable.
Return No if it doesnt make sense or is not something that can be answered by searching through the codebase.
"""


async def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    gen = chatan.generator("openai", api_key)

    ds = chatan.dataset(
        {
            "file_path": chatan.call(get_file_path),
            "file_chunk": chatan.call(get_file_chunk),
            "ground_truth": gen(GROUND_TRUTH_PROMPT),
            "user_query": gen(USER_QUERY_PROMPT),
            "check": gen(CHECK_GROUND_TRUTH_PROMPT)
        }
    )

    await ds.generate(n=1000, concurrency=500)
    hf_ds = ds.to_huggingface()
    hf_ds.push_to_hub("cdreetz/swe-grep-final", token=os.getenv("HF_TOKEN"))
    return hf_ds


if __name__ == "__main__":
    d = asyncio.run(main())


