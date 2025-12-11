import pygame
from resources import load_characters
from classes import GameManager, Scene, AudioManager, RelationshipTracker

# List of scenes and their backgrounds
scene_list = [
    ("scene1", "assets/backgrounds/scene1.png", "assets/audio/music/First-Day.ogg"),
    ("scene1_5", "assets/backgrounds/scene1_5.png", "assets/audio/music/Chase-Em.ogg"),
    ("scene2", "assets/backgrounds/scene2.png", "assets/audio/music/Break-Time.ogg"),
    ("scene2_5", "assets/backgrounds/scene2_5.png", "assets/audio/music/Fallen.ogg"),
    ("scene3", "assets/backgrounds/scene3.png", "assets/audio/music/After-Work.ogg"),
    ("scene_neutral", "assets/backgrounds/scene3.png", "assets/audio/music/Neutral-End.ogg"),
    ("scene_good", "assets/backgrounds/scene3.png", "assets/audio/music/Good-End.ogg"),
    ("scene_bad", "assets/backgrounds/scene3.png", "assets/audio/music/Bad-End.ogg")
]

def run_game():
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((1280, 720))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 28)

    # Preload audio manager
    audio_manager = AudioManager("assets/audio")
    relationship_tracker = RelationshipTracker()

    # Preload characters once
    raw_characters = load_characters("assets/characters/characters.json")

    # Convert all paths to pygame.Surface if not already
    characters = {}
    for name, emotions in raw_characters.items():
        characters[name] = {}
        for emo, val in emotions.items():
            if isinstance(val, str):  # file path
                try:
                    characters[name][emo] = pygame.image.load(val).convert_alpha()
                except Exception as e:
                    print(f"Failed to load {val}: {e}")
                    characters[name][emo] = None
            elif isinstance(val, pygame.Surface):
                characters[name][emo] = val
            else:
                characters[name][emo] = None

    # Preload all scenes
    scenes = []
    for scene_name, bg_path, music_path in scene_list:
        dialogue_path = f"assets/dialogue/{scene_name}.json"
        try:
            scene = Scene(bg_path, dialogue_path, characters, music_path)
            scenes.append(scene)
        except Exception as e:
            print(f"Scene load error in {scene_name}: {e}")

    # Setup GameManager
    game_manager = GameManager(screen, scenes, audio_manager, font, relationship_tracker)

    # Main loop
    running = True
    while running:
        dt = clock.tick(60) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                game_manager.handle_event(event)

        game_manager.update(dt)
        screen.fill((0, 0, 0))
        game_manager.draw()
        pygame.display.flip()

    pygame.quit()