"""Application layer.

Use cases own orchestration and the transaction boundary. They depend on
repository protocols and on the domain; they know nothing about FastAPI, and a
route never contains a rule.
"""
