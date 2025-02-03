import pygame
import sys
import random
import math
import io
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ------------------------------
# Global Constants and Settings
# ------------------------------
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
CELL_SIZE = 20
TOP_MARGIN = 80  # Reserve space at the top for the question bar

# The grid now covers the play area (excluding the top margin)
GRID_WIDTH = SCREEN_WIDTH // CELL_SIZE
GRID_HEIGHT = (SCREEN_HEIGHT - TOP_MARGIN) // CELL_SIZE

FPS = 10

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 180, 0)
DARKGREEN = (0, 120, 0)
RED = (200, 0, 0)
DARKRED = (150, 0, 0)
BLUE = (0, 0, 200)
DARKBLUE = (0, 0, 150)
GRAY = (200, 200, 200)
DARKGRAY = (50, 50, 50)

# -------------------------------------------
# Unit Circle Values (only standard angles)
# -------------------------------------------
# For sin and cos: π/6, π/4, π/3, π/2.
# For tan: π/6, π/4, π/3.
base_vals = {
    "sin": {
        math.pi / 6: r"\frac{1}{2}",
        math.pi / 4: r"\frac{\sqrt{2}}{2}",
        math.pi / 3: r"\frac{\sqrt{3}}{2}",
        math.pi / 2: "1"
    },
    "cos": {
        math.pi / 6: r"\frac{\sqrt{3}}{2}",
        math.pi / 4: r"\frac{\sqrt{2}}{2}",
        math.pi / 3: r"\frac{1}{2}",
        math.pi / 2: "0"
    },
    "tan": {
        math.pi / 6: r"\frac{1}{\sqrt{3}}",
        math.pi / 4: "1",
        math.pi / 3: r"\sqrt{3}"
    }
}

# For constructing full-angle LaTeX strings.
angle_fractions = {
    math.pi / 6: (1, 6),
    math.pi / 4: (1, 4),
    math.pi / 3: (1, 3),
    math.pi / 2: (1, 2)
}

# --------------------------------------------------
# Caching for rendered LaTeX text (via matplotlib)
# --------------------------------------------------
latex_cache = {}


def render_latex(text, fontsize=24, color="black"):
    """
    Render a LaTeX string (without surrounding $…$) to a pygame Surface.
    Uses matplotlib to produce a PNG image (cached for performance).
    """
    key = (text, fontsize, color)
    if key in latex_cache:
        return latex_cache[key]
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, f"${text}$", fontsize=fontsize, color=color)
    buffer = io.BytesIO()
    plt.axis('off')
    plt.savefig(buffer, format='png', bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)
    buffer.seek(0)
    image = pygame.image.load(buffer)
    image = image.convert_alpha()
    latex_cache[key] = image
    return image


# ---------------------------------------------------
# Calculate the full angle in LaTeX given a base angle and quadrant.
# ---------------------------------------------------
def get_full_angle_latex(base_angle, quadrant):
    if abs(base_angle - math.pi / 2) < 1e-6:
        return r"\frac{\pi}{2}" if quadrant in [1, 2] else r"\frac{3\pi}{2}"
    num, den = angle_fractions[base_angle]
    if quadrant == 1:
        n = num
    elif quadrant == 2:
        n = den - num
    elif quadrant == 3:
        n = den + num
    elif quadrant == 4:
        n = 2 * den - num
    return r"\frac{" + (f"{n}\pi" if n != 1 else r"\pi") + r"}{" + str(den) + "}"


# ---------------------------------------------------
# Given a trig function, base angle, and quadrant, return the LaTeX–formatted answer.
# ---------------------------------------------------
def get_adjusted_answer(func, base_angle, quadrant):
    value_str = base_vals[func][base_angle]
    if value_str == "0":
        return "0"
    if func == "sin":
        return ("-" if quadrant in [3, 4] else "") + value_str
    elif func == "cos":
        return ("-" if quadrant in [2, 3] else "") + value_str
    elif func == "tan":
        return ("-" if quadrant in [2, 4] else "") + value_str


