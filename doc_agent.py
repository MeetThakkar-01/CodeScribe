"""
Documentation Agent - Monitors GitHub repo and maintains README documentation
Uses Google Gemini API for AI-powered documentation generation
"""

import os
import time
import hashlib
from datetime import datetime
from github import Github
import google.generativeai as genai
import json
from pathlib import Path
from dotenv import load_dotenv

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
        self.github = Github(github_token)
        self.repo = self.github.get_repo(repo_name)
        
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        
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
        """Use Gemini to generate or update documentation"""
        
        # Prepare the codebase summary
        code_summary = self._prepare_code_summary(repo_structure)
        
        # Create prompt for Gemini
        if changes and (changes["added"] or changes["modified"] or changes["deleted"]):
            prompt = f"""You are a technical documentation expert. Analyze the following code repository and update the README documentation.

CURRENT README:
{current_readme}

REPOSITORY STRUCTURE AND CODE:
{code_summary}

RECENT CHANGES:
- Added files: {', '.join(changes['added']) if changes['added'] else 'None'}
- Modified files: {', '.join(changes['modified']) if changes['modified'] else 'None'}
- Deleted files: {', '.join(changes['deleted']) if changes['deleted'] else 'None'}

TASK:
1. Review the changes and determine if README updates are necessary
2. If updates are needed, provide an updated README that:
   - Clearly explains what the project does
   - Documents the main components and their purposes
   - Includes installation instructions
   - Provides usage examples
   - Lists dependencies
   - Maintains consistent formatting

3. If no significant updates are needed, respond with: "NO_UPDATE_NEEDED"

Provide ONLY the updated README content in markdown format, or "NO_UPDATE_NEEDED"."""
        else:
            prompt = f"""You are a technical documentation expert. Create comprehensive README documentation for this code repository.

REPOSITORY STRUCTURE AND CODE:
{code_summary}

Create a professional README.md that includes:
1. Project title and description
2. Key features
3. Installation instructions
4. Usage examples
5. Project structure overview
6. Dependencies
7. Contributing guidelines (if applicable)

Provide ONLY the README content in markdown format."""

        # Call Gemini API
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=4000,
                )
            )
            
            response_text = response.text.strip()
            
            if response_text == "NO_UPDATE_NEEDED":
                return None
            
            return response_text
            
        except Exception as e:
            print(f" Error calling Gemini API: {e}")
            return None
    
    def _prepare_code_summary(self, repo_structure):
        """Prepare a concise summary of the codebase for Claude"""
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
            print(" README updated successfully!")
            return True
        except Exception as e:
            # If README doesn't exist, create it
            try:
                self.repo.create_file(
                    path="README.md",
                    message="docs: Create README via Documentation Agent",
                    content=new_content
                )
                print("README created successfully!")
                return True
            except Exception as create_error:
                print(f"Error updating README: {e}")
                print(f"Error creating README: {create_error}")
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
        print(f"\n Checking repository at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Get current state
        current_structure = self.get_repo_structure()
        current_readme = self.get_current_readme()
        
        # Load previous state
        cached_data = self.load_cache()
        
        # Analyze changes
        if cached_data:
            changes = self.analyze_changes(cached_data, current_structure)
            
            if not any(changes.values()):
                print(" No changes detected")
                return
            
            print(f" Changes detected:")
            print(f"   Added: {len(changes['added'])} files")
            print(f"   Modified: {len(changes['modified'])} files")
            print(f"   Deleted: {len(changes['deleted'])} files")
            
            # Generate updated documentation
            new_readme = self.generate_documentation(current_structure, current_readme, changes)
        else:
            print("First run - generating initial documentation")
            new_readme = self.generate_documentation(current_structure, current_readme)
        
        # Update README if needed
        if new_readme:
            print("Documentation update required")
            if self.update_readme(new_readme):
                # Save new state
                self.save_cache(current_structure)
        else:
            print("No documentation updates needed")
            # Still save the cache to track changes
            self.save_cache(current_structure)
    
    def run_continuous(self, interval_minutes=60):
        """Run the agent continuously"""
        print(f"Documentation Agent started")
        print(f"Monitoring repository: {self.repo.full_name}")
        print(f"Check interval: {interval_minutes} minutes")
        
        while True:
            try:
                self.run_once()
            except Exception as e:
                print(f" Error: {e}")
            
            print(f"\nWaiting {interval_minutes} minutes until next check...")
            time.sleep(interval_minutes * 60)


def main():
    """Main entry point"""
    # Get configuration from environment variables
    repo_name = os.getenv("GITHUB_REPO")  # Format: "owner/repo"
    github_token = os.getenv("GITHUB_TOKEN")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    check_interval = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
    
    if not all([repo_name, github_token, gemini_api_key]):
        print(" Error: Missing required environment variables")
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