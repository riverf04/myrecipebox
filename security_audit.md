# API Security Audit – Recipe Box API

**Date:** 2026-10-01  
**Auditor:** River Frazier  

This document records an end-to-end security review of the Recipe Box API, focusing on:
- Safe password storage
- Authentication (identity protection)
- Authorization (ownership and admin role enforcement)
- Regression testing of cross-user access controls

---

## 1. Safe Password Storage

### Database Schema
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user'
);
```

### Verification
```sql
SELECT id, username, email, password_hash, role FROM users LIMIT 5;
```

**Observed Output:**
`password_hash` values are long, properly salted `scrypt` hashes, e.g.:
```text
scrypt:32768:8:1$QbssAmB5JMntZVOj$3d4b84...e71fc44
```
No plaintext or easily guessable passwords were found in storage.

> **Conclusion:** Passwords are stored as secure hashes, not plaintext.  
> **Status:** ✅ **PASS**

---

## 2. Authentication – Identity Protection

### 2.1 Anonymous Access to Protected Route
**Route under test:**
```python
@app.post("/recipes")
@token_required
def create_recipe():
    ...
```

**Request:**
```bash
curl -i \
  -X POST http://127.0.0.1:5000/recipes \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Security test recipe",
    "ingredients": "test ingredients",
    "instructions": "test instructions",
    "is_public": true
  }'
```

**Expected Result:** `401 Unauthorized` (missing identity token)  
**Observed Output:**
```http
HTTP/1.1 401 UNAUTHORIZED
{"error":"missing or invalid Authorization header"}
```

> **Conclusion:** Protected route correctly rejects anonymous requests with HTTP 401.  
> **Status:** ✅ **PASS**

---

### 2.2 Authenticated Login
**Route under test:**
```python
@app.post("/login")
def login():
    ...
```

**Request:**
```bash
curl -i \
  -X POST http://127.0.0.1:5000/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "password": "testpass"
  }'
```

**Observed Output:**
```http
HTTP/1.1 200 OK
{"id":1,"username":"alice","token":"<JWT_TOKEN_HERE>"}
```

> **Conclusion:** Valid credentials successfully issue a signed JWT containing `sub`, `username`, `role`, and `exp` claims.  
> **Status:** ✅ **PASS**

---

## 3. Authorization – Ownership and Roles

### 3.1 Initial Context & Data State
**Database state:**
```sql
SELECT id, title, is_public, owner_id FROM recipes;
```

```text
id  title                    is_public  owner_id
--  -----------------------  ---------  --------
2   Overnight oats           1          1
3   Secret family hot sauce  0          1
```
*Note: User with `id = 1` (`alice`) owns recipes `2` and `3`.*

---

### 3.2 Non-Owner Cannot Update Another User's Recipe
**Route under test:**
```python
@app.patch("/recipes/<int:recipe_id>")
@token_required
def update_recipe(recipe_id):
    ...
    denial = ensure_owner_or_admin(recipe, user_id, user_role)
    if denial is not None:
        return denial
    ...
```

**Step 1:** Authenticate as non-owner (`charlie`)
```bash
curl -i \
  -X POST http://127.0.0.1:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "charlie", "password": "testpass"}'
```

**Step 2:** Attempt to update `alice`'s recipe (ID `2`)
```bash
curl -i \
  -X PATCH http://127.0.0.1:5000/recipes/2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <CHARLIE_JWT>" \
  -d '{
    "title": "Overnight oats (hacked by charlie)"
  }'
```

**Expected Result:** `403 Forbidden`  
**Observed Output:**
```http
HTTP/1.1 403 FORBIDDEN
{"error":"Forbidden"}
```

> **Conclusion:** Non-owners cannot modify recipes owned by other users.  
> **Status:** ✅ **PASS**

---

### 3.3 Owner Can Update Own Recipe
**Step 1:** Authenticate as owner (`alice`)
```bash
curl -i \
  -X POST http://127.0.0.1:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "testpass"}'
