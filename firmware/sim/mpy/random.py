# MicroPython only: a stand-in for random.Random with gauss(), the one call the sensor models make.
# test_mpy.py uses this same generator under ordinary Python too, so that both runs see the same sensor noise.
import math


class Random:
    def __init__(self, seed=1):
        self.x = seed & 0x7FFFFFFF or 1

    def random(self):
        self.x = (self.x * 48271) % 2147483647          # Lehmer generator: exact in integers on both interpreters
        return self.x / 2147483647.0

    def gauss(self, mu, sd):
        a, b = self.random(), self.random()
        return mu + sd * math.sqrt(-2.0 * math.log(a)) * math.cos(2 * math.pi * b)
