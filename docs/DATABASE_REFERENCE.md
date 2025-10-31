# Database Reference

## Correct Database Configuration

The Technical Service Assistant uses PostgreSQL with the following configuration:

- **Container Name**: `pgvector`
- **Database Name**: `vector_db` (NOT `postgres` or `technical_service_assistant`)
- **Username**: `postgres`
- **Password**: `postgres`
- **Port**: `5432`

## Connection Examples

### Via Docker CLI
```bash
# Correct way to connect
docker exec -it pgvector psql -U postgres -d vector_db

# List tables
docker exec -it pgvector psql -U postgres -d vector_db -c "\dt"

# Query users
docker exec -it pgvector psql -U postgres -d vector_db -c "SELECT * FROM users;"
```

### Via Application Code
The application uses the configuration from `config.py`:
```python
from config import get_settings
settings = get_settings()
# settings.db_name will be "vector_db"
```

## Key Tables

- `users` - User accounts and authentication
- `roles` - User roles (admin, employee, guest)
- `document_chunks` - Processed document content with embeddings
- `audit_logs` - Security and system audit trail
- `verification_tokens` - Email verification tokens

## Common Mistakes to Avoid

❌ **Wrong database name**: Don't use `postgres` or `technical_service_assistant`
✅ **Correct database name**: Always use `vector_db`

❌ **Wrong connection**: `psql -U postgres -d postgres`
✅ **Correct connection**: `psql -U postgres -d vector_db`