```

**Step 2:** Update recipe ID `2`
```bash
curl -i \
  -X PATCH http://127.0.0.1:5000/recipes/2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <ALICE_JWT>" \
  -d '{
    "title": "Overnight oats (owner edit by alice)"
  }'
```

**Observed Output:**
```http
HTTP/1.1 200 OK
{"id":2,...,"title":"Overnight oats (owner edit by alice)"}
```

> **Conclusion:** Resource owners can successfully update their own recipes.  
> **Status:** ✅ **PASS**

---

### 3.4 Admin Can Update Another User's Recipe
**Step 1:** Authenticate as administrator (`bob`)
```bash
curl -i \
  -X POST http://127.0.0.1:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "bob", "password": "testpass"}'
```

**Step 2:** Update `alice`'s recipe (ID `2`)
```bash
curl -i \
  -X PATCH http://127.0.0.1:5000/recipes/2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <BOB_JWT>" \
  -d '{
    "title": "Overnight oats (admin edit by bob)"
  }'
```

**Observed Output:**
```http
HTTP/1.1 200 OK
{"id":2,...,"title":"Overnight oats (admin edit by bob)"}
```

> **Conclusion:** Admin role is correctly permitted to modify recipes across accounts per specifications.  
> **Status:** ✅ **PASS**

---

## 4. Known Issue – Recipe Creation Failure

### Route & Implementation Under Test
```python
@app.post("/recipes")
@token_required
def create_recipe():
    ...
    cur = db.execute(
        "INSERT INTO recipes (title, ingredients, instructions, is_public)"
        " VALUES (?, ?, ?, ?)",
        (...)
    )
    ...
```

### Table Schema
```sql
CREATE TABLE recipes (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL UNIQUE,
    ingredients TEXT NOT NULL,
    instructions TEXT NOT NULL DEFAULT '',
    is_public INTEGER NOT NULL DEFAULT 1,
    owner_id INTEGER NOT NULL
);
```

### Observed Behavior
Any authenticated attempt to create a recipe returns:
```http
HTTP/1.1 409 CONFLICT
{"error":"a recipe with that title already exists"}
```
*(Occurs even when the recipe title is completely unique in the database.)*

### Root Cause Analysis
1. `owner_id` is defined as `NOT NULL` in the SQL schema.
2. The `INSERT` statement in `create_recipe()` omits `owner_id`.
3. SQLite throws an `IntegrityError` because `owner_id` is null.
4. The application catches all `IntegrityError` exceptions and generically returns a `409` conflict claiming the title already exists.

> **Conclusion:** Authentication is enforced for recipe creation, but creation currently fails for all inputs due to a SQL statement/schema mismatch.  
> **Status:** ⚠️ **FAIL** *(Implementation bug, not an authorization bypass)*

---

## 5. Audit Summary

| Check / Metric | Details | Result |
| :--- | :--- | :---: |
| **Password Storage** | Passwords stored with salted `scrypt` hashing. | ✅ **PASS** |
| **Authentication** | JWT-based auth via `/login`; protected endpoints return `401` when unauthenticated. | ✅ **PASS** |
| **Non-Owner Access** | Non-owners receive `403 Forbidden` when attempting to modify other users' recipes. | ✅ **PASS** |
| **Owner Access** | Users can edit their own recipes (`200 OK`). | ✅ **PASS** |
| **Admin Access** | Administrators can edit any user's recipe (`200 OK`). | ✅ **PASS** |
| **Recipe Creation** | `POST /recipes` fails due to missing `owner_id` in SQL `INSERT` statement. | ⚠️ **FAIL** |

### Overall Assessment
Identity protection, ownership rules, and role-based access controls are securely enforced across tested endpoints. The primary issue discovered is an application logic bug in `POST /recipes` that prevents new recipe creation.