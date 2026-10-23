from app.db import get_db
from app.models import Recipe
import sqlite3


def get_all_recipes():
    recipes = Recipe.query.filter_by(is_public=True).all()
    return [
        {
            "id": recipe.id,
            "title": recipe.title,
            "ingredients": recipe.ingredients,
            "instructions": recipe.instructions,
            "is_public": bool(recipe.is_public),
        }
        for recipe in recipes
    ]


def get_recipe_by_id(recipe_id):
    recipe = Recipe.query.get(recipe_id)
    if recipe is None:
        return None
    return {
        "id": recipe.id,
        "title": recipe.title,
        "ingredients": recipe.ingredients,
        "instructions": recipe.instructions,
        "is_public": bool(recipe.is_public),
    }


def get_recipes_for_user(user_id):
    db = get_db()
    cursor = db.execute("SELECT * FROM recipes WHERE owner_id = ?", (user_id,))
    rows = cursor.fetchall()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "ingredients": row["ingredients"],
            "instructions": row["instructions"],
            "is_public": bool(row["is_public"]),
        }
        for row in rows
    ]


def create_recipe(data, user_id):
    db = get_db()
    title = data.get("title")
    ingredients = data.get("ingredients")
    instructions = data.get("instructions", "")
    is_public = 1 if data.get("is_public", True) else 0

    try:
        cursor = db.execute(
            """
            INSERT INTO recipes (title, ingredients, instructions, is_public, owner_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, ingredients, instructions, is_public, user_id),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return None

    recipe_id = cursor.lastrowid
    row = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()

    return {
        "id": row["id"],
        "title": row["title"],
        "ingredients": row["ingredients"],
        "instructions": row["instructions"],
        "is_public": bool(row["is_public"]),
    }