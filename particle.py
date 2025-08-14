import pygame
import numpy as np
import random
import math


class Particle:
    def __init__(self, pid, image, radius, max_hp, max_speed, acc_magnitude, width, height, position):
        self.id = pid
        self.image = image
        self.radius = radius
        self.max_hp = max_hp
        self.max_speed = max_speed
        self.acc_magnitude = acc_magnitude
        self.width = width
        self.height = height  
        # Random initial position within bounds
        self.pos = position
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.5, 1)
        # Initial velocity vector
        self.vel = np.array([math.cos(angle) * speed, math.sin(angle) * speed], dtype=float)
        self.acc_mag = 0.01  # Acceleration magnitude
        self.hp = max_hp
        self.alive = True
        self.mass = 1.0  

    def move(self):
        if not self.alive:
            return

        # Apply acceleration in the direction of velocity
        if np.linalg.norm(self.vel) > 0:
            acc_dir = self.vel / np.linalg.norm(self.vel)
            acc = acc_dir * self.acc_mag
        else:
            acc = np.array([0.0, 0.0])

        self.vel += acc

        speed = np.linalg.norm(self.vel)
        if speed > self.max_speed:
            self.vel = (self.vel / speed) * self.max_speed

        self.pos += self.vel

        # Bounce off edges
        THR = 0.1  # Threshold to avoid sticking to the edge
        for i, limit in enumerate([self.width, self.height]):
            min_pos = self.radius + THR
            max_pos = limit - self.radius - THR
            if self.pos[i] < min_pos:
                self.pos[i] = min_pos
                self.vel[i] *= -1
            elif self.pos[i] > max_pos:
                self.pos[i] = max_pos
                self.vel[i] *= -1

    def draw(self, surface):
        # Gradient color based on HP (green to red)
        hp_ratio = max(0, min(self.hp / self.max_hp, 1))
        # Resize the image to match the particle's radius
        scaled_image = pygame.transform.smoothscale(self.image, (self.radius * 2, self.radius * 2))
        img_rect = scaled_image.get_rect(center=(int(self.pos[0]), int(self.pos[1])))
        # Draw the prepared image
        surface.blit(scaled_image, img_rect)
        # HP bar with gradient and rounded border
        bar_width = self.radius * 2
        bar_height = 8
        x = int(self.pos[0]) - self.radius
        y = int(self.pos[1]) - self.radius - 14

        # HP bar background (dark gray, rounded border)
        bg_rect = pygame.Rect(x, y, bar_width, bar_height)
        pygame.draw.rect(surface, (40, 40, 40), bg_rect, border_radius=4)

        # HP bar gradient (red to green)
        hp_bar_len = int(hp_ratio * bar_width)
        for i in range(hp_bar_len):
            grad_ratio = i / bar_width
            r = int(255 * (1 - grad_ratio))
            g = int(255 * grad_ratio)
            color = (r, g, 40)
            pygame.draw.rect(surface, color, (x + i, y, 1, bar_height), border_radius=0)

        # Thin white border
        pygame.draw.rect(surface, (220,220,220), bg_rect, width=1, border_radius=4)

    def damage(self, force):
        self.hp -= force
        if self.hp <= 0:
            self.alive = False
            self.vel = np.array([0, 0], dtype=float)