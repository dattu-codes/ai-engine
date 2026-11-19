import os

# Ensure tests run in development mode by default if APP_ENVIRONMENT is unset
if not os.environ.get("APP_ENVIRONMENT"):
    os.environ["APP_ENVIRONMENT"] = "development"
