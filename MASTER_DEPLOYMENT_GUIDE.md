# CORTEX Master Control Plane - Deployment Guide

Complete guide to deploying the master admin dashboard (frontend + backend).

## Architecture Overview

```
Master Control Plane
├── Master Backend (Render) → cortex-master-api.onrender.com
│   └── Connects to: Master Supabase (frkquqpbnczafibjsvmd)
│
├── Master Frontend (Vercel) → master-admin.vercel.app
│   └── Calls: Master Backend API
│
└── Master Supabase → frkquqpbnczafibjsvmd.supabase.co
    └── Stores: companies, schemas, deployments, admins

Company Deployments (e.g., Unit Industries)
├── Backend (Render) → cortex-backend-eehs.onrender.com
│   ├── Connects to: Master Supabase (for configs)
│   └── Connects to: Company Supabase (for data)
│
└── Frontend (Vercel) → connectorfrontend-vsnc.vercel.app
    └── Calls: Company Backend API
```

---

## Part 1: Deploy Master Backend to Render

### Step 1: Create New Web Service

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository: `ThunderbirdLabs/CORTEX`
4. Configure:
   ```
   Name: cortex-master-api
   Region: Oregon (US West)
   Branch: main
   Root Directory: master-backend
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
   Instance Type: Starter ($7/month)
   ```

### Step 2: Add Environment Variables

In the Environment tab, add:

```bash
MASTER_SUPABASE_URL=https://frkquqpbnczafibjsvmd.supabase.co
MASTER_SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZya3F1cXBibmN6YWZpYmpzdm1kIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MTc2NzYxNywiZXhwIjoyMDc3MzQzNjE3fQ.Q8OYGzwDYGk3tiybmW5EvuKOPZk9yJ1GaK71MpuCiys
```

### Step 3: Deploy

Click **"Create Web Service"**

Wait 3-5 minutes for deployment to complete.

### Step 4: Verify Backend

Once deployed, visit:
```
https://cortex-master-api.onrender.com/
```

You should see:
```json
{
  "name": "CORTEX Master Control Plane API",
  "version": "1.0.0",
  "status": "operational"
}
```

Test health check:
```
https://cortex-master-api.onrender.com/health
```

Should show:
```json
{
  "status": "healthy",
  "master_supabase": "connected",
  "timestamp": "2025-10-29T..."
}
```

### Step 5: View API Docs

Visit:
```
https://cortex-master-api.onrender.com/docs
```

You'll see interactive API documentation (FastAPI Swagger UI).

---

## Part 2: Deploy Master Frontend to Vercel

### Step 1: Push Code to GitHub

Make sure master-admin-frontend is pushed to your GitHub repository.

### Step 2: Create New Vercel Project

1. Go to https://vercel.com/new
2. Click **"Import Git Repository"**
3. Select: `ThunderbirdLabs/CORTEX`
4. Configure:
   ```
   Project Name: cortex-master-admin
   Framework Preset: Next.js
   Root Directory: master-admin-frontend
   Build Command: npm run build
   Output Directory: .next
   Install Command: npm install
   ```

### Step 3: Add Environment Variables

In the Environment Variables section, add:

```bash
NEXT_PUBLIC_MASTER_API_URL=https://cortex-master-api.onrender.com
```

Make sure to add it for:
- ✅ Production
- ✅ Preview
- ✅ Development

### Step 4: Deploy

Click **"Deploy"**

Wait 2-3 minutes for build to complete.

### Step 5: Verify Frontend

Once deployed, Vercel will give you a URL like:
```
https://cortex-master-admin.vercel.app
```

Visit it and you should see the purple/pink gradient login page!

### Step 6: Test Login

Login with:
```
Email: nicolas@unit.com
Password: UnitMaster2025!
```

You should be redirected to the dashboard!

---

## Part 3: Configure Custom Domain (Optional)

### For Frontend (Vercel)

1. In Vercel project settings → **Domains**
2. Add custom domain: `admin.cortex.unit.com` (or similar)
3. Follow DNS instructions
4. Wait for SSL certificate provisioning

### For Backend (Render)

1. In Render service settings → **Custom Domains**
2. Add custom domain: `api-master.cortex.unit.com` (or similar)
3. Update DNS:
   ```
   CNAME api-master.cortex.unit.com → cortex-master-api.onrender.com
   ```
4. Wait for SSL certificate provisioning

### Update Frontend Env Var

After backend custom domain is set up:

1. Go to Vercel project → **Settings** → **Environment Variables**
2. Edit `NEXT_PUBLIC_MASTER_API_URL`
3. Change to: `https://api-master.cortex.unit.com`
4. Redeploy frontend

---

## Part 4: Test End-to-End

### 1. Login to Master Dashboard

```
https://cortex-master-admin.vercel.app
Email: nicolas@unit.com
Password: UnitMaster2025!
```

### 2. View Dashboard Statistics

Should show:
- Total Companies: 1
- Active: 1
- Trial: 0
- Provisioning: 0

### 3. View Companies Page

