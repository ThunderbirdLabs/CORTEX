# CORTEX Master Control Plane - Backend API

Backend API for managing all CORTEX company deployments.

## Features

- Master admin authentication (email + password, bcrypt)
- Session management with tokens (8-hour expiry)
- Companies CRUD (create, read, update, delete)
- Schemas CRUD (add/remove custom entities per company)
- Deployments management (store/view credentials)
- Team members management
- Dashboard statistics
- Audit logging (all actions tracked)

## Endpoints

### Authentication
- `POST /auth/login` - Login (returns session token)
- `POST /auth/logout` - Logout (invalidates token)

### Companies
- `GET /companies` - List all companies
- `GET /companies/{id}` - Get company details
- `POST /companies` - Create new company
- `PATCH /companies/{id}` - Update company
- `DELETE /companies/{id}` - Soft delete company

### Schemas
- `GET /schemas/{company_id}` - List custom schemas
- `POST /schemas` - Add custom schema (entity/relation)
- `DELETE /schemas/{id}` - Deactivate schema

### Deployments
- `GET /deployments/{company_id}` - Get deployment config
- `POST /deployments` - Store deployment credentials

### Team Members
- `GET /team-members/{company_id}` - List team members
- `POST /team-members` - Add team member

### Stats
- `GET /stats` - Dashboard statistics
- `GET /health` - Health check

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export MASTER_SUPABASE_URL="https://frkquqpbnczafibjsvmd.supabase.co"
export MASTER_SUPABASE_SERVICE_KEY="your_service_key"

# Run server
uvicorn main:app --reload --port 8000

# Open http://localhost:8000/docs for API docs
```

## Deploy to Render

1. Create new Web Service
2. Connect this directory
3. Set environment variables:
   - `MASTER_SUPABASE_URL`
   - `MASTER_SUPABASE_SERVICE_KEY`
4. Deploy!

## Authentication Flow

1. Frontend sends `POST /auth/login` with email + password
2. Backend verifies password (bcrypt)
3. Backend creates session token, stores in `master_admin_sessions`
4. Backend returns token to frontend
5. Frontend stores token in localStorage
6. Frontend sends token in `Authorization` header for all requests
7. Backend verifies token on each request via `get_current_admin` dependency

## Permissions

Master admins have role-based permissions:
- `can_create_companies` - Create new companies
- `can_delete_companies` - Delete companies
- `can_view_schemas` - View custom schemas
- `can_edit_schemas` - Add/remove custom schemas
- `can_view_deployments` - View deployment credentials
- `can_edit_deployments` - Edit deployment credentials

## Security

- Passwords hashed with bcrypt
- Session tokens are 32-byte secure random strings
- Sessions expire after 8 hours
- CORS enabled (configure allowed origins in production)
- All sensitive actions logged to `audit_log_global`
