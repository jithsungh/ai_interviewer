# Admin Persistence Layer Testing Guide

## Integration Tests (Real Database)

```python
# tests/integration/admin/persistence/test_template_repository.py

def test_create_template(db_session):
    """Repository creates template in database"""
    repo = TemplateRepository(db_session)
    template = repo.create(TEMPLATE_DATA)
    db_session.commit()
    assert template.id is not None

def test_multi_tenancy_filtering(db_session):
    """Templates scoped to organization"""
    # Create template for Org A
    # Query as Org B
    # Assert empty result
```

---

## Query Performance Tests

```python
def test_template_list_query_performance(db_session, benchmark):
    """List query completes in <100ms"""
    result = benchmark(lambda: repo.list(org_id=1))
    assert len(result) > 0
```

Run: `pytest tests/integration/admin/persistence/ --benchmark-only`
