# 🎉 FINAL STEP: Update GitHub Webhook URL

## ✅ Everything is Running!

- ✅ Server running on http://0.0.0.0:8000
- ✅ ngrok tunnel active
- ✅ Public URL: https://unsatirized-unstraightened-corinna.ngrok-free.dev

## 🔧 Update GitHub Webhook (2 minutes)

### Step 1: Go to Your GitHub App Settings
1. Visit: https://github.com/settings/apps
2. Click on your app: **codescribeagent**
3. Scroll down to **Webhook URL**

### Step 2: Update the Webhook URL
Replace the current URL with:
```
https://unsatirized-unstraightened-corinna.ngrok-free.dev/webhook/github
```

**IMPORTANT:** Make sure to include `/webhook/github` at the end!

### Step 3: Save Changes
Click **Save changes** at the bottom

### Step 4: Verify Webhook
1. Scroll down to **Recent Deliveries** section
2. GitHub will automatically send a ping event
3. You should see a ✅ green checkmark (200 response)

---

## 🧪 Ready to Test!

Once you've updated the webhook URL, you can test the agent by:

1. Creating a new branch in your repository
2. Making some code changes
3. Opening a Pull Request
4. Watch the AI review your code! 🤖

**The agent will post comments within 10-20 seconds!**

---

## 📝 Quick Reference

**Your Configuration:**
- GitHub App ID: 2791430
- Webhook URL: https://unsatirized-unstraightened-corinna.ngrok-free.dev/webhook/github
- Server: Running on port 8000
- ngrok: Active tunnel

**To stop the servers:**
- Press Ctrl+C in the terminal windows

**To restart:**
```bash
cd /Users/hari/.gemini/antigravity/scratch/github-pr-review-agent
source venv/bin/activate
python -m src.main
# In another terminal:
ngrok http 8000
```
