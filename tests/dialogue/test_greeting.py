from __future__ import annotations

from dialogue.prompts import RestaurantPrompts


def test_render_greeting_without_featured_items() -> None:
    prompts = RestaurantPrompts(
        restaurant_id="demo",
        greeting="Welcome to Demo Cafe!",
    )
    assert prompts.render_greeting() == "Welcome to Demo Cafe!"


def test_render_greeting_with_featured_items() -> None:
    prompts = RestaurantPrompts(
        restaurant_id="hot_bagels_2nd_street",
        greeting="Welcome to Hot Bagels on 2nd Street!",
        featured_items=[
            "a cream cheese sandwich",
            "iced coffee",
            "Mediterranean toast",
        ],
    )
    text = prompts.render_greeting()
    assert text.startswith("Welcome to Hot Bagels on 2nd Street!")
    assert "1. A cream cheese sandwich" in text
    assert "2. Iced coffee" in text
    assert "3. Mediterranean toast" in text
    assert "\n2. " in text
    assert "What would you like to order today?" in text
