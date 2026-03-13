---
name: debugging
description: Debugging strategies, diagnostic steps, and common issues
tags: [debugging, troubleshooting, profiling]
auto_load: false
---

# Debugging Best Practices

## Debugging Mindset

### Scientific Method
1. **Observe** - What is the actual behavior?
2. **Hypothesize** - What could cause this?
3. **Test** - How can I verify my hypothesis?
4. **Iterate** - Refine based on results

### Common Mistakes
- Guessing without evidence
- Changing multiple things at once
- Not reading error messages carefully
- Assuming the bug is in complex code (often it's simple)

## Reading Error Messages

### Anatomy of a Stack Trace
```
Traceback (most recent call last):
  File "app.py", line 42, in process_data
    result = calculate(value)
  File "utils.py", line 15, in calculate
    return value / divisor
ZeroDivisionError: division by zero
```

**Read bottom-up:**
1. Error type: `ZeroDivisionError`
2. Location: `utils.py`, line 15
3. Context: Called from `app.py`, line 42

### Key Information
- **Error type** - What went wrong
- **Error message** - Why it went wrong
- **File and line** - Where it went wrong
- **Call stack** - How we got there

## Debugging Techniques

### 1. Print Debugging (Quick & Dirty)
```python
def calculate_discount(price, user_type):
    print(f"DEBUG: price={price}, user_type={user_type}")

    if user_type == "premium":
        discount = 0.2
    else:
        discount = 0.1

    result = price * (1 - discount)
    print(f"DEBUG: discount={discount}, result={result}")
    return result
```

**Pros:** Fast, no tools needed
**Cons:** Clutters code, easy to forget to remove

### 2. Logging (Production-Ready)
```python
import logging

logger = logging.getLogger(__name__)

def process_order(order_id):
    logger.info(f"Processing order {order_id}")

    try:
        order = fetch_order(order_id)
        logger.debug(f"Order data: {order}")

        result = validate_order(order)
        logger.info(f"Order {order_id} validated: {result}")

    except Exception as e:
        logger.error(f"Failed to process order {order_id}", exc_info=True)
        raise
```

**Log Levels:**
- DEBUG - Detailed diagnostic info
- INFO - General informational messages
- WARNING - Something unexpected but handled
- ERROR - Error occurred, operation failed
- CRITICAL - Serious error, system may crash

### 3. Debugger (Interactive)

**Python (pdb)**
```python
import pdb

def buggy_function(data):
    pdb.set_trace()  # Breakpoint here
    result = process(data)
    return result
```

**Commands:**
- `n` (next) - Execute next line
- `s` (step) - Step into function
- `c` (continue) - Continue execution
- `p variable` - Print variable value
- `l` - List source code
- `q` - Quit debugger

**JavaScript (Node.js)**
```javascript
node inspect app.js

// In code:
debugger;  // Breakpoint
```

### 4. Binary Search (Isolate the Problem)
```python
# Comment out half the code
# Does the bug still occur?
# If yes: bug is in remaining half
# If no: bug is in commented half
# Repeat until you find the line
```

### 5. Rubber Duck Debugging
Explain your code line-by-line to a rubber duck (or colleague). Often you'll spot the bug while explaining.

## Common Bug Patterns

### 1. Off-by-One Errors
```python
# Bug: Misses last element
for i in range(len(items) - 1):
    process(items[i])

# Fix:
for i in range(len(items)):
    process(items[i])

# Better:
for item in items:
    process(item)
```

### 2. Mutable Default Arguments
```python
# Bug: List is shared across calls
def add_item(item, items=[]):
    items.append(item)
    return items

# Fix:
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

### 3. Variable Scope Issues
```python
# Bug: Closure captures reference, not value
callbacks = []
for i in range(3):
    callbacks.append(lambda: print(i))

for cb in callbacks:
    cb()  # Prints: 2, 2, 2

# Fix: Capture value explicitly
callbacks = []
for i in range(3):
    callbacks.append(lambda i=i: print(i))

for cb in callbacks:
    cb()  # Prints: 0, 1, 2
```

### 4. Race Conditions
```python
# Bug: Multiple threads access shared state
counter = 0

def increment():
    global counter
    counter += 1  # Not atomic!

# Fix: Use locks
import threading

counter = 0
lock = threading.Lock()

def increment():
    global counter
    with lock:
        counter += 1
```

### 5. Null/None Pointer Errors
```python
# Bug: Assuming value exists
user = get_user(user_id)
print(user.name)  # Crashes if user is None

# Fix: Check first
user = get_user(user_id)
if user:
    print(user.name)
else:
    print("User not found")
```

## Performance Debugging

### Profiling (Python)
```python
import cProfile
import pstats

# Profile a function
cProfile.run('slow_function()', 'profile_stats')

# Analyze results
stats = pstats.Stats('profile_stats')
stats.sort_stats('cumulative')
stats.print_stats(10)  # Top 10 slowest
```

### Memory Profiling
```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    large_list = [i for i in range(1000000)]
    return sum(large_list)
```

### Common Performance Issues
1. **N+1 Queries** - Database query in loop
2. **Unnecessary Copies** - Copying large data structures
3. **Inefficient Algorithms** - O(n²) when O(n log n) exists
4. **Memory Leaks** - Objects not garbage collected

## Debugging Checklist

### When You're Stuck
- [ ] Read the error message carefully
- [ ] Check recent changes (git diff)
- [ ] Verify assumptions (print/log values)
- [ ] Simplify - Remove complexity until it works
- [ ] Search error message online
- [ ] Check documentation
- [ ] Ask for help (with context)

### Before Asking for Help
1. **Minimal reproducible example** - Simplest code that shows the bug
2. **What you expected** - Desired behavior
3. **What actually happened** - Actual behavior
4. **What you tried** - Steps taken to debug
5. **Environment** - OS, language version, dependencies

## Tools

### Python
- **pdb** - Built-in debugger
- **ipdb** - IPython debugger (better interface)
- **pytest** - Test framework with good error messages
- **logging** - Standard logging library

### JavaScript
- **Chrome DevTools** - Browser debugger
- **Node.js Inspector** - Server-side debugging
- **console.log** - Quick debugging
- **debugger** statement - Breakpoint

### General
- **Git bisect** - Find commit that introduced bug
- **Wireshark** - Network traffic analysis
- **strace/ltrace** - System call tracing (Linux)

## Prevention

### Write Defensive Code
```python
def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
```

### Use Type Hints
```python
def process_user(user_id: int) -> User:
    # Type checker catches wrong types
    return get_user(user_id)
```

### Add Assertions
```python
def calculate_discount(price):
    assert price >= 0, "Price cannot be negative"
    return price * 0.1
```

### Write Tests
- Catch bugs before production
- Prevent regressions
- Document expected behavior
