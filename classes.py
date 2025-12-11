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
        # Strip extension and "assets/audio/" if present
        key = name.replace("assets/audio/", "").rsplit(".", 1)[0].replace("\\", "/")
        sound = self.sounds.get(key)
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
    """
        Loads scene background, references preloaded character sprites,
        and loads a single scene JSON file.
    """
    def __init__(self, background_path, dialogue_file, preloaded_characters, background_music=None):
        """
            preloaded_characters: dict of char_name -> dict of emotion -> Surface
        """
        self.background = pygame.image.load(background_path).convert()
        self.characters = preloaded_characters

        with open(dialogue_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.id = data.get("id")
        self.dialogue = data.get("dialogue", [])
        self.background_music = background_music  # path to music file (optional)

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

        self.image_screen_active = False
        self.image_screen_surface = None

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

        elif line_type == "image_screen":
            # Activate image screen
            self.image_screen_active = True
            image_path = line_data.get("image")
            if image_path:
                try:
                    self.image_screen_surface = pygame.image.load(image_path).convert_alpha()
                except Exception:
                    self.image_screen_surface = None
            self.waiting = True
            return line_data

        # For unknown types (including possible 'command' entries), just return it
        return line_data

    def draw_wrapped_text(self, screen, text, x, y, max_width, color=None):
        if color is None:
            color = self.color

        words = text.split(" ")
        lines = []
        current = ""

        for w in words:
            test = current + w + " "
            if self.font.size(test)[0] <= max_width:
                current = test
            else:
                lines.append(current)
                current = w + " "
        if current:
            lines.append(current)

        # Draw each wrapped line
        for line in lines:
            surf = self.font.render(line, True, color)
            screen.blit(surf, (x, y))
            y += self.font.get_linesize()

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

        # Image screen handling
        if line_type == "image_screen" and self.image_screen_active:
            # Just wait for click to advance (handled in click()) or auto advance if you want
            return None

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
        if choice_index >= len(choices):
            return

        choice = choices[choice_index]
        points = choice.get("points", 0)

        if self.relationship:
            self.relationship.add(points)

        rel_value = self.relationship.get() if self.relationship else 0

        # Branch selection
        if "target" in choice:
            # simple jump (good ending)
            self.insert_scene_jump(choice["target"])
            return

        # Positive/negative branching for "Sorry."
        if "target_positive" in choice and "target_negative" in choice:
            if rel_value >= 0:
                self.insert_scene_jump(choice["target_positive"])
            else:
                self.insert_scene_jump(choice["target_negative"])
            return

        # Old branch insertion
        branch = choice.get("branch")
        if branch and isinstance(branch, list):
            insert_pos = self.index + 1
            # Make a shallow copy to avoid mutating original data unintentionally
            for i, entry in enumerate(branch):
                # Insert in original order
                self.dialogue_lines.insert(insert_pos + i, entry)

    def insert_scene_jump(self, scene_id):
        self.dialogue_lines.insert(self.index + 1, {
            "type": "scene_jump",
            "target": scene_id
        })

    # Drawing & rendering
    def draw(self, screen, scene):
        """
        Draw current line or choices, including both character sprites with emotions,
        dimming/highlighting, and processing hide/show commands.
        """
        if not self.current_line:
            return

        # Init of visible_characters from scene
        if self.visible_characters is None:
            self.visible_characters = {}
            # mark all characters present in the scene as visible by default
            if hasattr(scene, "characters") and isinstance(scene.characters, dict):
                for name in scene.characters.keys():
                    self.visible_characters[name] = True

        # Image screen rendering
        if self.image_screen_active:
            if self.image_screen_surface:
                sw, sh = screen.get_size()
                img = self.image_screen_surface
                iw, ih = img.get_size()
                screen.blit(img, ((sw - iw) // 2, (sh - ih) // 2))
            return  # don't draw anything else while image screen is active

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
        # Determine left/right names for multi-character rendering
        left_name = "Partner"  # e.g. Ellie
        right_name = "Player"  # e.g. Vera

        # Helper function: safely get a Surface for a character + emotion
        def _get_sprite(name, emotion_key="neutral"):
            if name not in scene.characters:
                return None
            char_data = scene.characters[name]
            if isinstance(char_data, dict):
                return char_data.get(emotion_key, char_data.get("neutral"))
            return char_data  # fallback if Surface directly stored

        # Determine active speaker for dimming
        active_speaker = None
        if speaker and self.visible_characters.get(speaker, False):
            active_speaker = speaker

        # Draw left character if visible
        left_sprite = _get_sprite(left_name, emotion if speaker == left_name else "neutral")
        if left_sprite and self.visible_characters.get(left_name, True):
            try:
                alpha_val = 255 if active_speaker == left_name else 120
                sprite_to_draw = left_sprite.copy()
                sprite_to_draw.set_alpha(alpha_val)
                screen.blit(sprite_to_draw, (100, 200))
            except Exception:
                screen.blit(left_sprite, (100, 200))

        # Draw right character if visible
        right_sprite = _get_sprite(right_name, emotion if speaker == right_name else "neutral")
        if right_sprite and self.visible_characters.get(right_name, True):
            try:
                sw = screen.get_width()
                sprite_w = right_sprite.get_width()
                right_x = max(sw - sprite_w - 100, 300)
                alpha_val = 255 if active_speaker == right_name else 120
                sprite_to_draw = right_sprite.copy()
                sprite_to_draw.set_alpha(alpha_val)
                screen.blit(sprite_to_draw, (right_x, 200))
            except Exception:
                screen.blit(right_sprite, (sw - sprite_w - 100, 200))

        # Draw text / choices on top
        if line_type in ["line", "narration"]:
            text = self.current_line.get("line", "")

            # Speaker name
            if speaker:
                display_name = self.name_map.get(speaker, speaker)
                # Draw speaker name slightly above dialogue text
                name_surf = self.font.render(f"{display_name}:", True, self.color)
                name_y = y_offset - self.font.get_linesize() - 5
                screen.blit(name_surf, (self.pos[0], name_y))

            # Draw wrapped dialogue text
            max_width = screen.get_width() - self.pos[0] - 40
            self.draw_wrapped_text(
                screen,
                text,
                self.pos[0],
                y_offset,
                max_width
            )

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

        elif line_type == "choice":
            choices = self.current_line.get("choices", [])
            rel_value = self.relationship.get() if self.relationship else 0

            for i, choice in enumerate(choices):
                locked = False

                # Check lock condition (e.g. "relationship < 0")
                condition = choice.get("lock_condition")
                if condition:
                    locked = self.evaluate_condition(condition, rel_value)

                prefix = "X " if locked else "> " if i == getattr(self, "selected_choice", -1) else ""
                color = (150, 150, 150) if locked else self.color

                surf = self.font.render(f"{prefix}{choice['text']}", True, color)
                screen.blit(surf, (self.pos[0], y_offset + i * self.font.get_height() * 1.5))

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
        rel_value = self.relationship.get() if self.relationship else 0

        for i, choice in enumerate(choices):
            choice_y_top = y_start + i * choice_height
            choice_y_bottom = choice_y_top + choice_height
            if choice_y_top <= mouse_y <= choice_y_bottom:

                # Check lock condition
                locked = False
                condition = choice.get("lock_condition")
                if condition:
                    locked = self.evaluate_condition(condition, rel_value)

                if locked:
                    return None  # do nothing if locked

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
        if self.image_screen_active:
            self.image_screen_active = False
            self.image_screen_surface = None
            self.index += 1
            return self.start_line()

        if line_type == "choice" and mouse_pos is not None:
            # delegate to choice click handler
            return self.handle_click(mouse_pos)
        else:
            # advance a normal line manually (skips voice wait)
            self.index += 1
            return self.start_line()

    def evaluate_condition(self, condition, rel):
        condition = condition.replace("relationship", str(rel))

        try:
            return eval(condition)
        except:
            return False

# -----------------------
# Game Manager
# -----------------------
class GameManager:
    # Manages scenes, dialogue progression, and drawing
    def __init__(self, screen, scenes, audio_manager, font, relationship_tracker):
        self.screen = screen
        self.scenes = scenes
        self.audio = audio_manager
        self.font = font
        self.relationship_tracker = relationship_tracker

        self.current_scene_index = 0
        self.current_scene = scenes[0]

        self.dialogue_system = DialogueSystem(
            self.current_scene.dialogue,
            self.audio,
            self.font
        )

        self.current_line = self.dialogue_system.start_line()
        self.active = True

        self.current_music = None

    def play_scene_music(self):
        scene = self.current_scene
        if scene.background_music and scene.background_music != self.current_music:
            try:
                pygame.mixer.music.load(scene.background_music)
                pygame.mixer.music.set_volume(0.5)
                pygame.mixer.music.play(-1)  # loop
                self.current_music = scene.background_music
            except Exception as e:
                print(f"Failed to load music '{scene.background_music}': {e}")

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

        # draw background
        self.screen.blit(scene.background, (0, 0))

        # let DialogueSystem handle characters, text, and choices
        self.dialogue_system.draw(self.screen, scene)

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
        self.play_scene_music()  # <-- music changes with scene

    def start_next_scene(self):
        """
        Chooses which scene to load based on relationship points.
        """
        current_id = self.current_scene.id

        if current_id == "scene_2":
            # Branching logic here
            if self.relationship_tracker.points > 0:
                self.load_scene("scene_2.5")
            else:
                self.load_scene("scene_3")
            return

        # Default linear progression
        next_scene_id = self.current_scene.next_scene
        if next_scene_id:
            self.load_scene(next_scene_id)