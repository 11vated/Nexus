---
name: api-design
description: Design REST APIs following best practices - use when building endpoints
tools: Read, Write
model: qwen2.5-coder:14b
---
# API Design Skill

## REST Principles
- Nouns for resources: `/users`, `/orders`
- HTTP verbs: GET, POST, PUT, DELETE
- Return proper status codes

## Status Codes
- 200 OK
- 201 Created
- 400 Bad Request
- 401 Unauthorized
- 404 Not Found
- 500 Server Error

## Example: Flask
```python
@app.route('/api/users', methods=['GET'])
def get_users():
    return jsonify(users)

@app.route('/api/users', methods=['POST'])
def create_user():
    user = request.json
    return jsonify(user), 201
```