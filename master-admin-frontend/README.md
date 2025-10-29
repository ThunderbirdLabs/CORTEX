# CORTEX Master Admin Dashboard

Next.js 14 dashboard for managing all CORTEX company deployments.

## Features

- Master admin authentication (login/logout)
- Dashboard overview with statistics
- Companies management (list, view, create, edit)
- Custom schemas editor (add/remove entity types per company)
- Beautiful dark theme with purple/pink gradients
- Responsive design

## Tech Stack

- **Next.js 14** (App Router)
- **React 18**
- **TypeScript**
- **Tailwind CSS**
- **Lucide Icons**

## Local Development

```bash
# Install dependencies
npm install

# Create .env.local file
cp .env.example .env.local

# Edit .env.local with your master backend URL
# NEXT_PUBLIC_MASTER_API_URL=http://localhost:8000

# Run development server
npm run dev

# Open http://localhost:3001
```

## Deploy to Vercel

### Option 1: Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy
vercel

# Set production env var
vercel env add NEXT_PUBLIC_MASTER_API_URL production
# Enter: https://your-master-backend.onrender.com

# Deploy to production
vercel --prod
```

### Option 2: Vercel Dashboard

1. Go to https://vercel.com/new
2. Import this directory from GitHub
3. Set framework preset: **Next.js**
4. Add environment variable:
   - `NEXT_PUBLIC_MASTER_API_URL` = `https://your-master-backend.onrender.com`
5. Click **Deploy**

## Pages

### `/` - Login Page
- Email + password authentication
- Validates credentials against master backend
- Stores session token in localStorage
- Redirects to `/dashboard` on success

### `/dashboard` - Dashboard Home
- Shows statistics (total companies, active, trial, provisioning)
- Quick action buttons
- Recent activity feed

### `/dashboard/companies` - Companies List
- View all companies with status badges
- Links to frontend/backend deployments
- "Add Company" button (manual provisioning)
- Edit schemas button per company

### `/dashboard/schemas` - Schemas Editor
- Select company from dropdown
- View custom entity types and relationships
- Add new schemas (MACHINE, PRODUCT, etc.)
- Delete schemas
- Requires backend restart to take effect

## API Integration

See [lib/api.ts](lib/api.ts) for the complete API client implementation.

All requests include the session token in the `Authorization` header.

## Authentication Flow

1. User enters email + password on login page
2. Frontend calls `POST /auth/login` on master backend
3. Backend verifies password (bcrypt), creates session token
4. Frontend stores token in localStorage
5. All subsequent requests include token in header
6. Backend validates token via `get_current_admin` dependency
7. Logout clears token from localStorage and invalidates on backend

## Styling

- Dark theme (gray-950 background, gray-900 cards)
- Purple/pink gradient accents
- Hover states and transitions
- Responsive grid layouts
- Lucide React icons

## Environment Variables

- `NEXT_PUBLIC_MASTER_API_URL` - Master backend API URL (required)

## Notes

- Session tokens expire after 8 hours
- Requires master backend to be running
- All actions are logged to `audit_log_global` table
- Schemas changes require backend restart to take effect
