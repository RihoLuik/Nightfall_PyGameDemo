import pygame, os, json

# -----------------------
# Audio Manager
# -----------------------
class AudioManager:
    # Loads and plays sound effects/voice lines
    def __init__(self, folder):
        self.sounds = {}
        if not os.path.isdir(folder):
            print(f"Audio folder '{folder}' not found.")
            return

        for file in os.listdir(folder):
            if file.endswith(".wav") or file.endswith(".ogg"):
                name = os.path.splitext(file)[0]
                self.sounds[name] = pygame.mixer.Sound(os.path.join(folder, file))

    def play(self, name):
        if name in self.sounds:
            self.sounds[name].play()

    def stop(self, name):
        if name in self.sounds:
            self.sounds[name].stop()

# -----------------------
# RelationshipTracker
# -----------------------
class RelationshipTracker:
    # Tracks player-character relationship score and determines endings
    def __init__(self):
        self.score = 0

    def add(self, amount):
        self.score += amount

    def get_score(self):
        return self.score

# -----------------------
# Choice Timer
# -----------------------
class ChoiceTimer:
    # Handles timed choices and QTE countdowns
    def __init__(self, duration):
        self.duration = duration
        self.time_left = duration
        self.active = False

    # Start (or restart) the timer.
    def start(self):
        self.time_left = self.duration
        self.active = True

    # Decrease time by delta time. Returns True when timer hits zero.
    def update(self, dt):
        if self.active:
            self.time_left -= dt
            if self.time_left <= 0:
                self.active = False
                return True  # timer expired
        return False

    # Reset without starting.
    def reset(self):
        self.time_left = self.duration
        self.active = False

    # Return how much time is left.
    def get_remaining(self):
        return max(0, self.time_left)

# -----------------------
# Scene
# -----------------------
class Scene:
    # Loads scene backgrounds, character sprites, and dialogue JSON
    def __init__(self, background, characters_dict, dialogue_file):
        """
        characters_dict example:
        {
            "Partner": {"neutral": "partner/neutral.png", "angry": "partner/angry.png"},
            "Player": {"neutral": "player/neutral.png", "determined": "player/determined.png"}
        }
        """
        self.background = pygame.image.load(background).convert()
        self.characters = {}

        for char_name, sprites in characters_dict.items():
            self.characters[char_name] = {}
            for emotion, path in sprites.items():
                self.characters[char_name][emotion] = pygame.image.load(path).convert_alpha()

        with open(dialogue_file, "r", encoding="utf-8") as f:
            import json
            data = json.load(f)
            scene_key = list(data.keys())[0]
            self.dialogue = data[scene_key]

