from turtle import width
import yaml
import pygame
import numpy as np
import os
import pandas as pd
import random
import re
import time

from particle import Particle
import requests
from io import BytesIO
from tqdm import tqdm

def safe_filename(name: str) -> str:
    # Permitir solo letras, números, guiones y guiones bajos
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)

def load_config(path='config.yaml'):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

# Calculate dynamic radius based on number of particles
def get_dynamic_radius(particles, width, height, min_radius, max_radius, change_radius=True):
    num_particles = len(particles)
    best_radius = min_radius

    for r in range(max_radius, min_radius - 1, -1):
        cell_size = 4 * r 
        cols = width // cell_size
        rows = height // cell_size
        if cols * rows >= num_particles:
            best_radius = r
            break

    if change_radius:
        for p in particles:
            p.radius = best_radius

    return best_radius

# Create a circular mask for particle images
def circular_mask(image):
    size = image.get_size()
    mask_surface = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.circle(mask_surface, (255, 255, 255, 255), (size[0]//2, size[1]//2), min(size)//2)
    image.blit(mask_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return image

# Assign positions for particles in a grid-like manner to avoid overlap
def assign_position(radius, width, height, num_particles):
        cell_size = 2 * radius + 1
        cols = int(width // cell_size)
        rows = int(height // cell_size)

        if num_particles > cols * rows:
            raise ValueError("Not enough space to place all particles without overlap.")

        available_cells = [(col, row) for col in range(cols) for row in range(rows)]
        random.shuffle(available_cells)

        positions = []

        for i in range(num_particles):
            if not available_cells:
                raise RuntimeError("Not enough space to place all particles without overlap.")

            col, row = available_cells.pop()
            x = col * cell_size + radius
            y = row * cell_size + radius
            positions.append(np.array([float(x), float(y)]))

        return positions

# Load particles from a CSV file
def load_particles(min_radius, max_radius, max_hp, max_speed, acc_magnitude, width, height, image_path, local_images):

    if local_images:
        # Read how many particle images are available
        num_particles = len([f for f in os.listdir(image_path) if f.endswith('.png')])
            
        if num_particles == 0:
            raise ValueError("No particle images found in the 'img' directory.")

        # Load and mask particle images
        particle_images = [circular_mask(pygame.image.load(f'{image_path}/particle_{i}.png').convert_alpha()) for i in range(num_particles)]

        radius = get_dynamic_radius(particle_images, width, height, min_radius, max_radius, change_radius=False)

        positions = assign_position(radius, width, height, num_particles)

        # Create particles
        particles = [Particle(i, particle_images[i], radius, max_hp, max_speed, acc_magnitude, width, height, positions[i]) for i in range(num_particles)]
    
    else:
        # Ensure image_path is a CSV file, not a directory
        if os.path.isdir(image_path):
            # Find the first CSV file in the directory
            csv_files = [f for f in os.listdir(image_path) if f.endswith('.csv')]
            if not csv_files:
                raise FileNotFoundError(f"No CSV file found in directory '{image_path}'.")
            csv_path = os.path.join(image_path, csv_files[0])
        else:
            csv_path = image_path

        df = pd.read_csv(csv_path)
        particle_images = []
        usernames = []
        for _, row in tqdm(df.iterrows(), total=len(df), desc="Loading avatars"):
            username = row['Username']
            img_path = row['Avatar URL']

            filename = safe_filename(username)
            filepath = f"followers_info/img/{filename}.png"

            if os.path.exists(filepath):
                image = pygame.image.load(filepath).convert_alpha()
                particle_images.append(circular_mask(image))
            else:
                try:
                    response = requests.get(img_path, timeout=10)
                    response.raise_for_status()
                    img_data = BytesIO(response.content)
                    image = pygame.image.load(img_data).convert_alpha()
                    particle_images.append(circular_mask(image))
                    # Guardar solo si no existe
                    pygame.image.save(image, filepath)
                except Exception as e:
                    print(f"Error loading image for {username}: {e}")
                    # fallback genérico
                    fallback_surface = pygame.Surface((max_radius*2, max_radius*2), pygame.SRCALPHA)
                    pygame.draw.circle(fallback_surface, (200, 200, 200, 255), (max_radius, max_radius), max_radius)
                    particle_images.append(circular_mask(fallback_surface))
                
            usernames.append(row['Username'])
        
        num_particles = len(particle_images)

        radius = get_dynamic_radius(particle_images, width, height, min_radius, max_radius, change_radius=False)

        positions = assign_position(radius, width, height, num_particles)

        # Create particles
        particles = [Particle(usernames[i], particle_images[i], radius, max_hp, max_speed, acc_magnitude, width, height, positions[i]) for i in range(num_particles)]
        
    return particles

ranking = []
kill_feed = []

def create_log(particle_a, particle_b, timestamp, frame_number):
    global ranking, kill_feed
    killed_a = not particle_a.alive
    killed_b = not particle_b.alive

    if killed_a and particle_a not in ranking:
        ranking.append(particle_a)
        kill_feed.append((str(particle_b.id), str(particle_a.id), time.time()))  # killer, victim, tiempo
    if killed_b and particle_b not in ranking:
        ranking.append(particle_b)
        kill_feed.append((str(particle_a.id), str(particle_b.id), time.time()))  # killer, victim, tiempo

    # limitar a X eventos mostrados
    if len(kill_feed) > 1:
        kill_feed.pop(0)  # borra el más viejo

    log_entries = [
        {'Particle': particle_a.id, 'Opponent': particle_b.id, 'Frame': frame_number, 'Killed': killed_a},
        {'Particle': particle_b.id, 'Opponent': particle_a.id, 'Frame': frame_number, 'Killed': killed_b}
    ]

    df = pd.DataFrame(log_entries)
    file_path = f'simulations/{timestamp}_collision_log.csv'
    write_header = not os.path.exists(file_path)
    df.to_csv(file_path, mode='a', header=write_header, index=False, lineterminator='\n')

# Get grid cell coordinates for a position
def get_cell_coords(pos, cell_size):
    return int(pos[0] // cell_size), int(pos[1] // cell_size)

# Check collisions using a grid-based approach
def check_collisions(radius, cell_size, grid_width, grid_height, particles, timestamp, frame_number):

    # Create empty grid
    grid = [[[] for _ in range(grid_height)] for _ in range(grid_width)]

    # Assign particles to grid cells
    for p in particles:
        if p.alive:
            cell_x, cell_y = get_cell_coords(p.pos, cell_size)
            grid[cell_x][cell_y].append(p)

    # Check each cell and neighbors
    for i in range(grid_width):
        for j in range(grid_height):
            cell_particles = grid[i][j]
            for a in cell_particles:
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        ni, nj = i + dx, j + dy
                        if 0 <= ni < grid_width and 0 <= nj < grid_height:
                            for b in grid[ni][nj]:
                                if b is a or not b.alive:
                                    continue
                                if not a.alive:
                                    break  # Already eliminated
                                dist_pos = a.pos - b.pos
                                dist = np.linalg.norm(dist_pos)
                                if dist < radius * 2:
                                    # Compute direction of collision
                                    direction = dist_pos / dist if dist != 0 else np.array([1.0, 0.0])

                                    # Repel particles slightly to avoid sticking
                                    repel_distance = 0.1 * radius
                                    a.pos += direction * repel_distance
                                    b.pos -= direction * repel_distance

                                    # Damage calculation, the force is the difference in velocities
                                    # and the damage is the minimum of the force and the minimum HP of both particles,
                                    # so only one particle can be eliminated at a time.
                                    force_a = np.linalg.norm(a.vel)*2
                                    force_b = np.linalg.norm(b.vel)*2

                                    min_hp = min(a.hp, b.hp)
                                    a.damage(min(force_b, min_hp))
                                    b.damage(min(force_a, min_hp))

                                    # Conservation of momentum (1D elastic collision in collision direction)
                                    v1 = np.dot(a.vel, direction)
                                    v2 = np.dot(b.vel, direction)
                                    m1 = a.mass
                                    m2 = b.mass

                                    # New velocities in collision direction
                                    new_v1 = (v1 * (m1 - m2) + 2 * m2 * v2) / (m1 + m2)
                                    new_v2 = (v2 * (m2 - m1) + 2 * m1 * v1) / (m1 + m2)

                                    # Update velocities
                                    a.vel += (new_v1 - v1) * direction
                                    b.vel += (new_v2 - v2) * direction

                                    if not a.alive or not b.alive:
                                        create_log(a, b, timestamp, frame_number)

def display_winner(font, particles, screen, width, height, radius):
    global ranking
    # Último vivo
    winner = next(p for p in particles if p.alive)
    if winner not in ranking:
        ranking.append(winner)

    # Posiciones verticales para los textos, centrados horizontalmente
    start_y = int(height * 0.5)   # antes estaba height - radius*2
    spacing = 50                   # separación entre cada línea de texto
    padding = 10                   # espacio alrededor del texto para el fondo negro

    colors = [(255, 215, 0), (192, 192, 192), (205, 127, 50)]  # colores para 1°, 2°, 3°
    labels = ['Ganó', '2do', '3ro']

    top3 = ranking[-1:-4:-1]  # último vivo y los dos anteriores

    # Mostrar imagen del primer puesto centrada y detrás de los textos
    img_diameter = radius * 3
    img = pygame.transform.smoothscale(top3[0].image, (img_diameter, img_diameter))
    img_rect = img.get_rect(center=(width // 2, height // 4))
    screen.blit(img, img_rect)

    # Mostrar los textos por encima con fondo negro semi-transparente
    for i, particle in enumerate(top3):
        text = font.render(f"{labels[i]}: {particle.id}", True, colors[i])
        text_rect = text.get_rect(center=(width // 2, start_y + i * spacing))

        # Fondo negro semi-transparente
        bg_surface = pygame.Surface((text_rect.width + 2*padding, text_rect.height + 2*padding), pygame.SRCALPHA)
        bg_surface.fill((0, 0, 0, 150))  # 150 = opacidad (0 transparente, 255 opaco)
        screen.blit(bg_surface, (text_rect.left - padding, text_rect.top - padding))

        screen.blit(text, text_rect)

    pygame.display.flip()

def add_particle_to_frames(screen, frames):
    frame_surface = pygame.surfarray.array3d(screen)
    frame_surface = frame_surface.transpose([1, 0, 2])  # Convert to (height, width, RGB)
    frames.append(frame_surface)
    return frames

def remove_dead_particles(particles):
    particles = [p for p in particles if p.alive]
    return particles