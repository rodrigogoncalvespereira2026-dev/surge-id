from db import execute, one

SEED_GAMES = [
    ("primal_force", "Power Rangers Primal Force"),
    ("surge_hub", "Surge Games Hub"),
]


def seed_games():
    for slug, name in SEED_GAMES:
        if not one("SELECT slug FROM games WHERE slug = %s", (slug,)):
            execute("INSERT INTO games (slug, name) VALUES (%s, %s)", (slug, name))


def main():
    from app import create_app

    create_app()
    print("Base de dados inicializada e jogos de exemplo inseridos.")


if __name__ == "__main__":
    main()
