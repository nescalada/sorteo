import pygame
import random
import moviepy as mpy

from utils.helpers import ranking, kill_feed, load_config, get_dynamic_radius, load_particles, check_collisions, display_winner, add_particle_to_frames, remove_dead_particles
import datetime
import gc
import time


# Initialize global variables
running = True
winner_shown = False
top_dying_players = {}

# Load configuration
config = load_config('config.yaml')

WIDTH = config['screen']['width']
HEIGHT = config['screen']['height']
FPS = config['screen']['fps']

MIN_RADIUS = config['particles']['min_radius']
MAX_RADIUS = config['particles']['max_radius']
MAX_HP = config['particles']['max_hp']
MAX_SPEED = config['particles']['max_speed']
ACC_MAGNITUDE = config['particles']['acc_magnitude']

BG_COLOR = tuple(config['colors']['background'])

IMG_PATH = config['images']['path']
LOCAL_IMAGES = config['images']['local']

# Initialize Pygame
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Particle Simulation")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 36)
feed_font = pygame.font.SysFont(None, 26)
small_font = pygame.font.SysFont(None, 20)

def draw_top_leaderboard(screen, particles, small_font):
    global top_dying_players
    current_time = pygame.time.get_ticks()
    
    # Get alive particles sorted by HP (descending)
    alive_particles = [p for p in particles if p.alive]
    alive_particles.sort(key=lambda x: x.hp, reverse=True)
    
    # Get top
    top = alive_particles[:5]
    
    # Check for players that just died (not in current top but were before)
    current_top_ids = {p.id for p in top}
    
    # Remove expired dying players (after 20ms)
    expire_ms = 1000  # 1 segundo
    expired_players = [player_id for player_id, death_time in top_dying_players.items()
                   if current_time - death_time > expire_ms]
    
    for player_id in expired_players:
        del top_dying_players[player_id]
    
    # Draw TOP table
    table_x = 20
    table_y = 60
    row_height = 25
    
    # Title
    title_text = small_font.render("TOP 3", True, (255, 255, 255))
    title_rect = title_text.get_rect(topleft=(table_x, table_y))
    
    # Title background
    title_bg = pygame.Surface((title_rect.width + 10, title_rect.height + 5), pygame.SRCALPHA)
    title_bg.fill((0, 0, 0, 150))
    #screen.blit(title_bg, (title_rect.left - 5, title_rect.top - 2))
    #screen.blit(title_text, title_rect)
    
    # Draw each player in the top
    for i, particle in enumerate(top):
        y_pos = table_y + 32 + (i * row_height)
        
        # Check if this player is dying (red color for 20ms)
        text_color = (255, 255, 255)  # Default white
        if particle.id in top_dying_players:
            text_color = (255, 0, 0)  # Red for dying players
        
        # Player text with position number
        player_text = f"{i+1}. {particle.id} ({int(particle.hp)} HP)"
        text_surface = small_font.render(player_text, True, text_color)
        text_rect = text_surface.get_rect(topleft=(table_x, y_pos))
        
        # Text background
        text_bg = pygame.Surface((text_rect.width + 10, text_rect.height + 2), pygame.SRCALPHA)
        text_bg.fill((0, 0, 0, 120))
        screen.blit(text_bg, (text_rect.left - 5, text_rect.top - 1))
        screen.blit(text_surface, text_rect)

# Create a timestamp 
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# Init frames
frames = []

# Load particles
particles = load_particles(MIN_RADIUS, MAX_RADIUS, MAX_HP, MAX_SPEED, ACC_MAGNITUDE, WIDTH, HEIGHT, IMG_PATH, LOCAL_IMAGES)
num_particles = len(particles)

# Demora para empezar a jugar
start_time = pygame.time.get_ticks()  # tiempo en ms al iniciar el juego
preparation_duration_ms = 1500

# Main loop
ranking = []  # inicializar ranking aquí
previous_alive_ids = {p.id for p in particles if p.alive}

