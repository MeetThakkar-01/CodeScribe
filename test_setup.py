"""
Test script to verify your Documentation Agent setup
Run this to check if everything is configured correctly
"""

import os
import sys
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

def test_environment():
    """Test if environment variables are set up correctly"""
    print("=" * 60)
    print("TESTING ENVIRONMENT CONFIGURATION")
    print("=" * 60)
    
    load_dotenv()
    
    required_vars = {
        "GITHUB_REPO": os.getenv("GITHUB_REPO"),
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY")
    }
    
    all_good = True
    
    for var_name, var_value in required_vars.items():
        if var_value:
            # Mask sensitive values
            if "TOKEN" in var_name or "KEY" in var_name:
                masked = var_value[:10] + "..." + var_value[-4:] if len(var_value) > 14 else "***"
                print(f"[OK] {var_name}: {masked}")
            else:
                print(f"[OK] {var_name}: {var_value}")
        else:
            print(f"[!] {var_name}: NOT SET")
            all_good = False
    
    print()
    return all_good

def test_imports():
    """Test if all required packages are installed"""
    print("=" * 60)
    print("TESTING REQUIRED PACKAGES")
    print("=" * 60)
    
    packages = {
        "github": "PyGithub",
        "google.genai": "google-genai",
        "dotenv": "python-dotenv"
    }
    
    all_good = True
    
    for module_name, package_name in packages.items():
        try:
            __import__(module_name)
            print(f"[OK] {package_name} is installed")
        except ImportError:
            print(f"[!] {package_name} is NOT installed")
            print(f"   Install with: pip install {package_name}")
            all_good = False
    
    print()
    return all_good

def test_github_connection():
    """Test GitHub connection"""
    print("=" * 60)
    print("TESTING GITHUB CONNECTION")
    print("=" * 60)
    
    try:
        from github import Github, Auth
        load_dotenv()
        
        token = os.getenv("GITHUB_TOKEN")
        repo_name = os.getenv("GITHUB_REPO")
        
        if not token or not repo_name:
            print("[!] GitHub credentials not set in .env")
            return False
        
        auth = Auth.Token(token)
        g = Github(auth=auth)
        repo = g.get_repo(repo_name)
        
        print(f"[OK] Connected to repository: {repo.full_name}")
        print(f"   Description: {repo.description or 'No description'}")
        print(f"   Stars: {repo.stargazers_count}")
        print(f"   Forks: {repo.forks_count}")
        print(f"   Default branch: {repo.default_branch}")
        
        # Check rate limit (simpler approach)
        try:
            rate = g.get_rate_limit()
            print(f"   API calls remaining: {rate.core.remaining}")
        except:
            print(f"   API connection: OK")
        
        print()
        return True
        
    except Exception as e:
        print(f"[!] Error connecting to GitHub: {e}")
        print()
        return False

def test_gemini_connection():
    """Test Gemini API connection"""
    print("=" * 60)
    print("TESTING GEMINI API CONNECTION")
    print("=" * 60)
    
    try:
        from google import genai
        from google.genai import types
        load_dotenv()
        
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            print("[!] Gemini API key not set in .env")
            return False
        
        client = genai.Client(api_key=api_key)
        
        # Make a simple test call with stable model
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents="Say 'API connection successful!' and nothing else.",
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=50,
            )
        )
        
        response_text = response.text.strip()
        print(f"[OK] Gemini API connected successfully")
        print(f"   Model: gemini-2.0-flash")
        print(f"   Response: {response_text}")
        print()
        return True
        
    except Exception as e:
        print(f"[!] Error connecting to Gemini API: {e}")
        print()
        return False

def main():
    """Run all tests"""
    print("\n=== Documentation Agent Setup Test ===\n")
    
    results = {
        "Environment": test_environment(),
        "Packages": test_imports(),
        "GitHub": test_github_connection(),
        "Gemini": test_gemini_connection()
    }
    
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{test_name}: {status}")
    
    print()
    
    if all(results.values()):
        print("SUCCESS: All tests passed! Your Documentation Agent is ready to use.")
        print("Run: python doc_agent.py")
    else:
        print("WARNING: Some tests failed. Please fix the issues above before running the agent.")
    
    print()

if __name__ == "__main__":
    main()