import pygame, json

def load_characters(char_file):
    with open(char_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    characters = {}
    for name, emotions in data.items():
        characters[name] = {}
        for emo, path in emotions.items():
            characters[name][emo] = pygame.image.load(path).convert_alpha()
    return characters