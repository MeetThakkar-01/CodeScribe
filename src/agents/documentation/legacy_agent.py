"""
Documentation Agent - Monitors GitHub repo and maintains README documentation
Uses Google Gemini API for AI-powered documentation generation
"""

import os
import sys
import time
import hashlib
from datetime import datetime
from github import Github, Auth
from google import genai
from google.genai import types
import json
from pathlib import Path
from dotenv import load_dotenv

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

# Load environment variables
load_dotenv()


class DocumentationAgent:
    def __init__(self, repo_name, github_token, gemini_api_key):
        """
        Initialize the documentation agent
        
        Args:
            repo_name: GitHub repository in format "owner/repo"
            github_token: GitHub personal access token
            gemini_api_key: Google Gemini API key
        """
        # Initialize GitHub with new auth method
        auth = Auth.Token(github_token)
        self.github = Github(auth=auth)
        self.repo = self.github.get_repo(repo_name)
        
        # Configure Gemini with new client
        self.client = genai.Client(api_key=gemini_api_key)
        
        self.cache_file = "repo_cache.json"
        self.last_commit_sha = None
        
    def get_repo_structure(self):
        """Get the current repository structure and file contents"""
        structure = {}
        contents = self.repo.get_contents("")
        
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(self.repo.get_contents(file_content.path))
            else:
                # Skip non-code files and large files
                if self._should_process_file(file_content.path):
                    try:
                        structure[file_content.path] = {
                            "content": file_content.decoded_content.decode('utf-8'),
                            "sha": file_content.sha
                        }
                    except Exception as e:
                        print(f"Error reading {file_content.path}: {e}")
        
        return structure
    
    def _should_process_file(self, filepath):
        """Determine if a file should be processed for documentation"""
        # Include code files, exclude binaries and generated files
        code_extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', 
                          '.c', '.h', '.go', '.rs', '.rb', '.php', '.cs', '.swift']
        exclude_dirs = ['node_modules', 'venv', '__pycache__', 'dist', 'build', '.git']
        
        # Check if in excluded directory
        for exclude_dir in exclude_dirs:
            if f'/{exclude_dir}/' in filepath or filepath.startswith(exclude_dir):
                return False
        
        # Check file extension
        return any(filepath.endswith(ext) for ext in code_extensions)
    
    def get_current_readme(self):
        """Get current README.md content"""
        try:
            readme = self.repo.get_readme()
            return readme.decoded_content.decode('utf-8')
        except Exception as e:
            print(f"No README found or error: {e}")
            return ""
    
    def analyze_changes(self, old_structure, new_structure):
        """Analyze what changed in the repository"""
        changes = {
            "added": [],
            "modified": [],
            "deleted": []
        }
        
        old_files = set(old_structure.keys())
        new_files = set(new_structure.keys())
        
        changes["added"] = list(new_files - old_files)
        changes["deleted"] = list(old_files - new_files)
        
        for filepath in old_files & new_files:
            if old_structure[filepath]["sha"] != new_structure[filepath]["sha"]:
                changes["modified"].append(filepath)
        
        return changes
    
    def generate_documentation(self, repo_structure, current_readme, changes=None):
        """Use Gemini to generate or update documentation without code blocks"""
        
        # Prepare the codebase summary
        code_summary = self._prepare_code_summary(repo_structure)
        
        # The core instruction to avoid the "boxes"
        formatting_instructions = """
1. Use markdown ONLY for headings (# ## ###) and lists (-)
2. DO NOT use code blocks (```) UNLESS showing actual executable code
3. DO NOT use backticks (`) for regular text, file names, or descriptions
4. Write everything as plain readable text in paragraphs
5. Code blocks are ONLY for: commands to run, code examples, configuration files
6. NO code blocks for: explanations, descriptions, architecture flow, file names
"""

        if changes and (changes["added"] or changes["modified"] or changes["deleted"]):
            prompt = f"""You are a technical documentation expert. Update the README.

CURRENT README:
{current_readme}

REPOSITORY CODE:
{code_summary}

CHANGES:
- Added: {', '.join(changes['added']) if changes['added'] else 'None'}
- Modified: {', '.join(changes['modified']) if changes['modified'] else 'None'}
- Deleted: {', '.join(changes['deleted']) if changes['deleted'] else 'None'}

TASK:
Review the changes. If updates are needed, provide an updated README. If not, respond with "NO_UPDATE_NEEDED".

{formatting_instructions}

Provide ONLY the markdown content, or "NO_UPDATE_NEEDED"."""
        else:
            prompt = f"""You are a technical documentation expert. Create a README for this repository.

REPOSITORY CODE:
{code_summary}

{formatting_instructions}

CRITICAL FORMATTING RULES - READ CAREFULLY:
1. Use markdown ONLY for headings (# ## ###) and lists (-)
2. DO NOT use code blocks (```) UNLESS showing actual executable code
3. DO NOT use backticks (`) for regular text, file names, or descriptions
4. Write everything as plain readable text in paragraphs
5. Code blocks are ONLY for: commands to run, code examples, configuration files
6. NO code blocks for: explanations, descriptions, architecture flow, file names

BAD EXAMPLES - NEVER DO THIS:
```
This is how it works  (NO - explanations are plain text)
```
The `server.js` file  (NO - file names are plain text)
- `Fast performance`  (NO - features are plain text)

GOOD EXAMPLES - ALWAYS DO THIS:
The server.js file handles all HTTP requests.  (YES - plain text)
The system uses a microservices architecture.  (YES - plain explanation)
Features include fast performance and easy deployment.  (YES - plain text)

Install dependencies:
```bash
npm install
```
(YES - actual command)

REQUIRED STRUCTURE WITH ARCHITECTURE:

# Project Title
One clear sentence describing what this project is and does.

## Overview
Write 2-3 sentences explaining the project purpose, main functionality, and target use case. Be concise and informative.

## Architecture

Describe the system architecture in clear paragraphs:

Explain the overall architectural pattern used (MVC, microservices, client-server, etc.). Describe how the main components are organized and how they communicate with each other.

Key components:
- Component 1: Explain its purpose and responsibilities
- Component 2: Explain its purpose and responsibilities  
- Component 3: Explain its purpose and responsibilities

Walk through the data flow or request flow. Explain what happens from input to output in a logical narrative sequence.

## Features
- Feature 1 with brief description of what it enables
- Feature 2 with brief description of what it enables
- Feature 3 with brief description of what it enables

## How It Works

Explain the operational flow in narrative paragraphs:

Describe the main workflow step by step. When X happens, the system does Y, which then triggers Z. Walk through typical use cases and explain the process in plain language.

For example: A client makes a request, the server receives it, processes the data through various handlers, applies business logic, interacts with the database if needed, and returns a formatted response.

## Installation

Prerequisites: List required software, versions, and dependencies.

Step-by-step installation:
1. Clone the repository
2. Navigate to directory
3. Install dependencies
4. Set up configuration

Commands:
```bash
git clone repository-url
cd project-directory
npm install
```

## Usage

Explain how to run and use the project in plain text.

Starting the application:
```bash
npm start
```

Making requests or using features:
```bash
curl http://localhost:3000
```

## API Reference (if applicable)

List endpoints with descriptions:

- GET /users - Retrieves all user records from the database
- POST /users - Creates a new user with provided data
- PUT /users/id - Updates existing user information
- DELETE /users/id - Removes user from the system

Describe request/response format, expected parameters, and return values in paragraphs.

## Project Structure

Explain the organization in narrative form:

The codebase is organized into logical sections. The main application code lives in the src directory. Configuration files are in the config folder. Tests are in the tests directory.

Important files:
- main.py: Application entry point that starts the server
- routes.py: Defines all API endpoints and routing logic
- models.py: Database models and schema definitions
- utils.py: Shared helper functions

## Technology Stack
- Technology 1: Explanation of its role in the project
- Technology 2: Explanation of its role in the project
- Technology 3: Explanation of its role in the project

Explain why these technologies were chosen and how they work together.



## Development

Explain the development setup and workflow in paragraphs.

Running tests:
```bash
npm test
```

## Contributing
Contribution guidelines in numbered steps without backticks.


REMEMBER: 
- Write in a natural, explanatory style
- Use plain paragraphs for all descriptions and explanations
- Code blocks only for actual code, commands, or config files
- No backticks in regular text
- Focus on helping readers understand both WHAT the code does and HOW it's structured

"""

        # Call Gemini API
        try:
            response = self.client.models.generate_content(
                model=getattr(self, 'model_name', 'gemini-2.5-flash'),
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=4000,
                )
            )
            
            response_text = response.text.strip()
            
            if response_text == "NO_UPDATE_NEEDED":
                return None
            
            return response_text
            
        except Exception as e:
            print(f"[!] Error calling Gemini API: {e}")
            return None
        
            
    def _prepare_code_summary(self, repo_structure):
        """Prepare a concise summary of the codebase for the LLM"""
        summary = []
        
        # Organize files by directory
        files_by_dir = {}
        for filepath, data in repo_structure.items():
            dir_name = os.path.dirname(filepath) or "root"
            if dir_name not in files_by_dir:
                files_by_dir[dir_name] = []
            files_by_dir[dir_name].append((filepath, data["content"]))
        
        # Create summary
        for dir_name, files in sorted(files_by_dir.items()):
            summary.append(f"\n## Directory: {dir_name}")
            for filepath, content in files:
                summary.append(f"\n### File: {filepath}")
                # Include first 50 lines or full file if shorter
                lines = content.split('\n')[:50]
                summary.append("```")
                summary.append('\n'.join(lines))
                if len(content.split('\n')) > 50:
                    summary.append("... (truncated)")
                summary.append("```")
        
        return '\n'.join(summary)
    
    def update_readme(self, new_content):
        """Update the README.md file in the repository"""
        try:
            # Get the README file
            readme = self.repo.get_readme()
            
            # Update it
            self.repo.update_file(
                path=readme.path,
                message="docs: Update README via Documentation Agent",
                content=new_content,
                sha=readme.sha
            )
            print("[OK] README updated successfully!")
            return True
        except Exception as e:
            # If README doesn't exist, create it
            try:
                self.repo.create_file(
                    path="README.md",
                    message="docs: Create README via Documentation Agent",
                    content=new_content
                )
                print("[OK] README created successfully!")
                return True
            except Exception as create_error:
                print(f"[!] Error updating README: {e}")
                print(f"[!] Error creating README: {create_error}")
                return False
    
    def load_cache(self):
        """Load cached repository state"""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_cache(self, data):
        """Save repository state to cache"""
        with open(self.cache_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def run_once(self):
        """Run the documentation agent once"""
        print(f"\n[*] Checking repository at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Get current state
        current_structure = self.get_repo_structure()
        current_readme = self.get_current_readme()
        
        # Load previous state
        cached_data = self.load_cache()
        
        # Analyze changes
        if cached_data and current_readme:
            changes = self.analyze_changes(cached_data, current_structure)
            
            if not any(changes.values()):
                print("[OK] No changes detected")
                return
            
            print(f"[*] Changes detected:")
            print(f"   Added: {len(changes['added'])} files")
            print(f"   Modified: {len(changes['modified'])} files")
            print(f"   Deleted: {len(changes['deleted'])} files")
            
            # Generate updated documentation
            new_readme = self.generate_documentation(current_structure, current_readme, changes)
        else:
            print("[*] First run - generating initial documentation")
            new_readme = self.generate_documentation(current_structure, current_readme)
        
        # Update README if needed
        if new_readme:
            print("[*] Documentation update required")
            if self.update_readme(new_readme):
                # Save new state
                self.save_cache(current_structure)
        else:
            print("[OK] No documentation updates needed")
            # Still save the cache to track changes
            self.save_cache(current_structure)
    
    def run_continuous(self, interval_minutes=60):
        """Run the agent continuously"""
        print(f"[*] Documentation Agent started")
        print(f"[*] Monitoring repository: {self.repo.full_name}")
        print(f"[*] Check interval: {interval_minutes} minutes")
        
        while True:
            try:
                self.run_once()
            except Exception as e:
                print(f"[!] Error: {e}")
            
            print(f"\n[*] Waiting {interval_minutes} minutes until next check...")
            time.sleep(interval_minutes * 60)


def main():
    """Main entry point"""
    # Get configuration from environment variables
    repo_name = os.getenv("GITHUB_REPO")  # Format: "owner/repo"
    github_token = os.getenv("GITHUB_TOKEN")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    check_interval = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
    
    if not all([repo_name, github_token, gemini_api_key]):
        print("[!] Error: Missing required environment variables")
        print("Required: GITHUB_REPO, GITHUB_TOKEN, GEMINI_API_KEY")
        return
    
    # Create and run agent
    agent = DocumentationAgent(repo_name, github_token, gemini_api_key)
    
    # Run once or continuously based on environment
    if os.getenv("RUN_ONCE", "false").lower() == "true":
        agent.run_once()
    else:
        agent.run_continuous(check_interval)


if __name__ == "__main__":
    main()