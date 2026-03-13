---
name: code-review
description: Code review checklist, security, performance, and best practices
tags: [code-review, security, quality]
auto_load: false
---

# Code Review Best Practices

## Review Mindset

### Goals
1. **Catch bugs** before production
2. **Share knowledge** across team
3. **Maintain consistency** in codebase
4. **Improve code quality** over time

### Principles
- Be kind and constructive
- Assume good intent
- Ask questions, don't demand changes
- Praise good code
- Focus on the code, not the person

## Review Checklist

### 1. Functionality
- [ ] Does the code do what it's supposed to?
- [ ] Are edge cases handled?
- [ ] Are error cases handled gracefully?
- [ ] Is the logic correct?

### 2. Security
- [ ] No SQL injection vulnerabilities
- [ ] No XSS (Cross-Site Scripting) vulnerabilities
- [ ] No CSRF (Cross-Site Request Forgery) vulnerabilities
- [ ] Sensitive data not logged or exposed
- [ ] Authentication/authorization checks present
- [ ] Input validation on all user inputs
- [ ] No hardcoded secrets or credentials

### 3. Performance
- [ ] No N+1 query problems
- [ ] Appropriate use of caching
- [ ] No unnecessary database queries
- [ ] Efficient algorithms (avoid O(n²) when possible)
- [ ] No memory leaks
- [ ] Proper resource cleanup (files, connections)

### 4. Code Quality
- [ ] Clear and descriptive names
- [ ] Functions are small and focused
- [ ] No code duplication (DRY principle)
- [ ] Appropriate comments (why, not what)
- [ ] Consistent with codebase style
- [ ] No dead code or commented-out code

### 5. Testing
- [ ] Tests cover new functionality
- [ ] Tests cover edge cases
- [ ] Tests are readable and maintainable
- [ ] No flaky tests
- [ ] Tests run fast

### 6. Documentation
- [ ] Public APIs documented
- [ ] Complex logic explained
- [ ] README updated if needed
- [ ] Breaking changes noted

## Security Vulnerabilities

### SQL Injection
```python
# BAD: String concatenation
query = f"SELECT * FROM users WHERE id = {user_id}"

# GOOD: Parameterized query
query = "SELECT * FROM users WHERE id = ?"
cursor.execute(query, (user_id,))
```

### XSS (Cross-Site Scripting)
```javascript
// BAD: Direct HTML insertion
element.innerHTML = userInput;

// GOOD: Text content or sanitization
element.textContent = userInput;
// OR
element.innerHTML = DOMPurify.sanitize(userInput);
```

### Path Traversal
```python
# BAD: User controls file path
file_path = f"/uploads/{user_filename}"
with open(file_path) as f:
    content = f.read()

# GOOD: Validate and sanitize
import os
safe_filename = os.path.basename(user_filename)
file_path = os.path.join("/uploads", safe_filename)
if not file_path.startswith("/uploads/"):
    raise ValueError("Invalid file path")
```

### Insecure Deserialization
```python
# BAD: Pickle from untrusted source
import pickle
data = pickle.loads(user_input)

# GOOD: Use JSON or validate source
import json
data = json.loads(user_input)
```

### Hardcoded Secrets
```python
# BAD: Secrets in code
API_KEY = "sk-1234567890abcdef"

# GOOD: Environment variables
import os
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY not set")
```

## Performance Issues

### N+1 Query Problem
```python
# BAD: Query in loop
users = User.query.all()
for user in users:
    posts = Post.query.filter_by(user_id=user.id).all()  # N queries!

# GOOD: Eager loading
users = User.query.options(joinedload(User.posts)).all()
for user in users:
    posts = user.posts  # Already loaded
```

### Unnecessary Copies
```python
# BAD: Copying large data
def process_data(data):
    data_copy = data.copy()  # Expensive!
    return [x * 2 for x in data_copy]

# GOOD: Process in place or use generator
def process_data(data):
    return (x * 2 for x in data)  # Generator, no copy
```

### Inefficient Algorithms
```python
# BAD: O(n²) nested loops
def find_duplicates(items):
    duplicates = []
    for i, item in enumerate(items):
        for j, other in enumerate(items):
            if i != j and item == other:
                duplicates.append(item)
    return duplicates

# GOOD: O(n) with set
def find_duplicates(items):
    seen = set()
    duplicates = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return list(duplicates)
```

## Code Quality Issues

### Poor Naming
```python
# BAD: Unclear names
def f(x, y):
    return x + y

# GOOD: Descriptive names
def calculate_total_price(base_price, tax_amount):
    return base_price + tax_amount
```

