from anime_sama_api.season import Season

one_piece = (
    [
        Season(f"https://anime-sama.si/catalogue/one-piece/saison{i}/")
        for i in range(1, 12)
    ]
    + [
        Season("https://anime-sama.si/catalogue/one-piece/film/"),
        Season("https://anime-sama.si/catalogue/one-piece/oav/"),
        Season("https://anime-sama.si/catalogue/one-piece/saison1hs/"),
        Season("https://anime-sama.si/catalogue/one-piece/kai/"),
    ]
    + [
        Season(f"https://anime-sama.si/catalogue/one-piece/kai{i}/")
        for i in range(2, 12)
    ]
)
gumball = [
    Season(f"https://anime-sama.si/catalogue/le-monde-incroyable-de-gumball/saison{i}/")
    for i in range(1, 7)
] + [
    Season("https://anime-sama.si/catalogue/le-monde-incroyable-de-gumball/saison1hs/")
]

mha = [
    Season(f"https://anime-sama.si/catalogue/my-hero-academia/saison{i}/")
    for i in range(1, 9)
] + [
    Season("https://anime-sama.si/catalogue/my-hero-academia/film/"),
    Season("https://anime-sama.si/catalogue/my-hero-academia/oav/"),
]
