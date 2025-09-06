# SyncScope Monitoring Service

Real-time developer activity monitoring and metrics collection service for the SyncScope developer productivity platform.

## Overview

The Monitoring Service is a core component of SyncScope that captures and processes developer activities in real-time. It provides comprehensive tracking of coding sessions, activity logs, code metrics, and Git events to power productivity insights and analytics across the platform.

## Features

- 🔍 **Real-time Activity Monitoring**: Track developer actions like file opens, edits, saves, and debugging
- 📊 **Code Metrics Collection**: Gather lines of code, complexity metrics, and quality indicators
- 🔄 **Git Event Tracking**: Monitor commits, pushes, pulls, merges, and repository interactions
- ⏱️ **Session Management**: Track coding sessions with IDE and project context
- 📈 **Bulk Data Processing**: Optimized endpoints for high-volume data ingestion
- 🛡️ **JWT Authentication**: Secure integration with SyncScope Auth Service
- 🚀 **Performance Optimized**: Redis caching and serverless-ready architecture
- 📋 **Health Monitoring**: Comprehensive health checks and monitoring endpoints
- 🐳 **Docker Support**: Containerized deployment ready
- 🧪 **Comprehensive Testing**: Full test suite with performance benchmarks

## Architecture & Service Integration

SyncScope Monitoring Service integrates seamlessly with the SyncScope microservices ecosystem:

### **Core Integration Points**

#### **← syncscope-auth-service** (Authentication Provider)
- **Purpose**: Provides JWT authentication and user context
- **Integration**: Monitoring Service validates all requests through Auth Service
- **Authentication Flow**: 
  - Receives JWT tokens from client applications
  - Validates tokens with Auth Service `/auth/verify-token` endpoint
  - Associates activities with authenticated users
- **Data Flow**: User and company context drives activity association and filtering

#### **→ syncscope-analytics-service** (Data Consumer)
- **Purpose**: Consumes monitoring data to generate insights and KPIs
- **Integration**: Analytics Service queries monitoring data for report generation
- **Data Flow**: 
  - Monitoring Service provides activity, session, and metrics data
  - Analytics Service aggregates data for performance insights
  - Real-time and historical data analysis

#### **→ syncscope-management-service** (Project Context)
- **Purpose**: Provides project and team context for activity association
- **Integration**: Links monitoring data with project management structures
- **Data Flow**: 
  - Activities are associated with projects and teams
  - Project-level metrics and team productivity insights
  - Integration setup and configuration management

#### **→ syncscope-alerts-service** (Event Triggering)
- **Purpose**: Receives activity events for alert rule evaluation
- **Integration**: Sends activity events to trigger productivity alerts
- **Data Flow**:
  - Real-time activity events trigger alert evaluations
  - Threshold-based alerts for activity patterns
  - Custom alert rules based on monitoring data

#### **← syncscope-agent** (Data Source)
- **Purpose**: SyncScope agent installed in developer IDEs
- **Integration**: Primary source of monitoring data
- **Data Flow**:
  - Agent collects IDE activities and sends to monitoring service
  - Session start/end events with context
  - Bulk activity uploads for performance optimization

#### **← Developer IDEs** (Direct Integration)
- **Purpose**: Direct integration with VS Code, IntelliJ, etc.
- **Integration**: IDE extensions send activity data directly
- **Supported IDEs**: VS Code, IntelliJ IDEA, PyCharm, WebStorm, Visual Studio
- **Data Types**: File operations, debugging sessions, test runs, Git operations

### **Database Schema Integration**

The Monitoring Service operates within the shared SyncScope database:

- **`monitoring` schema**: Primary ownership of all monitoring-related data
  - `developer_sessions`: Coding session tracking
  - `activity_logs`: Individual developer activities  
  - `code_metrics`: Code quality and complexity metrics
  - `git_events`: Git operation tracking
- **`auth` schema**: Read access for user and company context (owned by Auth Service)
- **`management` schema**: Read access for project associations (used by Management Service)

## Quick Start

### 1. Environment Setup

```bash
# Clone and setup
git clone <repo-url>
cd syncscope-monitoring-service

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database credentials and service URLs
```

### 2. Database Setup