# ---------------------------------------------------
# Generate a new question based on settings.
# ---------------------------------------------------
def generate_question(settings):
    enabled_funcs = [f for f, enabled in settings["functions"].items() if enabled]
    enabled_quads = [q for q, enabled in settings["quadrants"].items() if enabled]
    if not enabled_funcs or not enabled_quads:
        enabled_funcs = ["sin"]
        enabled_quads = [1]
    func = random.choice(enabled_funcs)
    valid_bases = list(base_vals[func].keys())
    base_angle = random.choice(valid_bases)
    quadrant = random.choice(enabled_quads)
    angle_latex = get_full_angle_latex(base_angle, quadrant)
    question_str = f"{func}({angle_latex})"
    correct_answer = get_adjusted_answer(func, base_angle, quadrant)
    return func, question_str, correct_answer


# ---------------------------------------------------
# Get a random grid cell for a food.
# Foods now spawn with a margin of 3 cells from the edges.
# Also, ensure that foods are at least 3 cells apart.
# ---------------------------------------------------
def get_random_food_position(snake_positions, current_foods):
    margin = 3
    while True:
        x = random.randint(margin, GRID_WIDTH - margin - 1)
        y = random.randint(margin, GRID_HEIGHT - margin - 1)
        if (x, y) in snake_positions:
            continue
        conflict = False
        for food in current_foods:
            fx, fy = food["pos"]
            if abs(x - fx) < 3 and abs(y - fy) < 3:
                conflict = True
                break
        if conflict:
            continue
        return (x, y)


# ---------------------------------------------------
# Generate food items: one correct answer and distractors.
# ---------------------------------------------------
def generate_foods(func, correct_answer, snake_positions):
    possible_answers = set()
    for base in base_vals[func]:
        for quad in [1, 2, 3, 4]:
            possible_answers.add(get_adjusted_answer(func, base, quad))
    if correct_answer in possible_answers:
        possible_answers.remove(correct_answer)
    num_distractors = min(3, len(possible_answers))
    distractors = random.sample(list(possible_answers), num_distractors)
    food_values = distractors + [correct_answer]
    random.shuffle(food_values)
    foods = []
    for value in food_values:
        pos = get_random_food_position(snake_positions, foods)
        foods.append({"pos": pos, "value": value})
    return foods


# ---------------------------------------------------
# Collision Check for Food.
# Instead of exact cell equality, we compute the distance between centers.
# If the distance is less than a threshold (15 pixels), we count it as a hit.
# ---------------------------------------------------
def food_collision(snake_cell, food_cell):
    # Convert cell coordinates to pixel centers.
    snake_x = snake_cell[0] * CELL_SIZE + CELL_SIZE / 2
    snake_y = snake_cell[1] * CELL_SIZE + TOP_MARGIN + CELL_SIZE / 2
    food_x = food_cell[0] * CELL_SIZE + CELL_SIZE / 2
    food_y = food_cell[1] * CELL_SIZE + TOP_MARGIN + CELL_SIZE / 2
    dx = snake_x - food_x
    dy = snake_y - food_y
    dist = math.sqrt(dx * dx + dy * dy)
    return dist < 30


