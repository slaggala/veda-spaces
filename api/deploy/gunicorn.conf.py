# Exactly ONE worker process (OPS-010, F-09): the in-process rate limiter, idempotency
# store, permission cache and Argon2 semaphore are authoritative only in a single process.
bind = "0.0.0.0:8000"
workers = 1
worker_class = "gthread"
threads = 8
timeout = 30
graceful_timeout = 20
accesslog = None  # request logs are structured JSON from the app (02 §9)
