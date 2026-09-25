## 2026-09-17

- GET /recipes → returns all recipes, including is_public:false items, to anonymous callers.
- PATCH /recipes/1 → allows anonymous caller to change recipe 1 title; change is persisted.
- DELETE /recipes/1 → allows anonymous caller to delete recipe 1; it no longer appears in GET /recipes.
