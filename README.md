# 📚 Documentation Agent

An AI-powered system that continuously monitors GitHub repositories and automatically keeps documentation in sync with the codebase.

---

## 🚀 Overview

**Documentation Agent** is designed to act like a diligent developer who never forgets to update documentation.  
It observes repository changes, understands code intent using AI, and updates documentation whenever necessary—without human intervention.

---

## 🧠 System Architecture

The agent operates in a **cyclical execution flow** to ensure documentation always reflects the latest code.

### 1️⃣ Discovery Phase
- Connects to GitHub via the REST API
- Recursively scans the repository
- Filters relevant source files
- Ignores build artifacts and dependency directories (e.g., `node_modules`, `dist`, `.venv`)

---

### 2️⃣ Difference Engine

- Compares the current repository state with the previous run
- Detects:
  - File additions
  - Modifications
  - Deletions

---

### 3️⃣ Intelligence Layer

  - Interprets code behavior
  - Infers developer intent

---

### 4️⃣ Commit & Push
- Automatically creates a commit


---

## ✨ Core Features

- 🔄 **Automated Monitoring**  
  Periodically checks the repository at configurable intervals

- 🤖 **AI-Powered Understanding**  
  Uses Gemini 2.0 to reason about code, not just diff it

- 🧹 **Smart Filtering**  
  Excludes non-essential files and directories automatically

- 📝 **Self-Updating Documentation**  
  Keeps README and docs accurate with every code change

---

## 🛠 Installation & Usage

### Prerequisites
- Python 3.10+
- PyGitHub
- Gemini API Key

---

