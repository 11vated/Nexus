# WORLD-CLASS SKILL: Advanced Debugging & Troubleshooting

## DEBUGGING PHILOSOPHY

> "Debugging is twice as hard as writing the code in the first place." - Brian Kernighan

Your goal: Find the ROOT CAUSE, not just fix symptoms.

---

## SYSTEMATIC DEBUGGING PROCESS

### Step 1: Reproduce
- Can you reproduce the bug consistently?
- What's the exact steps to trigger it?
- What data makes it fail?

### Step 2: Isolate
- Disable code until bug disappears
- Add logging to trace execution
- Use binary search on code changes

### Step 3: Analyze
- Read error messages CAREFULLY
- Check stack traces top-to-bottom
- Look for YOUR code, not framework internals

### Step 4: Hypothesize
- What's the root cause?
- Why does it fail this way?
- What assumptions are wrong?

### Step 5: Fix
- Fix the ROOT CAUSE
- Not just the symptom
- Consider edge cases

### Step 6: Verify
- Does fix work?
- Does it break anything else?
- Can you write a test for it?

---

## COMMON BUGS & FIXES

### JavaScript/TypeScript

#### "Cannot read property of undefined"
```typescript
// PROBLEM
const name = user.profile.name // user.profile might be undefined

// SOLUTION - Optional chaining
const name = user?.profile?.name

// Or with default
const name = user?.profile?.name ?? 'Unknown'
```

#### "Promise is not handled"
```typescript
// PROBLEM
fetchData()

// SOLUTION - Always handle promises
fetchData().catch(err => console.error(err))

// Or use async/await
await fetchData()
```

#### "Stale closure"
```typescript
// PROBLEM
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 100) // Prints 3,3,3
}

// SOLUTION - Use let or closure
for (let i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 100) // Prints 0,1,2
}
```

#### "Memory leak"
```typescript
// PROBLEM - Event listener not cleaned up
useEffect(() => {
  window.addEventListener('resize', handleResize)
  // Missing cleanup!
})

// SOLUTION
useEffect(() => {
  window.addEventListener('resize', handleResize)
  return () => window.removeEventListener('resize', handleResize)
}, [])
```

### React

#### "Too many re-renders"
```typescript
// PROBLEM
const handleClick = () => setCount(count + 1) // Infinite loop!

// SOLUTION - Use callback form
const handleClick = () => setCount(c => c + 1)
```

#### "Stale state"
```typescript
// PROBLEM
const handleClick = () => {
  setTimeout(() => {
    setCount(count + 1) // count is stale!
  }, 1000)
}

// SOLUTION - Use useReducer or ref
const countRef = useRef(count)
const handleClick = () => {
  setTimeout(() => {
    setCount(countRef.current + 1)
  }, 1000)
}
```

### API/Backend

#### "Connection refused"
```bash
# Check if service is running
curl http://localhost:3000/api/health

# Check port is listening
netstat -tlnp | grep 3000

# Check firewall
firewall-cmd --list-ports
```

#### "Database connection pool exhausted"
```typescript
// PROBLEM - Not closing connections
const users = await db.query('SELECT * FROM users')
// Missing: db.end()

// SOLUTION - Use try/finally
try {
  const users = await db.query('SELECT * FROM users')
} finally {
  await db.end()
}

// Or use Prisma's connection management
// It handles this automatically!
```

#### "CORS error"
```typescript
// SOLUTION - Configure CORS properly
app.use(cors({
  origin: process.env.ALLOWED_ORIGINS?.split(','),
  credentials: true,
}))
```

### Docker

#### "Container exits immediately"
```bash
# Check logs
docker logs container_id

# Check exit code
docker inspect container_id --format='{{.State.ExitCode}}'

# Interactive debug
docker run -it image_name /bin/sh
```

---

## DEBUGGING TOOLS

### Browser DevTools
- **Console** - Runtime errors, logs
- **Network** - API calls, timing
- **Sources** - Breakpoints, step debugging
- **Performance** - Slow rendering, memory
- **Application** - Local storage, cookies

### VS Code Debugging
```json
// .vscode/launch.json
{
  "configurations": [
    {
      "type": "node",
      "request": "launch",
      "name": "Debug Server",
      "skipFiles": ["<node_internals>/**"],
      "program": "${workspaceFolder}/src/index.ts"
    },
    {
      "type": "chrome",
      "request": "launch",
      "name": "Debug Frontend",
      "url": "http://localhost:3000"
    }
  ]
}
```

### Debug Logging
```typescript
// Structured logging
const logger = {
  info: (msg: string, meta: object) => 
    console.log(JSON.stringify({ level: 'info', msg, meta, timestamp: new Date() })),
  error: (msg: string, error: Error) =>
    console.error(JSON.stringify({ 
      level: 'error', 
      msg, 
      error: error.message, 
      stack: error.stack,
      timestamp: new Date() 
    }))
}
```

### Network Debugging
```bash
# Curl with details
curl -v http://localhost:3000/api/health

# Watch requests
npx httpx GET http://localhost:3000/api/health

# Check SSL
curl -vvv https://example.com
```

### Database Debugging
```sql
-- Explain query plan
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'test@example.com';

-- Check slow queries
SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;

-- Check connections
SELECT count(*) FROM pg_stat_activity;
```

---

## ERROR CODES QUICK REFERENCE

| Code | Meaning | Fix |
|------|---------|-----|
| 400 | Bad Request | Validate input |
| 401 | Unauthorized | Check auth token |
| 403 | Forbidden | Check permissions |
| 404 | Not Found | Check route |
| 429 | Rate Limited | Back off requests |
| 500 | Server Error | Check logs |
| 502 | Bad Gateway | Check upstream |
| 503 | Unavailable | Check service health |

---

## DEBUGGING CHECKLIST

When stuck:
1. [ ] Read the FULL error message
2. [ ] Check the stack trace
3. [ ] Look at YOUR code in stack, not library code
4. [ ] Search the error message
5. [ ] Check if it worked before (git diff)
6. [ ] Simplify to isolate
7. [ ] Add logging
8. [ ] Ask for help with FULL context