# ---------------------------------------------------
# Create Heart Sprite (Lives Indicator) procedurally.
# This function draws a heart shape on a transparent Surface.
# ---------------------------------------------------
def create_heart_sprite(size):
    """
    Create a heart-shaped Surface of dimensions (size x size).
    Draw two circles and a triangle to simulate a heart.
    """
    heart = pygame.Surface((size, size), pygame.SRCALPHA)
    red = (255, 0, 0)
    # Draw the left circle.
    pygame.draw.circle(heart, red, (size // 3, size // 3), size // 3)
    # Draw the right circle.
    pygame.draw.circle(heart, red, (2 * size // 3, size // 3), size // 3)
    # Draw the bottom triangle.
    pygame.draw.polygon(heart, red, [(0, size // 3), (size, size // 3), (size // 2, size)])
    return heart


# Preload the heart sprite (28x28 pixels).
HEART_SPRITE = create_heart_sprite(28)


# ---------------------------------------------------
# UI Elements: Button and Checkbox
# ---------------------------------------------------
class Button:
    def __init__(self, rect, text, font_size=36, bg_color=GRAY):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.bg_color = bg_color
        self.font = pygame.font.SysFont(None, font_size)

    def draw(self, surface):
        pygame.draw.rect(surface, self.bg_color, self.rect, border_radius=8)
        pygame.draw.rect(surface, BLACK, self.rect, 2, border_radius=8)
        text_surf = self.font.render(self.text, True, BLACK)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)


class Checkbox:
    def __init__(self, rect, text, checked=False, font_size=28):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.checked = checked
        self.font = pygame.font.SysFont(None, font_size)
        self.hitbox = self.rect.inflate(10, 10)

    def draw(self, surface):
        # Draw rounded rectangle for the box.
        pygame.draw.rect(surface, WHITE, self.rect, border_radius=5)
        pygame.draw.rect(surface, BLACK, self.rect, 2, border_radius=5)
        if self.checked:
            start = (self.rect.left + 5, self.rect.centery)
            mid = (self.rect.left + self.rect.width // 3, self.rect.bottom - 5)
            end = (self.rect.right - 5, self.rect.top + 5)
            pygame.draw.lines(surface, DARKGREEN, False, [start, mid, end], 3)
        # Draw label to the right.
        text_surf = self.font.render(self.text, True, BLACK)
        text_rect = text_surf.get_rect(midleft=(self.rect.right + 10, self.rect.centery))
        surface.blit(text_surf, text_rect)

    def toggle(self):
        self.checked = not self.checked

    def is_clicked(self, pos):
        return self.hitbox.collidepoint(pos)


# -----------------------
# Main Menu Functionality
# -----------------------
def main_menu(screen):
    clock = pygame.time.Clock()
    title_font = pygame.font.SysFont(None, 60)
    play_button = Button((SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 60, 200, 50), "Play", font_size=40)
    settings_button = Button((SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 + 10, 200, 50), "Settings", font_size=40)

    while True:
        screen.fill(WHITE)
        title_surf = title_font.render("Unit Circle Snake Game", True, DARKRED)
        title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4))
        screen.blit(title_surf, title_rect)
        play_button.draw(screen)
        settings_button.draw(screen)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit();
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                if play_button.is_clicked(pos):
                    return "PLAYING"
                if settings_button.is_clicked(pos):
                    return "SETTINGS"

        pygame.display.flip()
        clock.tick(30)


# --------------------------
# Settings Menu Functionality
# --------------------------
def settings_menu(screen, settings):
    clock = pygame.time.Clock()
    title_font = pygame.font.SysFont(None, 60)

    # Create checkboxes for trig functions.
    func_checkboxes = []
    funcs = ["sin", "cos", "tan"]
    for i, func in enumerate(funcs):
        cb = Checkbox((100, 120 + i * 50, 40, 40), func, settings["functions"].get(func, True))
        func_checkboxes.append(cb)

    # Create checkboxes for quadrants.
    quad_checkboxes = []
    for q in [1, 2, 3, 4]:
        cb = Checkbox((350, 120 + (q - 1) * 50, 40, 40), f"Quadrant {q}", settings["quadrants"].get(q, True))
        quad_checkboxes.append(cb)

    back_button = Button((SCREEN_WIDTH // 2 - 50, SCREEN_HEIGHT - 80, 100, 40), "Back", font_size=30)

    while True:
        screen.fill(WHITE)
        title_surf = title_font.render("Settings", True, DARKBLUE)
        title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, 50))
        screen.blit(title_surf, title_rect)

        for cb in func_checkboxes:
            cb.draw(screen)
        for cb in quad_checkboxes:
            cb.draw(screen)
        back_button.draw(screen)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit();
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                for cb in func_checkboxes:
                    if cb.is_clicked(pos):
                        cb.toggle()
                for cb in quad_checkboxes:
                    if cb.is_clicked(pos):
                        cb.toggle()
                if back_button.is_clicked(pos):
                    # Update settings based on checkbox states.
                    for cb in func_checkboxes:
                        settings["functions"][cb.text] = cb.checked
                    for cb in quad_checkboxes:
                        q_num = int(cb.text.split()[-1])
                        settings["quadrants"][q_num] = cb.checked
                    return settings

        pygame.display.flip()
        clock.tick(30)


# --------------------------
# Draw the Game (Snake, Foods, UI)
# --------------------------
def draw_game(screen, snake, foods, question_str, lives):
    screen.fill(WHITE)

    # Draw the question bar (centered within TOP_MARGIN).
    q_surface = render_latex(question_str, fontsize=32, color="black")
    q_rect = q_surface.get_rect(center=(SCREEN_WIDTH // 2, TOP_MARGIN // 2))
    screen.blit(q_surface, q_rect)

    # Draw lives as heart sprites in the upper right.
    spacing = 10
    heart_width = HEART_SPRITE.get_width()
    for i in range(lives):
        x = SCREEN_WIDTH - (heart_width + spacing) * (i + 1)
        y = 10
        screen.blit(HEART_SPRITE, (x, y))

    # Draw snake (offset by TOP_MARGIN).
    for segment in snake:
        rect = pygame.Rect(segment[0] * CELL_SIZE, segment[1] * CELL_SIZE + TOP_MARGIN, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(screen, DARKGREEN, rect)
        pygame.draw.rect(screen, GREEN, rect, 2)

    # Draw foods using math text with a smaller fontsize (14).
    for food in foods:
        x, y = food["pos"]
        food_surface = render_latex(food["value"], fontsize=14, color="black")
        cell_rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE + TOP_MARGIN, CELL_SIZE, CELL_SIZE)
        food_rect = food_surface.get_rect(center=cell_rect.center)
        screen.blit(food_surface, food_rect)


# --------------------------
# Game Loop (PLAYING state)
# --------------------------
def game_loop(screen, settings):
    clock = pygame.time.Clock()
    # Initialize snake in center of board.
    snake = [(GRID_WIDTH // 2, GRID_HEIGHT // 2)]
    direction = (1, 0)
    lives = 3
    score = 0

    func, question_str, correct_answer = generate_question(settings)
    foods = generate_foods(func, correct_answer, snake)

    running = True
    while running:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit();
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP and direction != (0, 1):
                    direction = (0, -1)
                elif event.key == pygame.K_DOWN and direction != (0, -1):
                    direction = (0, 1)
                elif event.key == pygame.K_LEFT and direction != (1, 0):
                    direction = (-1, 0)
                elif event.key == pygame.K_RIGHT and direction != (-1, 0):
                    direction = (1, 0)

        head_x, head_y = snake[0]
        dx, dy = direction
        new_head = (head_x + dx, head_y + dy)

        # Check collision with walls (game board boundaries).
        if new_head[0] < 0 or new_head[0] >= GRID_WIDTH or new_head[1] < 0 or new_head[1] >= GRID_HEIGHT:
            running = False
            continue

        # Check collision with self.
        if new_head in snake:
            running = False
            continue

        snake.insert(0, new_head)

        # Use our new collision function to detect food hits.
        ate_food = False
        food_eaten = None
        for food in foods:
            if food_collision(new_head, food["pos"]):
                ate_food = True
                food_eaten = food
                break

        if ate_food:
            if food_eaten["value"] == correct_answer:
                score += 1
                func, question_str, correct_answer = generate_question(settings)
                foods = generate_foods(func, correct_answer, snake)
            else:
                lives -= 1
                foods.remove(food_eaten)
                snake.pop()  # Do not grow.
                if lives <= 0:
                    running = False
        else:
            snake.pop()

        draw_game(screen, snake, foods, question_str, lives)
        pygame.display.flip()

    game_over(screen, score)


# --------------------------
# Game Over Screen
# --------------------------
def game_over(screen, score):
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 60)
    small_font = pygame.font.SysFont(None, 40)
    while True:
        screen.fill(WHITE)
        over_text = font.render("Game Over", True, RED)
        score_text = small_font.render("Score: " + str(score), True, BLACK)
        prompt_text = small_font.render("Press Enter to return to menu", True, BLACK)
        screen.blit(over_text, over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3)))
        screen.blit(score_text, score_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3 + 60)))
        screen.blit(prompt_text, prompt_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3 + 120)))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit();
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    return
        pygame.display.flip()
        clock.tick(30)


# --------------------------
# Main Program Loop
# --------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Unit Circle Snake Game")
    settings = {
        "functions": {"sin": True, "cos": True, "tan": True},
        "quadrants": {1: True, 2: True, 3: True, 4: True}
    }
    state = "MENU"
    while True:
        if state == "MENU":
            next_state = main_menu(screen)
            state = next_state
        elif state == "SETTINGS":
            settings = settings_menu(screen, settings)
            state = "MENU"
        elif state == "PLAYING":
            game_loop(screen, settings)
            state = "MENU"


if __name__ == "__main__":
    main()
