# Data Retention

Suggested defaults:

- Orders, payments, and access grants: retain while needed for purchase support, disputes, refunds, and accounting.
- Provider event IDs: retain long enough to guarantee webhook idempotency and support dispute review.
- Delivery token rows: prune expired tokens after 30 days unless under investigation.
- Delivery redemption metadata: delete or anonymize after 30-90 days.
- Backups: retain 14-30 days by default and keep mode `600`.

Do not keep raw webhook request bodies or production logs in the repository.
