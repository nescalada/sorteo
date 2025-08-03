import pygame
import random
import moviepy as mpy

from utils import load_config, get_dynamic_radius, load_particles, check_collisions, display_winner, add_particle_to_frames, remove_dead_particles
import datetime


# Initialize global variables
running = True
winner_shown = False

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
font = pygame.font.SysFont(None, 24)

# Create a timestamp 
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# Init frames
frames = []

# Load particles
particles = load_particles(MIN_RADIUS, MAX_HP, MAX_SPEED, ACC_MAGNITUDE, WIDTH, HEIGHT, IMG_PATH, LOCAL_IMAGES)
num_particles = len(particles)

# Main loop
while running:
    clock.tick(FPS)
    screen.fill(BG_COLOR)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    RADIUS = get_dynamic_radius(particles, MIN_RADIUS, MAX_RADIUS)

    CELL_SIZE = RADIUS * 2
    grid_width = WIDTH // CELL_SIZE + 1
    grid_height = HEIGHT // CELL_SIZE + 1

    # Move and draw particles
    for p in particles:
        p.move()
        p.draw(screen)
    
    # Show count of alive particles
    alive_count = sum(1 for p in particles if p.alive)
    font_big = pygame.font.SysFont(None, 36)
    text = font_big.render(f"Alive: {alive_count}", True, (255,255,255))
    screen.blit(text, (30, 30))

    # Show winner if only one particle remains
    if alive_count == 1 and not winner_shown:
        display_winner(font, particles, screen, WIDTH, HEIGHT, RADIUS)
        
        frames = add_particle_to_frames(screen, frames)

        pygame.time.wait(2000)
        running = False

    check_collisions(RADIUS, CELL_SIZE, grid_width, grid_height, particles, timestamp)

    # Remove dead particles from the list
    particles = remove_dead_particles(particles)

    pygame.display.flip()

    frames = add_particle_to_frames(screen, frames)

# Repeat last frame for 2 seconds
frames += [frames[-1]] * 2 * FPS  # Assuming 60 FPS

clip = mpy.ImageSequenceClip(frames, fps=FPS)
clip.write_videofile(f"simulations/{timestamp}_simulation.mp4", codec='libx264')

pygame.quit()