```bash
# Create monitoring schema and run migrations
python manage.py migrate

# Create superuser for admin access (optional)
python manage.py createsuperuser

# Verify setup
python manage.py check --deploy
```

### 3. Run the Service

```bash
# Development
python manage.py runserver 0.0.0.0:8002

# Production with Gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:8002

# Docker deployment
docker-compose up --build

# Health check
curl http://localhost:8002/health/
```

### 4. Integration with Other Services

Configure the monitoring service to work with other SyncScope services:

```bash
# Set service URLs in environment
export AUTH_SERVICE_URL=http://localhost:8000
export ANALYTICS_SERVICE_URL=http://localhost:8003
export MANAGEMENT_SERVICE_URL=http://localhost:8001
export ALERTS_SERVICE_URL=http://localhost:8004

# JWT configuration (must match Auth Service)
export JWT_SECRET_KEY=your-shared-jwt-secret
```

## Client Integration

### SyncScope Agent Integration

The SyncScope Agent is the primary way to integrate with the monitoring service:

```bash
# Install SyncScope Agent
npm install -g syncscope-agent

# Configure agent
syncscope config set monitoring-url http://localhost:8002
syncscope config set auth-token your-jwt-token

# Start monitoring
syncscope start
```

### Direct IDE Integration

For custom IDE integrations, use the monitoring service APIs directly:

#### 1. Authentication
```javascript
// Obtain JWT token from Auth Service
const authResponse = await fetch('http://localhost:8000/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
});
const { access_token } = await authResponse.json();
```

