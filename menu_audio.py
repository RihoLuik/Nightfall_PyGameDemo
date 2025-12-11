import pygame


class MenuAudio:
    def __init__(self):
        pygame.mixer.init()

        # Load sounds
        self.click = self.load_sound("assets/audio/sfx/click.ogg")
        self.hover = self.load_sound("assets/audio/sfx/hover.ogg")

    def load_sound(self, path):
        try:
            return pygame.mixer.Sound(path)
        except Exception as e:
            print(f"[Audio] Failed to load {path}: {e}")
            return None

    def play_click(self):
        if self.click:
            self.click.play()

    def play_hover(self):
        if self.hover:
            self.hover.play()

    def play_music(self):
        try:
            pygame.mixer.music.load("assets/audio/music/Nightfall-Theme.ogg")
            pygame.mixer.music.set_volume(0.6)
            pygame.mixer.music.play(-1)
        except Exception as e:
            print(f"[Music] Failed to play menu music: {e}")

    def stop_music(self):
        pygame.mixer.music.stop()

    # volume = 0.0 to 1.0
    def set_volume(self, volume):
        self.music_volume = volume
        self.sfx_volume = volume

        pygame.mixer.music.set_volume(self.music_volume)

        if self.hover:
            self.hover.set_volume(self.sfx_volume)
        if self.click:
            self.click.set_volume(self.sfx_volume)