"""Estimator outbox and audit wiring. The lead notification carries the estimate summary (crm/leads/events.py); no
estimator event is sent to customers. The app and the CLI import this module so that the registration stays explicit."""
