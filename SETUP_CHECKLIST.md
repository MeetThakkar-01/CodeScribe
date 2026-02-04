# Setup Progress Checklist

## ✅ COMPLETED
- [x] Python 3.13.5 verified
- [x] Virtual environment created
- [x] All dependencies installed

## 🔄 IN PROGRESS - YOU NEED TO DO THESE

### Step 4: Create GitHub App
**Your webhook secret:** `bea23b8267b21527495212ee742e9750da6b06249551f73194152018927570d4`

1. [ ] Go to: https://github.com/settings/apps
2. [ ] Click "New GitHub App"
3. [ ] Fill in:
   - Name: `PR-Review-Agent-YourName`
   - Homepage: `http://localhost:8000`
   - Webhook URL: `http://localhost:8000/webhook/github`
   - Webhook secret: `bea23b8267b21527495212ee742e9750da6b06249551f73194152018927570d4`
4. [ ] Set permissions:
   - Pull requests: **Read & write**
   - Contents: **Read only**
   - Metadata: **Read only** (automatic)
5. [ ] Subscribe to events:
   - Check: **Pull request**
6. [ ] Click "Create GitHub App"
7. [ ] **SAVE YOUR APP ID** (shown at top of page after creation)
8. [ ] Scroll down to "Private keys" → Click "Generate a private key"
9. [ ] Download the .pem file
10. [ ] Move .pem file to project:
    ```bash
    mv ~/Downloads/your-app-name*.private-key.pem /Users/hari/.gemini/antigravity/scratch/github-pr-review-agent/
    ```
11. [ ] Install app: Click "Install App" → Install on your repository

### Step 5: Get Google Gemini API Key
1. [ ] Go to: https://aistudio.google.com/app/apikey
2. [ ] Sign in with Google account
3. [ ] Click "Create API Key"
4. [ ] Copy the API key (starts with `AIza...`)
5. [ ] **SAVE IT** - you won't see it again!

### Step 6: Configure .env File
Once you have:
- GitHub App ID
- GitHub .pem filename
- Webhook secret (already generated above)
- Gemini API key

Tell me and I'll help you create the .env file!

## ⏳ NEXT STEPS (after you complete above)
- [ ] Create .env file
- [ ] Install ngrok
- [ ] Start the server
- [ ] Test with a PR

---

**TELL ME WHEN YOU'VE COMPLETED STEPS 4 & 5 ABOVE!**
I'll then help you with the configuration and testing.
