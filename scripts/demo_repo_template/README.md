# Simple Calculator

A small Python calculator. New features land via pull requests, which trigger automated review by the **CodeScribe** multi-agent system.

## Usage

```python
from calculator import add, subtract, multiply, divide

add(2, 3)         # 5
subtract(10, 4)   # 6
multiply(6, 7)    # 42
divide(20, 4)     # 5.0
```

## Running

```bash
python calculator.py
```

## Tests

```bash
pytest test_calculator.py
```

## About CodeScribe

Pull requests opened against this repository trigger three AI agents working together through a LangGraph orchestrator:

- **Code Review Agent** — analyzes the diff for bugs, security issues, performance problems, and style concerns. Posts inline comments with suggested fixes.
- **Documentation Agent** — updates this README when code changes warrant it.
- **Jira Integration Agent** — links the PR to its tracked issue and updates project status.

The agents are coordinated by the `CodeScribeOrchestrator`, with retrieval grounded in a Pinecone vector index and observability through LangSmith.