while running:
    frame_number = len(frames)
    clock.tick(FPS)
    screen.fill(BG_COLOR)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    RADIUS = get_dynamic_radius(particles, WIDTH, HEIGHT, MIN_RADIUS, MAX_RADIUS)
    CELL_SIZE = RADIUS * 2
    grid_width = WIDTH // CELL_SIZE + 1
    grid_height = HEIGHT // CELL_SIZE + 1

    current_time = pygame.time.get_ticks()
    preparation_phase = current_time - start_time < preparation_duration_ms

    # 1) mover primero (no dibujar todavía)
    for p in particles:
        p.move()

    # 2) dibujar partículas siempre
    for p in particles:
        p.draw(screen)

    # 3) si no estamos en la fase de preparación, resolver colisiones y muerte
    if not preparation_phase:
        check_collisions(RADIUS, CELL_SIZE, grid_width, grid_height, particles, timestamp, frame_number)
        
        current_alive_ids = {p.id for p in particles if p.alive}
        newly_dead = previous_alive_ids - current_alive_ids
        for dead_id in newly_dead:
            top_dying_players[dead_id] = current_time
        previous_alive_ids = current_alive_ids

        particles = remove_dead_particles(particles)

    # 4) contar vivos después de eliminar
    alive_count = len(particles)

    # 5) si hay más de uno, recién ahí dibujar y mostrar contador
    if alive_count > 1 and not winner_shown:
        for p in particles:
            p.draw(screen)

        # contador solo si no hay ganador
        text_str = f"Seguidores vivos: {alive_count}"
        text = font.render(text_str, True, (255, 255, 255))
        text_rect = text.get_rect(topleft=(100, 260))

        padding = 5
        bg_surface = pygame.Surface((text_rect.width + 2*padding, text_rect.height + 2*padding), pygame.SRCALPHA)
        bg_surface.fill((0, 0, 0, 150))
        screen.blit(bg_surface, (text_rect.left - padding, text_rect.top - padding))
        screen.blit(text, text_rect)

        
    # ---- DIBUJAR TOP ----
    if top_dying_players:
        draw_top_leaderboard(screen, particles, small_font)

    # ---- DIBUJAR KILL FEED ----
    padding = 5
    start_y = 60
    now = time.time()

    # mostrar solo las muertes que tengan <= 1s de vida o mientras sean parte de las últimas 5
    visible_kills = []
    for killer, victim, tstamp in kill_feed:
        visible_kills.append((killer, victim))

    for i, (killer, victim) in enumerate(visible_kills):
        killer_text = feed_font.render(killer, True, (255, 255, 255))
        action_text = feed_font.render(" eliminó a ", True, (255, 0, 0))
        victim_text = feed_font.render(victim, True, (255, 255, 255))

        total_width = killer_text.get_width() + action_text.get_width() + victim_text.get_width()
        total_height = killer_text.get_height()
        text_surface = pygame.Surface((total_width, total_height), pygame.SRCALPHA)
        text_surface.blit(killer_text, (0, 0))
        text_surface.blit(action_text, (killer_text.get_width(), 0))
        text_surface.blit(victim_text, (killer_text.get_width() + action_text.get_width(), 0))

        bg_surface = pygame.Surface(
            (text_surface.get_width() + 2*padding, text_surface.get_height() + 2*padding),
            pygame.SRCALPHA
        )
        bg_surface.fill((0, 0, 0, 150))

        y_pos = start_y + i * (total_height + 6)
        screen.blit(bg_surface, (15, y_pos))
        screen.blit(text_surface, (15 + padding, y_pos + padding))

    # 6) si queda 1 vivo, NO dibujar partículas (evita el rojo) y mostrar ganador
    if alive_count == 1 and not winner_shown:
        screen.fill(BG_COLOR)           # limpia cualquier resto
        # opcional: asegurar que no haya overlay activo en el último vivo
        for p in particles:
            p.collision_time = -1e9

        display_winner(font, particles, screen, WIDTH, HEIGHT, RADIUS)
        winner_shown = True
        frames = add_particle_to_frames(screen, frames)
        pygame.time.wait(2000)
        running = False

    pygame.display.flip()
    frames = add_particle_to_frames(screen, frames)

# Repeat last frame for 2 seconds
frames += [frames[-1]] * 2 * FPS  # Assuming 60 FPS

# Store each frame in a tmp file just in case
# for i, frame in enumerate(frames):
#    mpy.ImageClip(frame).save_frame(f"simulations/{timestamp}/frame_{i:04d}.png")

clip = mpy.ImageSequenceClip(frames, fps=FPS)
clip.write_videofile(f"simulations/{timestamp}_simulation.mp4", codec='libx264')

# Esperar a que se presione Enter antes de cerrar
waiting = True
while waiting:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:  # cerrar con la X
            waiting = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:  # tecla Enter
            waiting = False
    pygame.display.flip()

# Clean up variables to free RAM except for frames
del particles
del config
del font
del screen
del clock
del IMG_PATH
del LOCAL_IMAGES

gc.collect()

pygame.quit()