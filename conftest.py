"""
conftest.py — pytest configuration hook.

Its mere presence at the repository root makes pytest add this directory to
sys.path, so tests can `import src...` regardless of the directory pytest is
invoked from. No fixtures are needed; the system is pure and deterministic.
"""
