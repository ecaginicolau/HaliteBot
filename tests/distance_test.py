# Import & build cython at runtime
import pyximport
pyximport.install()

from bot.navigation import calculate_distance_between as distance2, Circle, calculate_angle_between as angle2, \
    closest_point_to as closest_point_to2, navigate as navigate2, intersect_segment_circle as intersect_segment_circle2

from time import time
from tests.distance_python import calculate_distance_between as distance1, calculate_angle_between as angle1, \
    closest_point_to as closest_point_to1, navigate as navigate1, intersect_segment_circle as intersect_segment_circle1


p1 = Circle(60, 80, 3)
p2 = Circle(180, 80, 2)
circle = Circle(-2, 2, 1)


nb = 1000000


"""
Distance
"""
print("\n\nDistance:")
start_time = time()
for i in range(nb):
    d = distance1(p1, p2)
end_time = time()
duration = end_time - start_time
print("distance: %s" % d)
print("python duration : %s" % duration)

start_time = time()
for i in range(nb):
    d = distance2(p1, p2)
end_time = time()
duration = end_time - start_time
print("distance: %s" % d)
print("cython duration : %s" % duration)



"""
Angle
"""
print("\n\nAngle:")
start_time = time()
for i in range(nb):
    a = angle1(p1, p2)
end_time = time()
duration = end_time - start_time
print("angle: %s" % a)
print("python duration : %s" % duration)

start_time = time()
for i in range(nb):
    a = angle2(p1, p2)
end_time = time()
duration = end_time - start_time
print("angle: %s" % a)
print("cython duration : %s" % duration)

"""
closest_point_to
"""
print("\n\nclosest_point_to:")
start_time = time()
for i in range(nb):
    p = closest_point_to1(p1, p2, 1)
end_time = time()
duration = end_time - start_time
print("position: %s:%s" % (p.x, p.y))
print("python duration : %s" % duration)

start_time = time()
for i in range(nb):
    p = closest_point_to2(p1, p2, 1)
end_time = time()
duration = end_time - start_time
print("position: %s:%s" % (p.x, p.y))
print("cython duration : %s" % duration)

"""
navigate
"""
print("\n\nnavigate:")
start_time = time()
for i in range(nb):
    speed, angle = navigate1(p1, p2, None, 50, ignore_ships=True, ignore_planets=True)
end_time = time()
duration = end_time - start_time
print("speed: %s, angle: %s" % (speed, angle))
print("python duration : %s" % duration)

start_time = time()
for i in range(nb):
    speed, angle = navigate2(p1, p2, None, 50, ignore_ships=True, ignore_planets=True)
end_time = time()
duration = end_time - start_time
print("speed: %s, angle: %s" % (speed, angle))
print("cython duration : %s" % duration)

"""
intersect_segment_circle
"""
print("\n\nintersect_segment_circle:")
start_time = time()
for i in range(nb):
    y = intersect_segment_circle1(p1, p2, circle)
end_time = time()
duration = end_time - start_time
print("intersect: %s" % y)
print("python duration : %s" % duration)

start_time = time()
for i in range(nb):
    y = intersect_segment_circle2(p1, p2, circle)
end_time = time()
duration = end_time - start_time
print("intersect: %s" % y)
print("cython duration : %s" % duration)

