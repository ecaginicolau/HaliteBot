from bot.settings import SHIP_INFLUENCE, PLANET_INFLUENCE, INFLUENCE_STEP, INFLUENCE_ZONE, INFLUENCE_THRESHOLD
from PIL import Image, ImageDraw
from collections import defaultdict
import os
import logging


class Influence(object):

    width = 0
    height = 0
    img = None
    __circle_to_draw_dict = defaultdict(list)
    player_id = 0
    turn = 0

    @staticmethod
    def init(player_id):
        # Store the player id, will be used to distinguish ships
        Influence.player_id = player_id

    @staticmethod
    def add_circle_position(entity, influence, empty_planet = False):
        # By default empty planet have a very thin influence zone
        if empty_planet:
            min_x = entity.pos.x - entity.pos.radius - influence * 2
            min_y = entity.pos.y - entity.pos.radius - influence * 2
            max_x = entity.pos.x + entity.pos.radius + influence * 2
            max_y = entity.pos.y + entity.pos.radius + influence * 2
            color = INFLUENCE_ZONE
            Influence.__circle_to_draw_dict[color].append([min_x, min_y, max_x, max_y])
        else:
            # Other planets or ships have a gradient of influence zone
            for i in range(INFLUENCE_STEP):
                min_x = entity.pos.x - entity.pos.radius - influence * (INFLUENCE_STEP - i)
                min_y = entity.pos.y - entity.pos.radius - influence * (INFLUENCE_STEP - i)
                max_x = entity.pos.x + entity.pos.radius + influence * (INFLUENCE_STEP - i)
                max_y = entity.pos.y + entity.pos.radius + influence * (INFLUENCE_STEP - i)
                color = INFLUENCE_ZONE * (i + 1)
                Influence.__circle_to_draw_dict[color].append([min_x, min_y, max_x, max_y])

    @staticmethod
    def update_game_map(game_map):
        Influence.width = game_map.width
        Influence.height = game_map.height
        Influence.__circle_to_draw_dict = defaultdict(list)
        Influence.img = Image.new('L', (Influence.width, Influence.height))
        draw = ImageDraw.Draw(Influence.img)

        """
        # First draw empty planet
        for planet_id, planet in Monitor.get_empty_planets().items():
            Influence.add_circle_position(planet, PLANET_INFLUENCE, empty_planet=True)
        """
        # Get the influence zone of every ships
        for ship in game_map.get_me().all_ships():
            # Draw a circle for every ship
            Influence.add_circle_position(ship, SHIP_INFLUENCE, empty_planet=False)

        # Get the influence zone of every planets
        for planet in game_map.all_planets():
            # Make sure it's our planet
            if planet.is_owned() and planet.owner.id == Influence.player_id:
                Influence.add_circle_position(planet, PLANET_INFLUENCE, empty_planet=False)

        # Now draw , ordered by color
        for color in sorted(Influence.__circle_to_draw_dict.keys()):
            for circle in Influence.__circle_to_draw_dict[color]:
                draw.ellipse(circle, fill=color, outline=color)

        if os.environ['RAMPA_LOG_LEVEL'] == "DEBUG":
            Influence.img.save("influence\\influence_%s.png" % Influence.turn)

        Influence.turn += 1

    @staticmethod
    def get_point_influence(pos):
        """
        Return the influence value of a single position (Circle)
        :param pos:
        :return: and int between 0 and 255
        """
        return Influence.img.getpixel((pos.x, pos.y))

    @staticmethod
    def is_in_influence_zone(pos):
        """
        Check if a position is inside the influence zone
        :param pos:
        :return:
        """
        return Influence.get_point_influence(pos) > INFLUENCE_THRESHOLD