### Long Functions
```python
# BAD: 100+ line function doing everything
def process_order(order_data):
    # Validate
    # Calculate totals
    # Apply discounts
    # Process payment
    # Send email
    # Update inventory
    # ... 100 more lines

# GOOD: Extract smaller functions
def process_order(order_data):
    validate_order(order_data)
    total = calculate_order_total(order_data)
    payment = process_payment(total)
    send_confirmation_email(order_data, payment)
    update_inventory(order_data)
```

### Code Duplication
```python
# BAD: Repeated logic
def calculate_employee_bonus(employee):
    if employee.level == "junior":
        return employee.salary * 0.05
    elif employee.level == "senior":
        return employee.salary * 0.10

def calculate_contractor_bonus(contractor):
    if contractor.level == "junior":
        return contractor.rate * 0.05
    elif contractor.level == "senior":
        return contractor.rate * 0.10

# GOOD: Extract common logic
def calculate_bonus(base_amount, level):
    multiplier = 0.05 if level == "junior" else 0.10
    return base_amount * multiplier

def calculate_employee_bonus(employee):
    return calculate_bonus(employee.salary, employee.level)

def calculate_contractor_bonus(contractor):
    return calculate_bonus(contractor.rate, contractor.level)
```

### Magic Numbers
```python
# BAD: Unexplained constants
if user.age > 18 and user.account_balance > 1000:
    approve_loan()

# GOOD: Named constants
MINIMUM_AGE = 18
MINIMUM_BALANCE = 1000

if user.age > MINIMUM_AGE and user.account_balance > MINIMUM_BALANCE:
    approve_loan()
```

## Review Comments

### Good Comments
```
"Could we add a check for empty input here? If `items` is empty,
this will raise an IndexError on line 42."

"Nice use of the strategy pattern here! This makes it easy to add
new payment methods."

"This looks correct, but I'm concerned about performance with large
datasets. Have you considered using a generator instead?"
```

### Bad Comments
```
"This is wrong."  # Not helpful

"Why didn't you use X?"  # Sounds accusatory

"I would have done it differently."  # Not constructive
```

### Comment Templates

**Asking Questions:**
- "Could you explain why...?"
- "What happens if...?"
- "Have you considered...?"

**Suggesting Changes:**
- "What do you think about...?"
- "Could we simplify this by...?"
- "Would it make sense to...?"

**Praising:**
- "Nice solution to..."
- "I like how you..."
- "Great catch on..."

## Review Priorities

### Must Fix (Block Merge)
- Security vulnerabilities
- Data corruption risks
- Breaking changes without migration
- Crashes or critical bugs

### Should Fix (Request Changes)
- Performance issues
- Missing tests for new code
- Poor error handling
- Significant code quality issues

### Nice to Have (Suggestions)
- Minor style inconsistencies
- Opportunities for refactoring
- Documentation improvements
- Non-critical optimizations

## Self-Review Checklist

Before requesting review:
- [ ] Run tests locally (all pass)
- [ ] Run linter/formatter
- [ ] Review your own diff
- [ ] Remove debug code and console.logs
- [ ] Update documentation
- [ ] Add/update tests
- [ ] Check for sensitive data in diff
- [ ] Verify commit messages are clear

## Common Mistakes

### 1. Reviewing Too Much at Once
- Keep PRs small (< 400 lines)
- Review in multiple sessions if needed
- Focus on high-risk areas first

### 2. Nitpicking Style
- Use automated formatters (Black, Prettier)
- Focus on substance over style
- Save style discussions for team guidelines

### 3. Not Testing the Code
- Check out the branch locally
- Run the code
- Try edge cases manually

### 4. Assuming Context
- Ask questions if unclear
- Don't assume intent
- Request clarification

### 5. Being Too Nice
- Don't approve bad code to be polite
- Constructive criticism helps everyone
- It's easier to fix now than later

## Tools

### Automated Checks
- **Linters** - Catch style issues (pylint, eslint)
- **Formatters** - Enforce consistent style (Black, Prettier)
- **Type Checkers** - Catch type errors (mypy, TypeScript)
- **Security Scanners** - Find vulnerabilities (Bandit, npm audit)
- **Test Coverage** - Ensure tests exist (pytest-cov, Istanbul)

### Review Platforms
- GitHub Pull Requests
- GitLab Merge Requests
- Bitbucket Pull Requests
- Gerrit

## Best Practices

1. **Review promptly** - Don't let PRs sit for days
2. **Be thorough but not pedantic** - Focus on important issues
3. **Explain your reasoning** - Help others learn
4. **Approve when ready** - Don't block on minor issues
5. **Follow up** - Check that feedback was addressed