# -----------------------
# Dialogue System
# -----------------------
class DialogueSystem:
    """
    Handles dialogue progression, voice playback, narration, and timed choices.
    Supports:
      - type: "line"      → normal dialogue
      - type: "narration" → descriptive text
      - type: "choice"    → timed choices affecting relationship score
    """

    def __init__(self, dialogue_lines, audio_manager, font, relationship_tracker=None, choice_timer_class=None, pos=(50, 500), color=(255,255,255)):
        self.dialogue_lines = dialogue_lines
        self.audio = audio_manager
        self.font = font
        self.pos = pos
        self.color = color
        self.index = 0
        self.current_voice = None
        self.waiting = False
        self.current_line = None

        # Link to RelationshipTracker
        self.relationship = relationship_tracker
        # Custom ChoiceTimer class
        self.ChoiceTimerClass = choice_timer_class

        # Active choice timer (if current line is a timed choice)
        self.choice_timer = None
        self.selected_choice = None

    # Start or return the current line.
    def start_line(self):
        if self.index >= len(self.dialogue_lines):
            self.current_line = None
            return None

        line_data = self.dialogue_lines[self.index]
        self.current_line = line_data

        line_type = line_data.get("type", "line")

        if line_type in ["line", "narration"]:
            voice = line_data.get("voice")
            if voice:
                self.audio.play(voice)
                self.current_voice = voice
            self.waiting = True
            return line_data

        elif line_type == "choice":
            # Start a timer if provided
            if "timer" in line_data and self.ChoiceTimerClass:
                self.choice_timer = self.ChoiceTimerClass(line_data["timer"])
                self.choice_timer.start()
            self.waiting = True
            self.selected_choice = None
            return line_data
        return line_data

    def update(self, dt):
        """
        Call every frame.
        Handles:
          - voice auto-advance
          - timed choices
        Returns new line if advanced.
        """
        if not self.current_line:
            return None

        line_type = self.current_line.get("type", "line")

        # For normal dialogue/narration, advance after voice ends
        if line_type in ["line", "narration"] and self.waiting:
            if not pygame.mixer.get_busy():
                self.waiting = False
                self.index += 1
                return self.start_line()

        # For choices
        if line_type == "choice" and self.choice_timer:
            if self.choice_timer.update(dt):
                # Timer expired; pick first choice as default if none selected
                if self.selected_choice is None:
                    self.selected_choice = 0
                    self.apply_choice(self.selected_choice)
                self.choice_timer = None
                self.index += 1
                return self.start_line()
        return None

    # Call when player clicks a choice button.
    def click_choice(self, choice_index):
        if self.current_line and self.current_line.get("type") == "choice":
            self.selected_choice = choice_index
            self.apply_choice(choice_index)
            if self.choice_timer:
                self.choice_timer.active = False
            self.choice_timer = None
            self.index += 1
            return self.start_line()
        return None

    # Apply relationship points from choice.
    def apply_choice(self, choice_index):
        choices = self.current_line.get("choices", [])
        if choice_index < len(choices):
            points = choices[choice_index].get("points", 0)
            if self.relationship:
                self.relationship.add(points)

    # Draw current line or choices, including speaker sprites with emotions.
    def draw(self, screen, scene):
        if not self.current_line:
            return

        line_type = self.current_line.get("type", "line")
        y_offset = self.pos[1]

        # Determine speaker and emotion
        speaker = self.current_line.get("speaker", "")
        emotion = self.current_line.get("emotion", "neutral")  # default to neutral

        # Draw character sprite if available
        if speaker in scene.characters and emotion in scene.characters[speaker]:
            sprite = scene.characters[speaker][emotion]
            screen.blit(sprite, (100, 200))  # adjust x, y as needed

        # --- Draw dialogue or narration ---
        if line_type in ["line", "narration"]:
            text = self.current_line.get("line", "")

            # Speaker name
            if speaker:
                name_surf = self.font.render(f"{speaker}:", True, self.color)
                screen.blit(name_surf, (self.pos[0], y_offset - 30))

            # Dialogue / narration text
            for i, line in enumerate(text.split("\n")):
                surf = self.font.render(line, True, self.color)
                screen.blit(surf, (self.pos[0], y_offset + i * self.font.get_height()))

        # --- Draw choices ---
        elif line_type == "choice":
            choices = self.current_line.get("choices", [])
            for i, choice in enumerate(choices):
                prefix = ">" if i == getattr(self, 'selected_choice', -1) else ""
                surf = self.font.render(f"{prefix}{choice['text']}", True, self.color)
                screen.blit(surf, (self.pos[0], y_offset + i * self.font.get_height() * 1.5))

            # Draw timer if present
            if getattr(self, 'choice_timer', None):
                timer_text = f"Time left: {int(self.choice_timer.get_remaining())}s"
                timer_surf = self.font.render(timer_text, True, self.color)
                screen.blit(timer_surf, (self.pos[0], y_offset - 40))

    def handle_click(self, mouse_pos):
        """
        Checks if a choice was clicked and selects it.
        Returns the new line if advanced, else None.
        """
        if not self.current_line or self.current_line.get("type") != "choice":
            return None

        # Basic layout: choices rendered vertically starting at self.pos
        x, y_start = self.pos
        choice_height = self.font.get_height() * 1.5
        mouse_x, mouse_y = mouse_pos

        choices = self.current_line.get("choices", [])
        for i, _ in enumerate(choices):
            choice_y_top = y_start + i * choice_height
            choice_y_bottom = choice_y_top + choice_height
            if choice_y_top <= mouse_y <= choice_y_bottom:
                # Clicked this choice
                return self.click_choice(i)
        return None

    def click(self, mouse_pos=None):
        """
        Handles clicks for both normal dialogue and choices.
        - If mouse_pos is provided, and it's a choice, selects the choice.
        - Otherwise, advances normal dialogue.
        """
        if not self.current_line:
            return None

        line_type = self.current_line.get("type", "line")

        if line_type == "choice" and mouse_pos is not None:
            # handle choice click
            x, y_start = self.pos
            choice_height = self.font.get_height() * 1.5
            mouse_x, mouse_y = mouse_pos

            choices = self.current_line.get("choices", [])
            for i, _ in enumerate(choices):
                choice_y_top = y_start + i * choice_height
                choice_y_bottom = choice_y_top + choice_height
                if choice_y_top <= mouse_y <= choice_y_bottom:
                    return self.click_choice(i)
            return None
        else:
            # normal dialogue click
            self.index += 1
            return self.start_line()

# -----------------------
# Game Manager
# -----------------------
class GameManager:
    # Manages scenes, dialogue progression, and drawing
    def __init__(self, screen, scenes, audio_manager, font):
        self.screen = screen
        self.scenes = scenes
        self.audio = audio_manager
        self.font = font

        self.current_scene_index = 0
        self.current_scene = scenes[0]

        self.dialogue_system = DialogueSystem(
            self.current_scene.dialogue,
            self.audio,
            self.font
        )

        self.current_line = self.dialogue_system.start_line()
        self.active = True

    def update(self, dt):
        if not self.active:
            return

        if self.current_line is None:
            self.next_scene()

        new_line = self.dialogue_system.update(dt)
        if new_line:
            self.current_line = new_line

    def draw(self):
        scene = self.current_scene

        # background
        self.screen.blit(scene.background, (0, 0))

        # characters
        x = 100
        for ch in scene.characters:
            self.screen.blit(ch, (x, 200))
            x += ch.get_width() + 40

        # dialogue
        self.dialogue_system.draw(self.screen)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            new_line = self.dialogue_system.click(event.pos)
            if new_line:
                self.current_line = new_line

    def next_scene(self):
        self.current_scene_index += 1

        if self.current_scene_index >= len(self.scenes):
            self.active = False
            return

        self.current_scene = self.scenes[self.current_scene_index]
        self.dialogue_system = DialogueSystem(
            self.current_scene.dialogue,
            self.audio,
            self.font
        )
        self.current_line = self.dialogue_system.start_line()