#### 2. Start Monitoring Session
```javascript
// Start a new monitoring session
const sessionResponse = await fetch('http://localhost:8002/monitoring/sessions/start', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${access_token}`,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        ide_name: 'VS Code',
        ide_version: '1.85.0',
        project_path: '/path/to/project',
        project_name: 'my-project',
        branch_name: 'main'
    })
});
const { session_id } = await sessionResponse.json();
```

#### 3. Send Activity Data
```javascript
// Send individual activities
await fetch('http://localhost:8002/monitoring/activities/', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${access_token}`,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        session_id,
        activity_type: 'file_edit',
        file_path: '/src/main.js',
        timestamp: new Date().toISOString(),
        details: { lines_changed: 5 }
    })
});

// Or send bulk activities for better performance
await fetch('http://localhost:8002/monitoring/activities/bulk/', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${access_token}`,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        activities: [
            {
                session_id,
                activity_type: 'file_open',
                file_path: '/src/utils.js',
                timestamp: '2024-01-01T10:00:00Z'
            },
            {
                session_id,
                activity_type: 'file_edit',
                file_path: '/src/utils.js',
                timestamp: '2024-01-01T10:01:00Z',
                details: { lines_changed: 3 }
            }
            // ... more activities
        ]
    })
});
```

#### 4. Send Code Metrics
```javascript
// Submit code metrics
await fetch('http://localhost:8002/monitoring/metrics/code/', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${access_token}`,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        session_id,
        file_path: '/src/main.js',
        lines_of_code: 150,
        cyclomatic_complexity: 8,
        test_coverage: 85.5,
        code_smells: 2,
        technical_debt: 30
    })
});
```

#### 5. Track Git Events
```javascript
// Record Git operations
await fetch('http://localhost:8002/monitoring/events/git/', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${access_token}`,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        session_id,
        event_type: 'commit',
        repository_url: 'https://github.com/company/project',
        branch_name: 'feature/new-feature',
        commit_hash: 'abc123def456',
        commit_message: 'Add new feature implementation',
        files_changed: 5,
        insertions: 120,
        deletions: 45
    })
});
```

#### 6. End Session
```javascript
// End monitoring session
await fetch(`http://localhost:8002/monitoring/sessions/${session_id}/end`, {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${access_token}`,
        'Content-Type': 'application/json'
    }
});
```

## API Endpoints

### Session Management
- `POST /monitoring/sessions/start` - Start new monitoring session
- `POST /monitoring/sessions/{id}/end` - End monitoring session  
- `GET /monitoring/sessions/` - Get user's active and recent sessions
- `GET /monitoring/sessions/{id}/stats` - Get session statistics

### Activity Tracking
- `POST /monitoring/activities/` - Record single activity
- `POST /monitoring/activities/bulk/` - Record multiple activities (recommended for performance)
- `GET /monitoring/activities/` - Get user's recent activities

### Code Metrics
- `POST /monitoring/metrics/code/` - Submit code quality metrics
- `GET /monitoring/metrics/` - Get code metrics for analysis

### Git Events
- `POST /monitoring/events/git/` - Record Git operation
- `GET /monitoring/events/git/` - Get Git event history

### Health & Monitoring
- `GET /health/` - Basic health check
- `GET /health/ready/` - Readiness probe (database connectivity)
- `GET /health/live/` - Liveness probe (service availability)

### **Service-to-Service Endpoints**

These endpoints are used by other SyncScope services:

- `GET /monitoring/sessions/user/{user_id}` - Get sessions for specific user (Analytics Service)
- `GET /monitoring/activities/project/{project_id}` - Get project activities (Management Service)
- `POST /monitoring/webhooks/alerts` - Webhook for alert service integration
- `GET /monitoring/metrics/dashboard/{company_id}` - Company-wide metrics (Frontend)

## Environment Configuration

### Development Environment

```env
# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/syncscope
DB_NAME=syncscope
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# Redis for caching and session management
REDIS_URL=redis://localhost:6379/1

# Service Integration URLs
AUTH_SERVICE_URL=http://localhost:8000
ANALYTICS_SERVICE_URL=http://localhost:8003
MANAGEMENT_SERVICE_URL=http://localhost:8001
ALERTS_SERVICE_URL=http://localhost:8004

# JWT Configuration (must match Auth Service)
JWT_SECRET_KEY=your-shared-jwt-secret

# Security
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Rate Limiting
RATELIMIT_ENABLE=True

# Logging Level
ENVIRONMENT=development
```

### Production Environment

```env
# Database (Railway/Production PostgreSQL)
DATABASE_URL=postgresql://production-db-url

# Redis Cache
REDIS_URL=redis://production-redis-url

# Service URLs (adjust for your infrastructure)
AUTH_SERVICE_URL=https://auth.syncscope.internal
ANALYTICS_SERVICE_URL=https://analytics.syncscope.internal
MANAGEMENT_SERVICE_URL=https://management.syncscope.internal
ALERTS_SERVICE_URL=https://alerts.syncscope.internal

# Security Settings
DEBUG=False
SECRET_KEY=secure-production-key
ALLOWED_HOSTS=monitoring.syncscope.com,api-gateway-url

# JWT Configuration
JWT_SECRET_KEY=production-jwt-secret

# Performance
CONN_MAX_AGE=0  # Serverless optimization
DB_CONNECT_TIMEOUT=10

# Rate Limiting
RATELIMIT_ENABLE=True

# Logging
ENVIRONMENT=production
```

## Data Models

### DeveloperSession
Tracks individual coding sessions with context:

```python
{
    "id": "uuid",
    "user": "user_id",
    "start_time": "2024-01-01T09:00:00Z",
    "end_time": "2024-01-01T17:00:00Z",
    "ide_name": "VS Code",
    "ide_version": "1.85.0",
    "project_name": "syncscope-frontend",
    "project_path": "/path/to/project",
    "branch_name": "feature/dashboard",
    "is_active": false,
    "total_activities": 245,
    "files_touched": 12
}
```

### ActivityLog
Individual developer activities during sessions:

```python
{
    "id": "uuid",
    "session": "session_id",
    "activity_type": "file_edit",  # file_open, file_edit, file_save, debug_start, etc.
    "timestamp": "2024-01-01T09:15:30Z",
    "file_path": "/src/components/Dashboard.tsx",
    "file_type": "typescript",
    "details": {
        "lines_changed": 5,
        "characters_typed": 127
    }
}
```

### CodeMetrics
Code quality and complexity measurements:

```python
{
    "id": "uuid",
    "session": "session_id",
    "file_path": "/src/components/Dashboard.tsx",
    "timestamp": "2024-01-01T09:30:00Z",
    "lines_of_code": 150,
    "cyclomatic_complexity": 8,
    "test_coverage": 85.5,
    "code_smells": 2,
    "technical_debt": 30,  # minutes
    "maintainability_index": 75.2
}
```

### GitEvent
Git operations and repository interactions:

```python
{
    "id": "uuid",
    "session": "session_id",
    "event_type": "commit",  # commit, push, pull, merge, branch, etc.
    "timestamp": "2024-01-01T10:00:00Z",
    "repository_url": "https://github.com/company/project",
    "branch_name": "feature/dashboard",
    "commit_hash": "abc123def456",
    "commit_message": "Add dashboard components",
    "files_changed": 5,
    "insertions": 120,
    "deletions": 45
}
```

## Rate Limiting

The monitoring service implements rate limiting to protect against abuse:

- **Sessions**: 50 requests per hour per user
- **Activities**: 200 requests per hour per user (500 for bulk endpoint)
- **Metrics**: 100 requests per hour per user
- **Git Events**: 100 requests per hour per user
- **Health Checks**: 1000 requests per hour (no authentication required)

Rate limits are implemented using Redis and return appropriate headers:
```
X-RateLimit-Limit: 200
X-RateLimit-Remaining: 195
X-RateLimit-Reset: 1640995200
```

## Caching Strategy

Redis is used for performance optimization:

- **Session Data**: Active sessions cached for 1 hour
- **User Context**: JWT token validation results cached for 15 minutes
- **Health Checks**: Database health status cached for 5 minutes
- **Rate Limiting**: Request counts and windows

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
.venv/Scripts/python -m pytest tests/ -v --ds=config.settings

# Run specific test categories
.venv/Scripts/python -m pytest tests/test_models.py -v --ds=config.settings
.venv/Scripts/python -m pytest tests/test_sessions.py -v --ds=config.settings
.venv/Scripts/python -m pytest tests/test_activities.py -v --ds=config.settings
.venv/Scripts/python -m pytest tests/test_metrics.py -v --ds=config.settings

# Performance tests
.venv/Scripts/python -m pytest tests/test_performance.py -v --ds=config.settings

# Integration tests with other services
.venv/Scripts/python -m pytest tests/test_integration.py -v --ds=config.settings

# With coverage reporting
.venv/Scripts/python -m pytest tests/ --cov=apps --cov-report=html --ds=config.settings
```

### Test Coverage

- **Model Tests**: Complete coverage of all data models and relationships
- **API Tests**: All endpoints with various authentication scenarios
- **Integration Tests**: Service-to-service communication
- **Performance Tests**: Bulk operations and rate limiting
- **Security Tests**: Authentication, authorization, and input validation

## Monitoring & Observability

### Logging

Structured logging is provided for all operations:

```python
# Activity logging
logger.info("Activity recorded", extra={
    "user_id": user.id,
    "session_id": session.id,
    "activity_type": "file_edit",
    "file_path": "/src/main.js"
})

# Performance monitoring
logger.info("Bulk activity processed", extra={
    "user_id": user.id,
    "activity_count": 25,
    "processing_time": 145.2  # milliseconds
})
```

### Health Checks

Monitor service health with comprehensive checks:

```bash
# Database connectivity
curl http://localhost:8002/health/

# Service dependencies
curl http://localhost:8002/health/ready/

# Application health
curl http://localhost:8002/health/live/
```

### Metrics Collection

Key metrics to monitor in production:

- **Request Volume**: Activities, sessions, metrics per minute
- **Response Times**: P50, P95, P99 response times
- **Error Rates**: 4xx, 5xx error percentages
- **Database Performance**: Connection pool usage, query times
- **Cache Hit Rates**: Redis cache effectiveness
- **Service Dependencies**: Auth service response times

## Deployment

### Docker Deployment

```bash
# Development
docker-compose up --build

# Production
docker-compose -f docker-compose.prod.yml up -d

# With specific service configuration
docker run -p 8002:8002 \
  -e DATABASE_URL=postgresql://... \
  -e AUTH_SERVICE_URL=http://auth:8000 \
  syncscope-monitoring-service
```

### Railway Deployment

1. Connect Railway PostgreSQL database
2. Set environment variables for service integration
3. Configure Redis addon for caching
4. Deploy with health check endpoints
5. Set up log aggregation and monitoring

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: monitoring-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: monitoring-service
  template:
    metadata:
      labels:
        app: monitoring-service
    spec:
      containers:
      - name: monitoring-service
        image: syncscope-monitoring-service:latest
        ports:
        - containerPort: 8002
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        - name: AUTH_SERVICE_URL
          value: "http://auth-service:8000"
        livenessProbe:
          httpGet:
            path: /health/live/
            port: 8002
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready/
            port: 8002
          initialDelaySeconds: 5
          periodSeconds: 5
```

## Security

### Authentication & Authorization

- **JWT-based authentication** with Auth Service integration
- **Service-to-service communication** with shared JWT secrets
- **User-level data isolation** - users can only access their own data
- **Company-level aggregation** for administrative features

### Input Validation

- **Request payload validation** using Django REST Framework serializers
- **File path sanitization** to prevent directory traversal
- **SQL injection protection** through Django ORM
- **XSS protection** with Content Security Policy headers

### Security Headers

Comprehensive security headers applied:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'self'` (for API endpoints)

## Troubleshooting

### Common Issues

#### Database Connection Problems
```bash
# Check database health
python manage.py check --database default

# Test database connectivity
python manage.py dbshell

# Run migrations if needed
python manage.py migrate
```

#### Authentication Issues
```bash
# Verify JWT configuration
echo $JWT_SECRET_KEY

# Test auth service connectivity
curl http://localhost:8000/health/

# Check token validation
curl -H "Authorization: Bearer $TOKEN" http://localhost:8002/monitoring/sessions/
```

#### Performance Issues
```bash
# Check Redis connectivity
redis-cli ping

# Monitor database connections
python manage.py shell -c "from django.db import connection; print(connection.queries)"

# Review rate limiting
curl -I http://localhost:8002/monitoring/activities/
```

#### Service Integration Issues

1. **Auth Service Communication**: Verify `AUTH_SERVICE_URL` and JWT secret consistency
2. **Database Schema Access**: Ensure proper permissions for monitoring schema
3. **Rate Limiting**: Check if requests are being throttled
4. **Cache Issues**: Restart Redis or clear cache if stale data

### Debug Mode

Enable debug mode for development troubleshooting:

```bash
export DEBUG=True
export LOGGING_LEVEL=DEBUG
python manage.py runserver 8002
```

## Performance Optimization

### Bulk Operations

Use bulk endpoints for high-volume data:

```javascript
// Instead of individual requests
for (const activity of activities) {
    await fetch('/monitoring/activities/', { ... });  // Slow
}

// Use bulk endpoint
await fetch('/monitoring/activities/bulk/', {
    method: 'POST',
    body: JSON.stringify({ activities })  // Fast
});
```

### Database Optimization

- **Connection pooling** configured for optimal performance
- **Read replicas** support for analytics queries
- **Index optimization** on frequently queried fields
- **Query optimization** with select_related and prefetch_related

### Caching Strategy

- **Redis caching** for frequently accessed data
- **Application-level caching** for expensive computations
- **CDN integration** for static assets
- **Database query caching** for repeated queries

## Contributing

### Development Setup

1. Fork and clone the repository
2. Create virtual environment and install dependencies
3. Configure development environment variables
4. Run tests to ensure everything works
5. Create feature branch for your changes

### Code Style

- **PEP 8** compliance for Python code
- **Black** formatting with line length 120
- **isort** for import organization  
- **Django best practices** for models and views
- **Comprehensive docstrings** for all functions

### Adding New Endpoints

1. **Create serializer** for request/response validation
2. **Implement view** with proper authentication and rate limiting
3. **Add URL pattern** to monitoring app URLs
4. **Write comprehensive tests** covering all scenarios
5. **Update API documentation** and this README
6. **Add monitoring and logging** for the new endpoint

## License

MIT License - see LICENSE file for details.

## Support

For technical support and integration questions:

- **Documentation**: Internal SyncScope documentation
- **Issues**: Create GitHub issues for bugs and feature requests  
- **Integration Support**: Contact the platform team for service integration help
- **Monitoring**: Set up proper observability for production deployments