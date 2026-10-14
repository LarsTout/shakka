"""Pure domain logic.

Rule: modules in this package do no I/O, read no clock and use no randomness. They may import
only the standard library (minus I/O modules), pydantic, astral and shakka.domain itself.
Enforced by tests/test_domain_purity.py.
"""
