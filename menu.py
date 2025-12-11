import pygame, pygame_gui
import nightfall
from menu_audio import MenuAudio


def run_menu():
    pygame.init()
    screen = pygame.display.set_mode((1280, 720))
    pygame.display.set_caption("Nightfall - POC Edition")

    clock = pygame.time.Clock()

    # GUI Manager
    manager = pygame_gui.UIManager((1280, 720))

    # Audio system
    audio = MenuAudio()
    audio.play_music()

    # Background
    background = pygame.image.load("assets/backgrounds/scene2_5.png").convert()
    background = pygame.transform.scale(background, (1280, 720))

    # Main menu buttons
    button_new = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect((540, 200), (200, 50)),
        text="Play",
        manager=manager
    )

    button_settings = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect((540, 260), (200, 50)),
        text="Settings",
        manager=manager
    )

    button_credits = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect((540, 320), (200, 50)),
        text="Credits",
        manager=manager
    )

    # Settings panel
    settings_panel = pygame_gui.elements.UIPanel(
        relative_rect=pygame.Rect((340, 160), (600, 400)),
        starting_height=1,
        manager=manager
    )
    settings_panel.hide()

    pygame_gui.elements.UILabel(
        relative_rect=pygame.Rect((0, 10), (600, 40)),
        text="Settings",
        manager=manager,
        container=settings_panel
    )

    # Volume slider logic
    volume_slider = pygame_gui.elements.UIHorizontalSlider(
        relative_rect=pygame.Rect((50, 100), (500, 40)),
        start_value=50,  # middle by default
        value_range=(0, 100),
        manager=manager,
        container=settings_panel
    )

    # a fix to initialize actual volume
    initial_volume = volume_slider.get_current_value() / 100.0
    audio.set_volume(initial_volume)

    close_settings = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect((225, 300), (150, 50)),
        text="Close",
        manager=manager,
        container=settings_panel
    )

    # Credits panel
    credits_panel = pygame_gui.elements.UIPanel(
        relative_rect=pygame.Rect((340, 160), (600, 400)),
        starting_height=1,
        manager=manager
    )
    credits_panel.hide()

    credits_text = (
        "Nightfall\n\n"
        "Created by Riho Luik\n"
        "Programming by Riho\n"
        "Story by Riho\n"
        "Music & most SFX by Riho\n"
        "Art & Backgrounds by Riho\n"
        "A lot of SFX gotten from freesound.org\n"
        "SFX edited together by Riho\n\n"
        "Thanks for playing!"
    )

    credits_box = pygame_gui.elements.UITextBox(
        html_text=credits_text,
        relative_rect=pygame.Rect((20, 20), (560, 300)),
        manager=manager,
        container=credits_panel
    )

    close_credits = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect((225, 330), (150, 50)),
        text="Close",
        manager=manager,
        container=credits_panel
    )

    overlay_active = False
    running = True

    while running:
        time_delta = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            manager.process_events(event)

            # Hover SFX
            if event.type == pygame_gui.UI_BUTTON_ON_HOVERED:
                audio.play_hover()

            # Volume slider logic
            if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
                if event.ui_element == volume_slider:
                    new_volume = event.value / 100.0
                    audio.set_volume(new_volume)

            # Button click logic
            if event.type == pygame_gui.UI_BUTTON_PRESSED:
                audio.play_click()

                if not overlay_active:
                    if event.ui_element == button_new:
                        audio.stop_music()
                        nightfall.run_game()

                    elif event.ui_element == button_settings:
                        settings_panel.show()
                        overlay_active = True

                    elif event.ui_element == button_credits:
                        credits_panel.show()
                        overlay_active = True

                if event.ui_element == close_settings:
                    settings_panel.hide()
                    overlay_active = False

                if event.ui_element == close_credits:
                    credits_panel.hide()
                    overlay_active = False

        manager.update(time_delta)

        screen.blit(background, (0, 0))
        manager.draw_ui(screen)
        pygame.display.flip()

    pygame.quit()