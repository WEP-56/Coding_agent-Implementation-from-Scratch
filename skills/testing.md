---
name: testing
description: Test strategies, framework selection, and best practices
tags: [testing, quality, tdd]
auto_load: false
---

# Testing Best Practices

## Test Pyramid

```
        /\
       /  \  E2E Tests (Few)
      /____\
     /      \
    / Integration \ (Some)
   /____________\
  /              \
 /  Unit Tests    \ (Many)
/__________________\
```

### Unit Tests (70%)
- Test individual functions/classes in isolation
- Fast execution (< 1ms per test)
- No external dependencies (mock everything)
- High coverage (80%+ for critical code)

### Integration Tests (20%)
- Test component interactions
- Use real dependencies (database, APIs)
- Slower but more realistic
- Focus on critical paths

### E2E Tests (10%)
- Test full user workflows
- Slowest, most brittle
- Only for critical user journeys
- Keep minimal

## Framework Selection

### Python
- **pytest** (recommended) - Simple, powerful, great plugins
- unittest - Built-in, verbose, Java-style
- nose2 - Legacy, use pytest instead

### JavaScript/TypeScript
- **Vitest** (recommended) - Fast, modern, Vite-compatible
- Jest - Popular, slower, more mature
- Mocha + Chai - Flexible, requires more setup

### Go
- **testing** (built-in) - Simple, fast, no dependencies
- testify - Assertions and mocking

## Test Structure

### AAA Pattern (Arrange-Act-Assert)
```python
def test_user_registration():
    # Arrange - Set up test data
    user_data = {"email": "test@example.com", "password": "secure123"}

    # Act - Execute the code under test
    result = register_user(user_data)

    # Assert - Verify the outcome
    assert result.success is True
    assert result.user.email == "test@example.com"
```

### Given-When-Then (BDD style)
```python
def test_shopping_cart_checkout():
    # Given a cart with items
    cart = ShoppingCart()
    cart.add_item(Item("Book", price=10))

    # When checking out
    order = cart.checkout()

    # Then order is created with correct total
    assert order.total == 10
    assert order.status == "pending"
```

## Mocking Strategies

### When to Mock
- External APIs (network calls)
- Database queries (in unit tests)
- File system operations
- Time-dependent code (datetime.now())
- Random number generation

### When NOT to Mock
- Simple data structures
- Pure functions
- Your own code (in integration tests)
- Standard library (unless I/O)

### Python Example
```python
from unittest.mock import Mock, patch

def test_fetch_user_data():
    # Mock external API
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {"id": 1, "name": "Alice"}

        result = fetch_user_data(user_id=1)

        assert result["name"] == "Alice"
        mock_get.assert_called_once_with("https://api.example.com/users/1")
```

## Test Naming

### Convention
```
test_<function>_<scenario>_<expected_result>
```

### Examples
- `test_register_user_with_valid_data_creates_user`
- `test_register_user_with_duplicate_email_raises_error`
- `test_calculate_discount_for_premium_user_returns_20_percent`

### Be Descriptive
- Good: `test_login_fails_when_password_is_incorrect`
- Bad: `test_login_error`

## Coverage Goals

### Target Coverage
- **Critical code**: 90%+ (auth, payments, data integrity)
- **Business logic**: 80%+
- **Utilities**: 70%+
- **UI/Glue code**: 50%+

### Coverage ≠ Quality
- 100% coverage doesn't mean bug-free
- Focus on **meaningful** tests, not just coverage numbers
- Test edge cases and error paths

## Test Data Management

### Fixtures (pytest)
```python
@pytest.fixture
def sample_user():
    return User(email="test@example.com", name="Test User")

def test_user_profile(sample_user):
    assert sample_user.email == "test@example.com"
```

### Factory Pattern
```python
class UserFactory:
    @staticmethod
    def create(email="test@example.com", **kwargs):
        return User(email=email, **kwargs)

def test_user_creation():
    user = UserFactory.create(name="Alice")
    assert user.name == "Alice"
```

## Common Pitfalls

1. **Flaky Tests** - Tests that randomly fail
   - Avoid: time.sleep(), random data, shared state
   - Use: deterministic data, proper cleanup

2. **Slow Tests** - Test suite takes too long
   - Avoid: unnecessary I/O, large datasets
   - Use: mocks, parallel execution, test selection

3. **Brittle Tests** - Break on minor changes
   - Avoid: testing implementation details
   - Use: test behavior, not internals

4. **Test Interdependence** - Tests depend on each other
   - Avoid: shared state, execution order
   - Use: isolated tests, fresh fixtures

## Test-Driven Development (TDD)

### Red-Green-Refactor Cycle
1. **Red** - Write failing test
2. **Green** - Write minimal code to pass
3. **Refactor** - Improve code quality

### Benefits
- Better design (testable code is good code)
- Fewer bugs (tests written first)
- Living documentation (tests show usage)

### When to Use TDD
- Complex algorithms
- Critical business logic
- Bug fixes (write test first)

### When to Skip TDD
- Prototyping/exploration
- Simple CRUD operations
- UI layout (use manual testing)

## Running Tests

### pytest Commands
```bash
# Run all tests
pytest

# Run specific file
pytest tests/test_user.py

# Run specific test
pytest tests/test_user.py::test_registration

# Run with coverage
pytest --cov=myapp --cov-report=html

# Run in parallel
pytest -n auto

# Run only failed tests
pytest --lf
```

### Continuous Integration
- Run tests on every commit
- Block merge if tests fail
- Track coverage trends
- Run different test suites (unit, integration, e2e)
