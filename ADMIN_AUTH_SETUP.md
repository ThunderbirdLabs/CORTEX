# Admin Auth Supabase Setup Guide

This document explains how to set up the separate Admin Auth Supabase project for platform admin authentication.

## Architecture Overview

**Two Supabase Projects:**

1. **Master Supabase** - Stores all customer data
   - Companies table
   - Company users table
   - Company deployments table
   - Audit logs
   - Customer authentication (for their company portals)

2. **Admin Auth Supabase** - Platform admin authentication ONLY
   - Only contains admin users (your team)
   - No customer data
   - Completely separate from customer authentication
   - Used only for admin portal login

## Security Model

- **Customers** authenticate through Master Supabase → can access their company portal
- **Admins** authenticate through Admin Auth Supabase → can access admin portal
- **Complete isolation**: Customers cannot access admin portal (different auth system)
- MASTERBACKEND verifies admin JWT tokens against Admin Auth Supabase
- MASTERBACKEND uses Master Supabase service key to access customer data

## Setup Steps

### 1. Create Admin Auth Supabase Project

1. Go to https://supabase.com/dashboard
2. Click "New Project"
3. Name: `cortex-admin-auth` (or similar)
4. Choose region (same as Master Supabase recommended)
5. Set strong database password
6. Wait for project to provision

### 2. Get Admin Auth Supabase Credentials

From your new Admin Auth Supabase project:

1. Go to **Settings → API**
2. Copy these values:
   - **Project URL** → `ADMIN_AUTH_SUPABASE_URL`
   - **anon/public key** → `ADMIN_AUTH_SUPABASE_ANON_KEY`

### 3. Add Environment Variables to MASTERBACKEND (Render)

Add these to your MASTERBACKEND Render service:

```bash
ADMIN_AUTH_SUPABASE_URL=https://your-admin-project.supabase.co
ADMIN_AUTH_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 4. Create Admin Users

In your Admin Auth Supabase project:

1. Go to **Authentication → Users**
2. Click "Add User"
3. Enter admin email and password
4. Enable email confirmation or auto-confirm
5. Repeat for each admin on your team

**Important:** Only create users here who should have admin portal access!

### 5. Enable 2FA (Recommended)

In Admin Auth Supabase:

1. Go to **Authentication → Providers**
2. Enable **Phone Auth** or **Email OTP** for 2FA
3. Configure 2FA settings
4. Require 2FA for all admin accounts

### 6. Admin Frontend Configuration

Your admin frontend needs to point to Admin Auth Supabase for login:

```typescript
// In admin frontend .env
NEXT_PUBLIC_SUPABASE_URL=https://your-admin-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
NEXT_PUBLIC_MASTERBACKEND_URL=https://masterbackend-cdfy.onrender.com
```

The admin frontend will:
1. Authenticate users through Admin Auth Supabase
2. Get JWT token
3. Send JWT to MASTERBACKEND for all API calls
4. MASTERBACKEND verifies JWT and accesses Master Supabase data

## Testing

### Test Admin Login:
1. Go to admin portal login page
2. Login with admin credentials (from Admin Auth Supabase)
3. Should receive JWT token
4. Make API call to MASTERBACKEND with JWT
5. MASTERBACKEND verifies JWT against Admin Auth Supabase
6. MASTERBACKEND returns customer data from Master Supabase

### Test Customer Isolation:
1. Try logging into admin portal with customer credentials → should fail
2. Customer JWT from Master Supabase should be rejected by admin endpoints

## Security Checklist

- [ ] Admin Auth Supabase project created
- [ ] Environment variables added to MASTERBACKEND
- [ ] MASTERBACKEND deployed and verified
- [ ] Admin users created in Admin Auth Supabase
- [ ] 2FA enabled for admin accounts (recommended)
- [ ] Tested admin login flow
- [ ] Verified customer credentials cannot access admin portal
- [ ] Admin portal can query Master Supabase data

## Troubleshooting

**Admin login fails:**
- Check `ADMIN_AUTH_SUPABASE_URL` and `ADMIN_AUTH_SUPABASE_ANON_KEY` in Render
- Verify admin user exists in Admin Auth Supabase
- Check browser console for errors

**Admin can't access data:**
- Verify MASTERBACKEND has Master Supabase service key
- Check MASTERBACKEND logs for auth errors
- Ensure JWT token is being sent in Authorization header

**Customer can access admin portal:**
- This should be impossible - customer JWT is from Master Supabase
- MASTERBACKEND verifies JWT against Admin Auth Supabase
- Different JWT issuers = automatic rejection

## Architecture Diagram

```
┌─────────────────┐
│  Customer User  │
└────────┬────────┘
         │ Login
         ▼
┌─────────────────────────┐
│   Master Supabase Auth  │ ◄─── Customer authentication
└────────┬────────────────┘
         │ JWT
         ▼
┌─────────────────────────┐
│  Customer Portal/App    │
└─────────────────────────┘


┌─────────────────┐
│   Admin User    │
└────────┬────────┘
         │ Login
         ▼
┌──────────────────────────┐
│  Admin Auth Supabase     │ ◄─── Admin authentication (separate)
└────────┬─────────────────┘
         │ JWT
         ▼
┌─────────────────────────┐
│    Admin Portal         │
└────────┬────────────────┘
         │ API calls with JWT
         ▼
┌─────────────────────────┐
│    MASTERBACKEND        │
│  - Verify JWT (Admin)   │
│  - Query Master Supabase│
└────────┬────────────────┘
         │ Service Key
         ▼
┌─────────────────────────┐
│   Master Supabase DB    │ ◄─── Customer data
│  - Companies            │
│  - Deployments          │
│  - Users                │
└─────────────────────────┘
```

## Key Points

1. **Two completely separate auth systems**
2. **Customers use Master Supabase auth** → company portals
3. **Admins use Admin Auth Supabase** → admin portal
4. **No overlap** - customers cannot become admins, admins cannot login as customers
5. **MASTERBACKEND is the bridge** - verifies admin JWT, queries customer data
