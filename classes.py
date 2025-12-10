import pygame, os, json

# -----------------------
# Audio Manager
# -----------------------
class AudioManager:
    # Loads and plays sound effects/voice lines
    def __init__(self, folder):
        self.sounds = {}
        self._load_audio_recursive(folder)

    def _load_audio_recursive(self, root_folder):
        if not os.path.isdir(root_folder):
            print(f"Audio folder '{root_folder}' not found.")
            return

        for root, dirs, files in os.walk(root_folder):
            for file in files:
                if file.endswith(".wav") or file.endswith(".ogg"):
                    full_path = os.path.join(root, file)

                    # Create a key like: voices/test_line   or   sfx/door_open
                    relative = os.path.relpath(full_path, root_folder)
                    key = os.path.splitext(relative)[0].replace("\\", "/")

                    try:
                        self.sounds[key] = pygame.mixer.Sound(full_path)
                    except pygame.error as e:
                        print(f"Failed to load sound '{full_path}': {e}")

    def play(self, name):
        sound = self.sounds.get(name)
        if sound:
            sound.play()
        else:
            print(f"[AudioManager] Sound not found: {name}")

    def stop(self, name):
        sound = self.sounds.get(name)
        if sound:
            sound.stop()

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
    Handles dialogue progression, voice playback, narration, timed choices,
    plus multi-character rendering (left/right), dimming, hide/show commands,
    and branch insertion for choices.
    """

    def __init__(self, dialogue_lines, audio_manager, font,
                 relationship_tracker=None, choice_timer_class=None,
                 pos=(50, 500), color=(255, 255, 255)):
        # Core data
        self.dialogue_lines = dialogue_lines
        self.audio = audio_manager
        self.font = font
        self.pos = pos
        self.color = color

        # Progress and current state
        self.index = 0
        self.current_voice = None
        self.waiting = False
        self.current_line = None

        # RelationshipTracker class
        self.relationship = relationship_tracker
        # ChoiceTimer class
        self.ChoiceTimerClass = choice_timer_class

        # Choice state
        self.choice_timer = None
        self.selected_choice = None

        # Name reveal map (keeps JSON stable; display name can change)
        self.name_map = {
            "Player": "Player",
            "Partner": "Partner"
        }

        # Visibility / rendering state for characters (init lazily)
        self.visible_characters = None  # dict: name -> bool

    def check_name_reveal(self, line_data):
        """
        Example triggers: update this logic to match actual reveal lines in your script.
        Keep it simple: if the text contains a reveal phrase, update name_map.
        """
        if not line_data:
            return
        text = line_data.get("line", "")
        speaker = line_data.get("speaker", "")

        # Example triggers (adjust to match your script wording)
        if speaker == "Player" and "Vera" in text:
            self.name_map["Player"] = "Vera"
        if speaker == "Partner" and "Ellie" in text:
            self.name_map["Partner"] = "Ellie"

    def start_line(self):
        """Start or return the current line. Processes normal lines and choice starts."""
        if self.index >= len(self.dialogue_lines):
            self.current_line = None
            return None

        line_data = self.dialogue_lines[self.index]
        self.current_line = line_data

        # Name reveal check
        self.check_name_reveal(line_data)

        line_type = line_data.get("type", "line")

        # If the line is a simple command (hide/show), draw() will process it
        # because draw has access to the 'scene' (which contains characters).
        # It still returns the line here so update() and draw() can see it.
        if line_type in ["line", "narration"]:
            voice = line_data.get("voice")
            if voice:
                try:
                    self.audio.play(voice)
                except Exception:
                    pass
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

        # For unknown types (including possible 'command' entries), just return it
        return line_data

    def update(self, dt):
        """
        Called each frame. Handles:
          - voice auto-advance for lines/narration
          - timed choice expiry
        Returns: new line_data if advanced, otherwise None.
        """
        if not self.current_line:
            return None

        line_type = self.current_line.get("type", "line")

        # For normal dialogue/narration, advance after voice ends
        if line_type in ["line", "narration"] and self.waiting:
            # advance when no sounds playing (voice finished)
            try:
                busy = pygame.mixer.get_busy()
            except Exception:
                busy = False
            if not busy:
                self.waiting = False
                self.index += 1
                return self.start_line()

        # For choices
        if line_type == "choice" and self.choice_timer:
            if self.choice_timer.update(dt):
                # timer expired
                if self.selected_choice is None:
                    self.selected_choice = 0
                    self.apply_choice(self.selected_choice)
                self.choice_timer = None
                self.index += 1
                return self.start_line()

        return None

    # Call when player clicks a choice button.
    def click_choice(self, choice_index):
        """Player explicitly selected a choice."""
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
        """Apply points and insert branch lines (if any)."""
        choices = self.current_line.get("choices", [])
        if choice_index < len(choices):
            choice = choices[choice_index]
            points = choice.get("points", 0)
            if self.relationship:
                self.relationship.add(points)

            # If there's a branch (list of lines), insert them right after current index
            branch = choice.get("branch")
            if branch and isinstance(branch, list):
                insert_pos = self.index + 1
                # Make a shallow copy to avoid mutating original data unintentionally
                for i, entry in enumerate(branch):
                    # Insert in original order
                    self.dialogue_lines.insert(insert_pos + i, entry)

    # Drawing & rendering
    def draw(self, screen, scene):
        """
        Draw current line or choices, including both character sprites with emotions,
        dimming/highlighting, and processing hide/show commands.
        """
        if not self.current_line:
            return

        # Lazy init of visible_characters from scene
        if self.visible_characters is None:
            self.visible_characters = {}
            # mark all characters present in the scene as visible by default
            if hasattr(scene, "characters") and isinstance(scene.characters, dict):
                for name in scene.characters.keys():
                    self.visible_characters[name] = True

        # If this line is a simple command (hide/show), process it now, using the scene context
        if "command" in self.current_line:
            cmd = self.current_line.get("command")
            target = self.current_line.get("target")
            if cmd and target:
                if cmd.lower() == "hide":
                    self.visible_characters[target] = False
                elif cmd.lower() == "show":
                    self.visible_characters[target] = True
            # advance immediately to next line
            self.index += 1
            self.start_line()
            return  # next frame will draw the next line

        line_type = self.current_line.get("type", "line")
        y_offset = self.pos[1]

        # Determine speaker and emotion for this line
        speaker = self.current_line.get("speaker", "")
        emotion = self.current_line.get("emotion", "neutral")

        # Multi-character rendering
        # Draw all visible characters (Partner = left, Player = right)
        # Uses dims for inactive speaker and full alpha for active speaker.
        left_name = "Partner" # Ellie
        right_name = "Player" # Vera

        # Helper to fetch sprite for a character + emotion (safe)
        def _get_sprite_for(name, emotion_key="neutral"):
            if not hasattr(scene, "characters") or not isinstance(scene.characters, dict):
                return None
            if name not in scene.characters:
                return None
            sprite_dict = scene.characters[name]
            # sprite_dict expected to be dict of emotion -> Surface OR single Surface for fallback
            if isinstance(sprite_dict, dict):
                sprite = sprite_dict.get(emotion_key, sprite_dict.get("neutral"))
            else:
                # if user used older format (simple path or Surface), try neutral fallback
                sprite = sprite_dict
            return sprite

        # Determine active speaker (for highlighting)
        active_speaker = None
        if speaker and self.visible_characters.get(speaker, False):
            active_speaker = speaker

        # Draw left character (Partner) if present and visible
        left_sprite = _get_sprite_for(left_name, emotion if speaker == left_name else "neutral")
        if left_sprite and self.visible_characters.get(left_name, True):
            try:
                # compute left position (fixed)
                left_x = 100
                left_y = 200
                # determine alpha
                alpha_val = 255 if active_speaker == left_name else 120
                sprite_to_draw = left_sprite.copy()
                # if sprite has per-pixel alpha, set_alpha still works on the copy
                sprite_to_draw.set_alpha(alpha_val)
                screen.blit(sprite_to_draw, (left_x, left_y))
            except Exception:
                # fallback: blit original without alpha changes
                screen.blit(left_sprite, (100, 200))

        # Draw right character (Player) if present and visible
        right_sprite = _get_sprite_for(right_name, emotion if speaker == right_name else "neutral")
        if right_sprite and self.visible_characters.get(right_name, True):
            try:
                # compute right position based on screen width and sprite width
                sw = screen.get_width()
                sprite_w = right_sprite.get_width()
                right_x = max( sw - sprite_w - 100, 300 )  # ensure not too far left
                right_y = 200
                alpha_val = 255 if active_speaker == right_name else 120
                sprite_to_draw = right_sprite.copy()
                sprite_to_draw.set_alpha(alpha_val)
                screen.blit(sprite_to_draw, (right_x, right_y))
            except Exception:
                screen.blit(right_sprite, (sw - sprite_w - 100, 200))

        # Draw text / choices on top
        if line_type in ["line", "narration"]:
            text = self.current_line.get("line", "")

            # Speaker name
            if speaker:
                display_name = self.name_map.get(speaker, speaker)
                name_surf = self.font.render(f"{display_name}:", True, self.color)
                screen.blit(name_surf, (self.pos[0], y_offset - 30))

            # Dialogue / narration text
            for i, line in enumerate(text.split("\n")):
                surf = self.font.render(line, True, self.color)
                screen.blit(surf, (self.pos[0], y_offset + i * self.font.get_height()))

        # Draw choices
        elif line_type == "choice":
            choices = self.current_line.get("choices", [])
            for i, choice in enumerate(choices):
                prefix = ">" if i == getattr(self, "selected_choice", -1) else ""
                surf = self.font.render(f"{prefix}{choice['text']}", True, self.color)
                screen.blit(surf, (self.pos[0], y_offset + i * self.font.get_height() * 1.5))

            if getattr(self, "choice_timer", None):
                timer_text = f"Time left: {int(self.choice_timer.get_remaining())}s"
                timer_surf = self.font.render(timer_text, True, self.color)
                screen.blit(timer_surf, (self.pos[0], y_offset - 40))

    # Click handling
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
            # delegate to choice click handler
            return self.handle_click(mouse_pos)
        else:
            # advance a normal line manually (skips voice wait)
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