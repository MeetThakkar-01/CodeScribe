# 🔍 Troubleshooting Guide

## ✅ What's Working:
- Server is running and healthy
- ngrok tunnel is active
- Public URL is accessible: https://unsatirized-unstraightened-corinna.ngrok-free.dev

## 🐛 Let's Debug Step by Step

### Step 1: Verify GitHub Webhook is Updated

1. Go to: https://github.com/settings/apps
2. Click on **codescribeagent**
3. Check the **Webhook URL** field shows:
   ```
   https://unsatirized-unstraightened-corinna.ngrok-free.dev/webhook/github
   ```
4. Make sure it ends with `/webhook/github` (not just the base URL)

### Step 2: Check Webhook Deliveries

1. In your GitHub App settings, scroll to **Recent Deliveries**
2. Look for recent webhook events
3. Click on the most recent one

**What to look for:**
- ✅ **Green checkmark** = Working! (200 response)
- ❌ **Red X** = Problem (click to see error details)

**Common issues:**
- **404 Not Found** = URL is wrong (missing `/webhook/github`)
- **401 Unauthorized** = Webhook secret mismatch
- **Connection refused** = ngrok not running or wrong URL

### Step 3: Test with a Simple PR

Did you create a Pull Request? The agent only triggers on:
- New PR opened
- PR reopened
- PR synchronized (new commits pushed)

**To test:**

1. **In your repository**, create a test file:
   ```bash
   # Go to your repository (NOT the agent repo)
   cd /path/to/your/test/repository
   
   # Create a new branch
   git checkout -b test-ai-review-2
   
   # Create a test file with intentional bugs
   cat > buggy_code.py << 'EOF'
def divide(a, b):
    return a / b  # Bug: no zero check!

def get_user(users, id):
    return users[id]  # Bug: no bounds check!
EOF
   
   git add buggy_code.py
   git commit -m "Test AI review"
   git push origin test-ai-review-2
   ```

2. **On GitHub**, open a Pull Request from this branch

3. **Wait 10-20 seconds** and check for comments

### Step 4: Check Server Logs

Look at the terminal where the server is running. You should see:
```json
{"event":"received webhook","event_type":"pull_request",...}
{"event":"Analyzing code changes",...}
{"event":"Posted comments",...}
```

**If you don't see these logs:**
- Webhook isn't reaching the server
- Check GitHub webhook deliveries for errors

### Step 5: Common Issues & Solutions

#### Issue: "No comments posted"

**Check:**
1. Is the GitHub App installed on the repository?
   - Go to: https://github.com/settings/installations
   - Click **Configure** next to codescribeagent
   - Make sure your repository is selected

2. Does the app have correct permissions?
   - Pull requests: Read & Write ✅
   - Contents: Read ✅

#### Issue: "Webhook shows 401 error"

**Solution:**
The webhook secret might be wrong. Let me verify:
```bash
# Check your .env file
cat .env | grep WEBHOOK_SECRET
```

Should match the secret in GitHub App settings.

#### Issue: "Agent posts comment but it's empty or error"

**Check:**
1. Gemini API key is valid
2. You haven't exceeded free tier limits
3. Server logs show the actual error

### Step 6: Manual Webhook Test

You can manually trigger a webhook from GitHub:

1. Go to GitHub App settings → Recent Deliveries
2. Click on any delivery
3. Click **Redeliver** button
4. Check server logs for the event

---

## 📊 Quick Diagnostic Commands

Run these to check status:

```bash
# Check if server is running
curl http://localhost:8000/health

# Check if ngrok is accessible
curl https://unsatirized-unstraightened-corinna.ngrok-free.dev/health

# View server logs (last 20 lines)
# Look at the terminal where you ran: python -m src.main
```

---

## 🆘 Tell Me What You See

Please tell me:

1. **Did you update the GitHub webhook URL?** (Yes/No)
2. **Did you create a Pull Request?** (Yes/No)
3. **What do you see in GitHub webhook deliveries?** (Green checkmark or red X?)
4. **Any error messages?** (Copy/paste them)

I'll help you fix it! 🔧
