"""Never read production credentials when collecting or running tests."""
import os

# Intentional overwrite: pytest must never inherit the developer's DATABASE_URL.
os.environ["DATABASE_URL"] = "postgresql+psycopg://test:test@127.0.0.1:1/disabled_test_database"
os.environ["MIGRATION_DATABASE_URL"] = ""
os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "false"
os.environ["JWT_SECRET_KEY"] = "test-only-key-not-for-deployment-0123456789abcdef"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["CORS_ORIGINS"] = '["http://localhost:4200"]'
os.environ["DOCS_ENABLED"] = "true"