Should show Unit Industries card with:
- Name: Unit Industries Group, Inc.
- Slug: @unit-industries
- Status: Active
- Location: United States
- Industries: Technology, SaaS, Enterprise Software

### 4. View Schemas Page

1. Select "Unit Industries" from dropdown
2. Should show "No custom schemas" (for now)
3. Click "Add Schema"
4. Fill in:
   ```
   Type: Entity
   Name: MACHINE
   Description: Injection molding machines and equipment
   ```
5. Click "Add Schema"
6. Should appear in list!

### 5. Restart Unit Industries Backend

To make schema take effect:

1. Go to Render → `cortex-backend-eehs`
2. Click **"Manual Deploy"** → **"Deploy latest commit"**
3. Wait for restart
4. Check logs for:
   ```
   🏢 Loading schemas from MASTER (Company: 2ede0765...)
   ✅ Loaded 1 custom entities: ['MACHINE']
   ```

---

## Part 5: Troubleshooting

### Backend Issues

**Problem: "Module not found" errors**
- Check `requirements.txt` includes all dependencies
- Try manual deploy in Render dashboard

**Problem: "MASTER_SUPABASE_URL not set"**
- Go to Render → Environment → verify env vars are set
- Redeploy

**Problem: "Failed to connect to master Supabase"**
- Check `MASTER_SUPABASE_SERVICE_KEY` is correct (not anon key!)
- Test connection in master Supabase dashboard

### Frontend Issues

**Problem: "Failed to fetch" errors**
- Check `NEXT_PUBLIC_MASTER_API_URL` is set correctly
- Verify backend is deployed and healthy
- Check CORS settings in backend (should allow all origins for now)

**Problem: Login fails with 401**
- Check email/password are correct
- Verify master_admins table has your account
- Check password hash is correct (bcrypt)

**Problem: Dashboard shows no companies**
- Check companies table in master Supabase
- Verify API token is being sent in Authorization header
- Check browser console for errors

### Database Issues

**Problem: "Table not found" errors**
- Verify you ran `001_create_master_tables.sql` on master Supabase
- Check table names match exactly (case-sensitive)

**Problem: "Permission denied"**
- Check you're using service_role key (not anon key)
- Verify RLS policies if enabled

---

## Part 6: URLs Reference

### Master Control Plane

| Service | URL | Purpose |
|---------|-----|---------|
| Master Backend | https://cortex-master-api.onrender.com | API for managing companies |
| Master Frontend | https://cortex-master-admin.vercel.app | Admin dashboard UI |
| Master Supabase | https://frkquqpbnczafibjsvmd.supabase.co | Control plane database |

### Unit Industries (Company Deployment)

| Service | URL | Purpose |
|---------|-----|---------|
| Backend | https://cortex-backend-eehs.onrender.com | Company API (multi-tenant mode) |
| Frontend | https://connectorfrontend-vsnc.vercel.app | Customer-facing UI |
| Supabase | https://ybopkvdylvhtqykhddok.supabase.co | Company operational data |

---

## Part 7: Security Checklist

### Before Production

- [ ] Change master admin password from default
- [ ] Rotate master Supabase service key
- [ ] Enable Supabase RLS policies
- [ ] Restrict backend CORS to specific origins
- [ ] Encrypt sensitive fields in company_deployments
- [ ] Enable MFA for master admin accounts
- [ ] Set up monitoring and alerts
- [ ] Configure rate limiting
- [ ] Enable audit logging
- [ ] Back up master Supabase regularly

### Render Security

- [ ] Enable automatic deployments on push
- [ ] Set up health checks
- [ ] Configure environment variable encryption
- [ ] Enable DDoS protection

### Vercel Security

- [ ] Enable automatic HTTPS
- [ ] Configure security headers
- [ ] Enable preview deployments protection
- [ ] Set up deployment protection

---

## Part 8: Next Steps

Once deployed:

1. **Add second company** (Acme Corp)
   - Manually provision Supabase, Neo4j, Qdrant, Render, Vercel
   - Add to master via dashboard
   - Test multi-tenant isolation

2. **Build automated provisioning**
   - Script to auto-create all infrastructure
   - One-click "Add Company" button
   - Email customer credentials

3. **Add monitoring**
   - Health checks for all deployments
   - Uptime monitoring
   - Error tracking (Sentry)
   - Performance metrics

4. **Add billing**
   - Track usage per company
   - Stripe integration
   - Invoice generation

5. **Build customer self-service**
   - Customer portal (separate from master admin)
   - Let customers add team members
   - Let customers configure schemas
   - Usage analytics

---

## Support

If you run into issues:

1. Check Render logs for backend errors
2. Check Vercel logs for frontend errors
3. Check browser console for client-side errors
4. Verify all environment variables are set
5. Test API endpoints directly via `/docs`

**Master backend logs**: https://dashboard.render.com → cortex-master-api → Logs
**Master frontend logs**: https://vercel.com → cortex-master-admin → Deployments → Logs

---

**You now have a fully deployed enterprise multi-tenant control plane!** 🎉
